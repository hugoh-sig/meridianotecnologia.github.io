#!/usr/bin/env python3
"""Pipeline de sensoriamento remoto Sentinel-2, parametrizado por cena.

Uso:
    python scripts/sensoriamento/pipeline.py --cena fortaleza
    python scripts/sensoriamento/pipeline.py --cena <nome> --config scripts/sensoriamento/cenas.yaml

Etapas:
  1. Coleção COPERNICUS/S2_SR_HARMONIZED filtrada por bbox, período e nuvem.
  2. Máscara de nuvem/sombra pela banda SCL (classes definidas em cenas.yaml).
  3. Composição mediana; registro das cenas e datas de aquisição.
  4. Camadas: cor verdadeira (B4,B3,B2), NDVI, MNDWI (B11 reamostrada a 10 m).
  5. Download em GeoTIFF (UTM SIRGAS 2000, fuso derivado do bbox) para
     dados/bruto/sensoriamento/<cena>/.
  6. Métricas (água, NDVI no continente, linha de costa, pixels válidos).
  7. COG + tiles XYZ + imagens estáticas WebP/AVIF em
     dados/processado/sensoriamento/<cena>/.
  8. FICHA.md e PROCEDENCIA-S2.md gerados automaticamente.

Autenticação: credenciais de usuário do earthengine-api já presentes na
máquina (fora do repositório). Nenhuma credencial é lida ou gravada aqui.
"""

import argparse
import datetime as dt
import hashlib
import json
import math
import shutil
import subprocess
import sys
import time
from pathlib import Path

import numpy as np
import requests
import yaml

REPO = Path(__file__).resolve().parents[2]
TILE_PX = 2048          # lado (px) de cada requisição de download ao EE
RES_M = 10              # resolução de exportação (m)
NODATA_F = -9999.0      # nodata das camadas float (NDVI, MNDWI)
LIMITE_GITIGNORE = 50 * 1000 * 1000  # 50 MB (decimais, como reportado nos logs)

# ---------------------------------------------------------------- utilidades


def log(msg):
    print(f"[{dt.datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)


def sha256(path, bufsize=1 << 20):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(bufsize):
            h.update(chunk)
    return h.hexdigest()


def run(cmd):
    log("$ " + " ".join(str(c) for c in cmd))
    subprocess.run([str(c) for c in cmd], check=True, capture_output=True, text=True)


def utm_sirgas2000_epsg(bbox):
    """Fuso UTM derivado do centro do bbox (WGS84) -> EPSG SIRGAS 2000.

    Fusos 17S-25S (Brasil): EPSG 31977-31985 = 31960 + fuso.
    Fora dessa faixa, recua para WGS84/UTM (326xx N, 327xx S).
    """
    lon = (bbox[0] + bbox[2]) / 2.0
    lat = (bbox[1] + bbox[3]) / 2.0
    fuso = int((lon + 180) // 6) + 1
    if lat < 0 and 17 <= fuso <= 25:
        return fuso, 31960 + fuso, f"SIRGAS 2000 / UTM zone {fuso}S"
    base = 32600 if lat >= 0 else 32700
    hemi = "N" if lat >= 0 else "S"
    return fuso, base + fuso, f"WGS 84 / UTM zone {fuso}{hemi} (fallback fora de 17S-25S)"


def grade_utm(bbox, epsg):
    """Grade de exportação: bbox reprojetado ao UTM e ajustado à grade de 10 m."""
    from rasterio.warp import transform_bounds

    xmin, ymin, xmax, ymax = transform_bounds("EPSG:4326", f"EPSG:{epsg}", *bbox, densify_pts=21)
    xmin = math.floor(xmin / RES_M) * RES_M
    ymin = math.floor(ymin / RES_M) * RES_M
    xmax = math.ceil(xmax / RES_M) * RES_M
    ymax = math.ceil(ymax / RES_M) * RES_M
    largura = round((xmax - xmin) / RES_M)
    altura = round((ymax - ymin) / RES_M)
    return xmin, ymax, largura, altura  # origem = canto superior esquerdo


# ------------------------------------------------------------ Earth Engine


def montar_colecao(ee, cfg, cena):
    regiao = ee.Geometry.Rectangle(cena["bbox"], proj="EPSG:4326", geodesic=False)
    col = (
        ee.ImageCollection(cfg["colecao"])
        .filterBounds(regiao)
        .filterDate(cena["data_inicial"], cena["data_final"])
        .filter(ee.Filter.lte("CLOUDY_PIXEL_PERCENTAGE", cena["nuvem_max"]))
    )
    return regiao, col


def listar_cenas(col):
    ids = col.aggregate_array("system:index").getInfo()
    tempos = col.aggregate_array("system:time_start").getInfo()
    nuvens = col.aggregate_array("CLOUDY_PIXEL_PERCENTAGE").getInfo()
    tiles = col.aggregate_array("MGRS_TILE").getInfo()
    cenas = [
        {
            "id": i,
            "data": dt.datetime.fromtimestamp(t / 1000, dt.timezone.utc).strftime("%Y-%m-%d"),
            "hora_utc": dt.datetime.fromtimestamp(t / 1000, dt.timezone.utc).strftime("%H:%M:%S"),
            "nuvem_pct": round(n, 2),
            "tile_mgrs": m,
        }
        for i, t, n, m in zip(ids, tempos, nuvens, tiles)
    ]
    return sorted(cenas, key=lambda c: (c["data"], c["tile_mgrs"]))


def compor_mediana(ee, col, scl_classes):
    """Máscara SCL + reamostragem bilinear (relevante para B11, 20 m) + mediana."""
    def preparar(img):
        scl = img.select("SCL")
        ruim = ee.Image(0)
        for c in scl_classes:
            ruim = ruim.Or(scl.eq(c))
        img = img.updateMask(ruim.Not())
        # bilinear: efetivamente neutro nas bandas de 10 m (grades coincidem);
        # garante B11 (20 m) interpolada ao ser lida na grade de 10 m
        return img.select(["B2", "B3", "B4", "B8", "B11"]).resample("bilinear")

    return col.map(preparar).median()


def baixar_camada(ee, imagem, bandas, epsg, x0, y0, largura, altura, destino, dtype, nodata):
    """Baixa a imagem em blocos de TILE_PX (limite de getDownloadURL) e mosaica."""
    import rasterio
    from rasterio.transform import from_origin

    destino.parent.mkdir(parents=True, exist_ok=True)
    ntx = math.ceil(largura / TILE_PX)
    nty = math.ceil(altura / TILE_PX)
    mosaico = np.full((len(bandas), altura, largura), nodata, dtype=dtype)

    for ty in range(nty):
        for tx in range(ntx):
            w = min(TILE_PX, largura - tx * TILE_PX)
            h = min(TILE_PX, altura - ty * TILE_PX)
            transform = [RES_M, 0, x0 + tx * TILE_PX * RES_M, 0, -RES_M, y0 - ty * TILE_PX * RES_M]
            params = {
                "bands": bandas,
                "crs": f"EPSG:{epsg}",
                "crs_transform": transform,
                "dimensions": f"{w}x{h}",
                "format": "GEO_TIFF",
            }
            for tentativa in range(1, 4):
                try:
                    url = imagem.getDownloadURL(params)
                    resp = requests.get(url, timeout=600)
                    resp.raise_for_status()
                    break
                except Exception as exc:  # noqa: BLE001 — repete quota/timeout do EE
                    if tentativa == 3:
                        raise
                    log(f"    bloco ({tx},{ty}) tentativa {tentativa} falhou ({exc}); repetindo")
                    time.sleep(15 * tentativa)
            bloco = destino.parent / f"_bloco_{destino.stem}_{tx}_{ty}.tif"
            bloco.write_bytes(resp.content)
            with rasterio.open(bloco) as src:
                dados = src.read()
            mosaico[:, ty * TILE_PX : ty * TILE_PX + h, tx * TILE_PX : tx * TILE_PX + w] = dados.astype(dtype)
            bloco.unlink()
            log(f"    bloco {ty * ntx + tx + 1}/{ntx * nty} ok ({w}x{h}px)")

    perfil = {
        "driver": "GTiff",
        "width": largura,
        "height": altura,
        "count": len(bandas),
        "dtype": dtype,
        "crs": f"EPSG:{epsg}",
        "transform": from_origin(x0, y0, RES_M, RES_M),
        "nodata": nodata,
        "compress": "deflate",
        "tiled": True,
        "predictor": 3 if str(dtype).startswith("float") else 2,
    }
    with rasterio.open(destino, "w", **perfil) as dst:
        dst.write(mosaico)
    log(f"  gravado {destino.relative_to(REPO)} ({destino.stat().st_size / 1e6:.1f} MB)")
    return mosaico


# ------------------------------------------------------------------ métricas


def calcular_metricas(ndvi, mndwi):
    """Métricas locais sobre os mosaicos de 10 m já baixados."""
    from skimage import measure

    valido = ndvi != NODATA_F
    n_total = ndvi.size
    n_valido = int(valido.sum())

    agua = (mndwi > 0) & valido
    continente = valido & ~agua
    px_km2 = (RES_M * RES_M) / 1e6

    ndvi_cont = ndvi[continente]
    stats_ndvi = {
        "min": float(np.min(ndvi_cont)),
        "max": float(np.max(ndvi_cont)),
        "mediana": float(np.median(ndvi_cont)),
        "p25": float(np.percentile(ndvi_cont, 25)),
        "p75": float(np.percentile(ndvi_cont, 75)),
    }

    # Linha de costa: contorno (marching squares) do maior corpo d'água
    # conectado (o oceano), excluindo segmentos que correm pela borda da
    # imagem. Corpos d'água interiores não entram na medida.
    rotulos = measure.label(agua, connectivity=1)
    comprimento_km = 0.0
    if rotulos.max() > 0:
        contagens = np.bincount(rotulos.ravel())
        contagens[0] = 0
        oceano = rotulos == int(np.argmax(contagens))
        h, w = oceano.shape

        def na_borda(p):
            return p[0] < 1.0 or p[0] > h - 2.0 or p[1] < 1.0 or p[1] > w - 2.0

        for contorno in measure.find_contours(oceano.astype(np.uint8), 0.5):
            pontos = np.asarray(contorno)
            seg = np.hypot(*(np.diff(pontos, axis=0).T))
            for i, d in enumerate(seg):
                if na_borda(pontos[i]) and na_borda(pontos[i + 1]):
                    continue
                comprimento_km += d * RES_M / 1000.0

    return {
        "pixels_validos_pct": round(100.0 * n_valido / n_total, 2),
        "area_agua_km2": round(float(agua.sum()) * px_km2, 2),
        "area_continente_km2": round(float(continente.sum()) * px_km2, 2),
        "ndvi_continente": {k: round(v, 4) for k, v in stats_ndvi.items()},
        "linha_costa_km": round(comprimento_km, 1),
    }


# ------------------------------------------------------------------ saída web


def gerar_cog(origem, destino, fotografico):
    destino.parent.mkdir(parents=True, exist_ok=True)
    opts = ["-of", "COG", "-co", "OVERVIEW_RESAMPLING=AVERAGE", "-co", "BLOCKSIZE=512"]
    if fotografico:
        opts += ["-co", "COMPRESS=JPEG", "-co", "QUALITY=85"]
    else:
        opts += ["-co", "COMPRESS=DEFLATE", "-co", "PREDICTOR=3"]
    run(["gdal_translate", *opts, origem, destino])


def rampa_cores(nome, pasta):
    """Rampas de cor para tiles de NDVI e MNDWI.

    Fonte única em realce_web.py: NDVI sequencial de matiz único (verde,
    claro->escuro, interpolada em CIELAB) e MNDWI divergente com ponto
    médio neutro em 0. Documentadas na FICHA de cada cena.
    """
    from realce_web import escrever_rampa, rampa_entradas

    return escrever_rampa(nome, pasta), rampa_entradas(nome)


def zoom_maximo(lat_centro):
    """Menor zoom XYZ cuja resolução (m/px) é <= resolução nativa de 10 m."""
    z = math.ceil(math.log2(156543.03392 * math.cos(math.radians(lat_centro)) / RES_M))
    return max(z, 1)


def gerar_tiles(origem_rgb, pasta_tiles, z_min, z_max):
    if pasta_tiles.exists():
        shutil.rmtree(pasta_tiles)
    run([
        "gdal2tiles.py", "--xyz", "-z", f"{z_min}-{z_max}", "-w", "none",
        "--processes", "4", "--tiledriver", "WEBP", "--webp-quality", "75",
        "-r", "average", origem_rgb, pasta_tiles,
    ])
    tiles = sorted(pasta_tiles.rglob("*.webp"))
    por_zoom = {}
    for t in tiles:
        z = int(t.relative_to(pasta_tiles).parts[0])
        por_zoom.setdefault(z, [0, 0])
        por_zoom[z][0] += 1
        por_zoom[z][1] += t.stat().st_size
    return tiles, {z: {"tiles": n, "kb": round(b / 1024, 1)} for z, (n, b) in sorted(por_zoom.items())}


def gerar_estaticas(tif_rgb, pasta_web, nome):
    """Versões estáticas da cor verdadeira em WebP e AVIF (1600/1000/600 px)."""
    import rasterio
    from PIL import Image

    pasta_web.mkdir(parents=True, exist_ok=True)
    with rasterio.open(tif_rgb) as src:
        rgb = np.transpose(src.read(), (1, 2, 0)).astype(np.uint8)
    im = Image.fromarray(rgb)
    saidas = []
    for largura in (1600, 1000, 600):
        altura = round(im.height * largura / im.width)
        red = im.resize((largura, altura), Image.LANCZOS)
        for fmt, ext, kw in (
            ("WEBP", "webp", {"quality": 80, "method": 6}),
            ("AVIF", "avif", {"quality": 55}),
        ):
            destino = pasta_web / f"{nome}_cor-verdadeira_{largura}.{ext}"
            red.save(destino, fmt, **kw)
            saidas.append(destino)
    return saidas


# -------------------------------------------------------------- documentação


def atualizar_gitignore(arquivos):
    """Adiciona ao .gitignore todo arquivo gerado acima de 50 MB (idempotente)."""
    gi = REPO / ".gitignore"
    linhas = gi.read_text().splitlines() if gi.exists() else []
    grandes = []
    for arq in arquivos:
        if arq.stat().st_size > LIMITE_GITIGNORE:
            rel = str(arq.relative_to(REPO))
            grandes.append(rel)
            if rel not in linhas:
                linhas.append(rel)
    if grandes:
        gi.write_text("\n".join(linhas) + "\n")
    return grandes


def escrever_ficha(caminho, ctx):
    m = ctx["metricas"]
    n = m["ndvi_continente"]
    datas = sorted({c["data"] for c in ctx["cenas"]})
    linhas_cenas = "\n".join(
        f"| {c['data']} {c['hora_utc']} | {c['tile_mgrs']} | {c['nuvem_pct']}% | `{c['id']}` |"
        for c in ctx["cenas"]
    )
    caminho.write_text(f"""# FICHA — Sensoriamento remoto: {ctx['nome']}

## Fonte e período

| Campo | Valor |
|---|---|
| Sensor | Sentinel-2 MSI (missões S2A/S2B/S2C, ESA/Copernicus) |
| Nível de processamento | Level-2A, refletância de superfície (correção Sen2Cor) |
| Coleção exata (Earth Engine) | `{ctx['colecao']}` |
| Período filtrado | {ctx['data_inicial']} a {ctx['data_final']} (data final exclusiva) |
| Justificativa do período | {ctx['justificativa_periodo']} |
| Nuvem máxima por cena | {ctx['nuvem_max']}% (metadado `CLOUDY_PIXEL_PERCENTAGE`) |
| Cenas usadas na composição | {len(ctx['cenas'])} |
| Datas de aquisição distintas | {len(datas)}: {", ".join(datas)} |

## Área de interesse

bbox WGS84 (O, S, L, N): `{ctx['bbox']}`

Memória de cálculo do bbox:

{ctx['memoria_bbox']}

## Máscara de nuvem e sombra

Banda `SCL` (Scene Classification, Sen2Cor). Pixels removidos nas classes:
{ctx['scl_txt']}. A composição usa apenas observações restantes.

## Composição e camadas

Composição por **MEDIANA** pixel a pixel das {len(ctx['cenas'])} cenas mascaradas.

| Camada | Fórmula (bandas nomeadas) | Observações |
|---|---|---|
| Cor verdadeira | R=`B4` (665 nm), G=`B3` (560 nm), B=`B2` (490 nm) | Esticamento linear declarado: refletância 0.00–0.25 (DN 0–2500) → 0–255 (8 bits) |
| NDVI | (`B8` − `B4`) / (`B8` + `B4`) | B8 = NIR 842 nm; float32, nodata {NODATA_F:.0f} |
| MNDWI | (`B3` − `B11`) / (`B3` + `B11`) | B11 = SWIR1 1610 nm, nativa 20 m, **reamostrada bilinearmente a 10 m**; float32, nodata {NODATA_F:.0f} |

## Projeções

| Etapa | CRS |
|---|---|
| bbox de entrada | WGS84 (EPSG:4326) |
| GeoTIFF/COG exportados | {ctx['crs_nome']} (EPSG:{ctx['epsg']}), fuso derivado do centro do bbox (fuso {ctx['fuso']}), resolução {RES_M} m |
| Tiles XYZ | Web Mercator (EPSG:3857), zooms {ctx['z_min']}–{ctx['z_max']} |

## Métricas

| Métrica | Valor |
|---|---|
| Pixels válidos após a máscara | {m['pixels_validos_pct']}% da grade exportada |
| Área de água (MNDWI > 0) | {m['area_agua_km2']} km² |
| Área de continente | {m['area_continente_km2']} km² |
| NDVI no continente — mín | {n['min']} |
| NDVI no continente — p25 | {n['p25']} |
| NDVI no continente — mediana | {n['mediana']} |
| NDVI no continente — p75 | {n['p75']} |
| NDVI no continente — máx | {n['max']} |
| Extensão da linha de costa | {m['linha_costa_km']} km |

Método da linha de costa: contorno (marching squares) do maior corpo d'água
conectado no MNDWI > 0, medido na resolução de 10 m, excluindo segmentos que
correm pela borda da imagem; corpos d'água interiores não entram. O valor
depende da resolução de medida (efeito de escala em linhas costeiras).

### Datas de aquisição de todas as cenas

| Data (UTC) | Tile MGRS | Nuvem | ID da cena |
|---|---|---|---|
{linhas_cenas}

## LIMITAÇÕES

* **NDVI não é interpretável sobre água** — os valores sobre o oceano e
  corpos d'água não medem vegetação; use a máscara MNDWI antes de ler NDVI.
* **A linha de costa varia com a maré**, que não é capturada: cada cena foi
  adquirida em um estágio de maré diferente e a mediana mistura esses estágios.
* **A composição mediana não representa uma data específica** — cada pixel
  pode vir de cenas diferentes dentro do período.
* **MNDWI confunde sombra e superfícies escuras com água** (sombras de
  nuvem residuais, sombras urbanas e de relevo, asfalto úmido podem
  aparecer como água).

---
Gerado automaticamente por `scripts/sensoriamento/pipeline.py` em {ctx['executado_em']}.
""")


def escrever_procedencia(caminho, ctx, hashes):
    linhas = "\n".join(f"| `{rel}` | {tam} | `{h}` |" for rel, tam, h in hashes)
    ignorados = "\n".join(f"* `{g}`" for g in ctx["gitignore_grandes"]) or "* (nenhum)"
    caminho.write_text(f"""# PROCEDÊNCIA — Sentinel-2 ({ctx['nome']})

| Campo | Valor |
|---|---|
| Coleção | `{ctx['colecao']}` (Google Earth Engine) |
| Data de execução | {ctx['executado_em']} |
| earthengine-api | {ctx['versao_ee']} |
| Projeto EE | {ctx['projeto_ee']} |
| Script | `scripts/sensoriamento/pipeline.py` (config `scripts/sensoriamento/cenas.yaml`) |
| Tiles XYZ | {ctx['n_tiles']} arquivos WebP em `{ctx['rel_tiles']}` (hash agregado sha256 `{ctx['hash_tiles']}`) |

## Hash SHA-256 dos arquivos

| Arquivo | Tamanho | SHA-256 |
|---|---|---|
{linhas}

## Arquivos acima de 50 MB (fora do versionamento, no .gitignore)

{ignorados}

---
Gerado automaticamente por `scripts/sensoriamento/pipeline.py`.
""")


# ---------------------------------------------------------------------- main


def main():
    t0 = time.monotonic()
    ap = argparse.ArgumentParser(description="Pipeline Sentinel-2 parametrizado")
    ap.add_argument("--cena", required=True, help="nome da cena em cenas.yaml")
    ap.add_argument("--config", default=str(Path(__file__).parent / "cenas.yaml"))
    args = ap.parse_args()

    cfg = yaml.safe_load(Path(args.config).read_text())
    if args.cena not in cfg["cenas"]:
        sys.exit(f"Cena '{args.cena}' não encontrada em {args.config}")
    cena = cfg["cenas"][args.cena]
    nome = args.cena

    import ee

    log(f"Inicializando Earth Engine (projeto {cfg['projeto_ee']})…")
    ee.Initialize(project=cfg["projeto_ee"])

    bbox = cena["bbox"]
    fuso, epsg, crs_nome = utm_sirgas2000_epsg(bbox)
    x0, y0, largura, altura = grade_utm(bbox, epsg)
    log(f"CRS de exportação: {crs_nome} (EPSG:{epsg}); grade {largura}x{altura} px a {RES_M} m")

    regiao, col = montar_colecao(ee, cfg, cena)
    cenas = listar_cenas(col)
    if not cenas:
        sys.exit("Nenhuma cena atende aos filtros — ajuste período ou nuvem_max.")
    log(f"{len(cenas)} cenas atendem aos filtros:")
    for c in cenas:
        log(f"  {c['data']} {c['hora_utc']} UTC  {c['tile_mgrs']}  nuvem {c['nuvem_pct']}%")

    comp = compor_mediana(ee, col, cfg["scl_mascara"])

    est = cena.get("estic_cor_verdadeira", [0, 2500])
    cor = comp.select(["B4", "B3", "B2"]).visualize(min=est[0], max=est[1]).unmask(0)
    ndvi = comp.normalizedDifference(["B8", "B4"]).rename("NDVI").unmask(NODATA_F).toFloat()
    b3, b11 = comp.select("B3"), comp.select("B11")
    mndwi = b3.subtract(b11).divide(b3.add(b11)).rename("MNDWI").unmask(NODATA_F).toFloat()

    bruto = REPO / "dados" / "bruto" / "sensoriamento" / nome
    proc = REPO / "dados" / "processado" / "sensoriamento" / nome
    tif_cor = bruto / f"{nome}_cor-verdadeira.tif"
    tif_ndvi = bruto / f"{nome}_ndvi.tif"
    tif_mndwi = bruto / f"{nome}_mndwi.tif"

    log("Baixando cor verdadeira…")
    baixar_camada(ee, cor, ["vis-red", "vis-green", "vis-blue"], epsg, x0, y0, largura, altura, tif_cor, "uint8", 0)
    log("Baixando NDVI…")
    arr_ndvi = baixar_camada(ee, ndvi, ["NDVI"], epsg, x0, y0, largura, altura, tif_ndvi, "float32", NODATA_F)[0]
    log("Baixando MNDWI…")
    arr_mndwi = baixar_camada(ee, mndwi, ["MNDWI"], epsg, x0, y0, largura, altura, tif_mndwi, "float32", NODATA_F)[0]

    log("Calculando métricas…")
    metricas = calcular_metricas(arr_ndvi, arr_mndwi)
    del arr_ndvi, arr_mndwi
    log(json.dumps(metricas, ensure_ascii=False, indent=2))

    log("Gerando COGs…")
    cog_cor = proc / f"{nome}_cor-verdadeira_cog.tif"
    cog_ndvi = proc / f"{nome}_ndvi_cog.tif"
    cog_mndwi = proc / f"{nome}_mndwi_cog.tif"
    gerar_cog(tif_cor, cog_cor, fotografico=True)
    gerar_cog(tif_ndvi, cog_ndvi, fotografico=False)
    gerar_cog(tif_mndwi, cog_mndwi, fotografico=False)

    log("Gerando tiles XYZ…")
    lat_c = (bbox[1] + bbox[3]) / 2.0
    z_max = zoom_maximo(lat_c)
    z_min = max(z_max - 6, 1)
    tamanhos_zoom = {}
    todos_tiles = []
    scratch = proc / "_temp"
    scratch.mkdir(parents=True, exist_ok=True)
    camadas_tiles = {"cor-verdadeira": tif_cor}
    for nm, tif in (("ndvi", tif_ndvi), ("mndwi", tif_mndwi)):
        rampa, _ = rampa_cores(nm, scratch)
        rgb = scratch / f"{nm}_rgb.tif"
        run(["gdaldem", "color-relief", "-alpha", tif, rampa, rgb, "-co", "COMPRESS=DEFLATE"])
        camadas_tiles[nm] = rgb
    for nm, origem in camadas_tiles.items():
        pasta = proc / "tiles" / nm
        tiles, por_zoom = gerar_tiles(origem, pasta, z_min, z_max)
        todos_tiles += tiles
        tamanhos_zoom[nm] = por_zoom
        log(f"  {nm}: {len(tiles)} tiles; KB por zoom: " + ", ".join(f"z{z}={v['kb']}" for z, v in por_zoom.items()))
    shutil.rmtree(scratch)

    log("Gerando imagens estáticas WebP/AVIF…")
    estaticas = gerar_estaticas(tif_cor, proc / "web", nome)
    for e in estaticas:
        log(f"  {e.name}: {e.stat().st_size / 1024:.0f} KB")

    principais = [tif_cor, tif_ndvi, tif_mndwi, cog_cor, cog_ndvi, cog_mndwi, *estaticas]
    grandes = atualizar_gitignore(principais + todos_tiles)

    log("Escrevendo FICHA.md, PROCEDENCIA-S2.md e relatório…")
    scl_txt = ", ".join({3: "3 (sombra de nuvem)", 8: "8 (nuvem, prob. média)", 9: "9 (nuvem, prob. alta)",
                         10: "10 (cirrus fino)", 11: "11 (neve/gelo)"}.get(c, str(c)) for c in cfg["scl_mascara"])
    memoria = "\n".join("> " + l for l in cena.get("memoria_calculo_bbox", _memoria_do_yaml(args.config, nome)).splitlines())
    ctx = {
        "nome": nome, "colecao": cfg["colecao"], "projeto_ee": cfg["projeto_ee"],
        "bbox": bbox, "memoria_bbox": memoria,
        "data_inicial": cena["data_inicial"], "data_final": cena["data_final"],
        "justificativa_periodo": _justificativa_do_yaml(args.config, nome),
        "nuvem_max": cena["nuvem_max"], "cenas": cenas, "scl_txt": scl_txt,
        "fuso": fuso, "epsg": epsg, "crs_nome": crs_nome,
        "z_min": z_min, "z_max": z_max, "metricas": metricas,
        "executado_em": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "versao_ee": ee.__version__,
        "gitignore_grandes": grandes,
    }
    escrever_ficha(proc / "FICHA.md", ctx)

    hashes = [(str(p.relative_to(REPO)), f"{p.stat().st_size / 1e6:.1f} MB", sha256(p)) for p in principais]
    agregado = hashlib.sha256("".join(sorted(sha256(t) for t in todos_tiles)).encode()).hexdigest()
    ctx.update({"n_tiles": len(todos_tiles), "hash_tiles": agregado,
                "rel_tiles": str((proc / "tiles").relative_to(REPO))})
    escrever_procedencia(proc / "PROCEDENCIA-S2.md", ctx, hashes)

    relatorio = {
        "cena": nome, "cenas_s2": cenas, "metricas": metricas,
        "tiles_kb_por_zoom": tamanhos_zoom,
        "arquivos": [{"arquivo": r, "tamanho": t, "sha256": h} for r, t, h in hashes],
        "gitignore_50mb": grandes,
        "tempo_execucao_s": round(time.monotonic() - t0, 1),
        "executado_em": ctx["executado_em"],
    }
    (proc / "relatorio_execucao.json").write_text(json.dumps(relatorio, ensure_ascii=False, indent=2))
    log(f"Concluído em {relatorio['tempo_execucao_s']} s.")


def _bloco_comentario_yaml(config, nome_cena, chave):
    """Recupera o comentário imediatamente acima de `chave` na cena, no yaml."""
    linhas = Path(config).read_text().splitlines()
    dentro, buf = False, []
    for ln in linhas:
        if ln.strip().startswith(f"{nome_cena}:"):
            dentro = True
            continue
        if dentro:
            s = ln.strip()
            if s.startswith("#"):
                buf.append(s.lstrip("# "))
            elif s.startswith(f"{chave}:"):
                return "\n".join(buf).strip()
            else:
                buf = []
    return "(ver cenas.yaml)"


def _memoria_do_yaml(config, nome_cena):
    return _bloco_comentario_yaml(config, nome_cena, "bbox")


def _justificativa_do_yaml(config, nome_cena):
    txt = _bloco_comentario_yaml(config, nome_cena, "data_inicial")
    return " ".join(txt.split())


if __name__ == "__main__":
    main()
