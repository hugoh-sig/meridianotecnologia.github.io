#!/usr/bin/env python3
"""Pós-processamento de exibição web das cenas do pipeline Sentinel-2.

Uso:
    python scripts/sensoriamento/realce_web.py --cena fortaleza

Opera SOMENTE sobre arquivos locais já baixados (não refaz downloads) e
NÃO altera os produtos originais. Gera, por cena:

  1. Segunda versão da cor verdadeira com realce para web:
     esticamento por percentis (p2-p98, por banda, pixels válidos),
     gama suave e leve aumento de saturação — WebP e AVIF em 1600/1000/600 px
     (sufixo `-realce`; as estáticas originais permanecem intactas).
  2. Rampas de cor revisadas para NDVI (sequencial de matiz único, verde,
     claro->escuro, passos interpolados em CIELAB — perceptualmente
     ordenada) e MNDWI (divergente com ponto médio neutro em 0);
     regenera os tiles XYZ dessas duas camadas com as novas rampas.
  3. Conjunto de camadas alinhadas pixel a pixel (cor realçada, NDVI,
     MNDWI) a 1600 px, mesmas dimensões e enquadramento, para transição
     por sobreposição (crossfade CSS) na página.
  4. Atualiza FICHA.md (seção "Realce aplicado nas imagens de exibição",
     entre marcadores, idempotente) e PROCEDENCIA-S2.md (hashes dos novos
     arquivos e hash agregado dos tiles).
"""

import argparse
import datetime as dt
import hashlib
import json
import math
import re
import shutil
import subprocess
import sys
from pathlib import Path

import numpy as np
import rasterio
from PIL import Image, ImageEnhance
from skimage import color as skcolor

REPO = Path(__file__).resolve().parents[2]
NODATA_F = -9999.0
RES_M = 10

# Parâmetros do realce (iguais para todas as cenas; os percentis em DN
# são calculados por cena e registrados na FICHA)
PCT_INF, PCT_SUP = 2, 98
GAMA = 1.2          # saída = entrada^(1/1.2), aplicada após o esticamento
SATURACAO = 1.15    # PIL ImageEnhance.Color

LARGURAS = (1600, 1000, 600)
FORMATOS = (("WEBP", "webp", {"quality": 80, "method": 6}),
            ("AVIF", "avif", {"quality": 55}))


def hex_rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i : i + 2], 16) for i in (0, 2, 4))


def rgb_hex(rgb):
    return "#{:02x}{:02x}{:02x}".format(*rgb)


def stops_lab(hex_ini, hex_fim, valores):
    """Passos interpolados linearmente em CIELAB entre duas cores.

    Interpolação linear no espaço perceptual CIELAB => passos com
    diferença perceptual (Delta-E) aproximadamente constante e
    luminosidade monotônica (rampa perceptualmente ordenada).
    """
    lab_i = skcolor.rgb2lab(np.array([[hex_rgb(hex_ini)]]) / 255.0)[0, 0]
    lab_f = skcolor.rgb2lab(np.array([[hex_rgb(hex_fim)]]) / 255.0)[0, 0]
    out = []
    for k, v in enumerate(valores):
        t = k / (len(valores) - 1)
        lab = (1 - t) * lab_i + t * lab_f
        rgb = skcolor.lab2rgb(lab[None, None, :])[0, 0]
        out.append((v, tuple(int(round(c * 255)) for c in np.clip(rgb, 0, 1))))
    return out


# NDVI: sequencial de matiz único (verde), claro->escuro; < 0 em cinza
# neutro (água/sombra — NDVI não interpretável)
CINZA_NDVI = hex_rgb("#b0aeaa")
STOPS_NDVI = stops_lab("#f1f5e6", "#14421f", [0.0, 0.15, 0.30, 0.45, 0.60, 0.75, 0.90])

# MNDWI: divergente com ponto médio neutro no limiar terra/água (0);
# lado terra em tons quentes (escuro->claro), lado água em azuis
# (claro->escuro)
STOPS_MNDWI_TERRA = stops_lab("#5a4632", "#f0eee8", [-1.0, -0.75, -0.50, -0.25, -0.02])
NEUTRO_MNDWI = (0.0, hex_rgb("#e8e8e6"))
STOPS_MNDWI_AGUA = stops_lab("#d8e6f2", "#0a3d6b", [0.02, 0.20, 0.40, 0.60, 0.80])


def rampa_entradas(nome):
    if nome == "ndvi":
        ent = [("-1.0", CINZA_NDVI), ("-0.0001", CINZA_NDVI)]
        ent += [(f"{v}", c) for v, c in STOPS_NDVI]
        ent.append(("1.0", STOPS_NDVI[-1][1]))
    else:
        ent = [(f"{v}", c) for v, c in STOPS_MNDWI_TERRA]
        ent.append((f"{NEUTRO_MNDWI[0]}", NEUTRO_MNDWI[1]))
        ent += [(f"{v}", c) for v, c in STOPS_MNDWI_AGUA]
        ent.append(("1.0", STOPS_MNDWI_AGUA[-1][1]))
    return ent


def escrever_rampa(nome, pasta):
    linhas = ["nv 0 0 0 0"] + [f"{v} {r} {g} {b} 255" for v, (r, g, b) in rampa_entradas(nome)]
    arq = pasta / f"_rampa_{nome}.txt"
    arq.write_text("\n".join(linhas) + "\n")
    return arq


def run(cmd):
    subprocess.run([str(c) for c in cmd], check=True, capture_output=True, text=True)


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(1 << 20):
            h.update(chunk)
    return h.hexdigest()


def realcar(cor_tif, ndvi_tif):
    """Cor verdadeira realçada: p2-p98 por banda + gama + saturação."""
    with rasterio.open(cor_tif) as src:
        rgb = src.read().astype(np.float32)  # (3, H, W), base linear 0.00-0.25
    with rasterio.open(ndvi_tif) as src:
        valido = src.read(1) != NODATA_F

    # Percentis sobre a distribuição CONJUNTA das três bandas e esticamento
    # único aplicado igualmente a R, G e B: preserva o matiz (um esticamento
    # independente por banda introduz dominante de cor)
    p2, p98 = np.percentile(rgb[:, valido], [PCT_INF, PCT_SUP])
    percentis = {"RGB conjunta": [round(float(p2), 1), round(float(p98), 1)]}
    x = np.clip((rgb - p2) / max(p98 - p2, 1e-6), 0, 1)
    saida = np.power(x, 1.0 / GAMA)

    arr = (np.transpose(saida, (1, 2, 0)) * 255).round().astype(np.uint8)
    arr[~valido] = 0
    img = Image.fromarray(arr)
    img = ImageEnhance.Color(img).enhance(SATURACAO)
    return img, percentis


def salvar_larguras(img, pasta, prefixo, larguras=LARGURAS):
    saidas = []
    for w in larguras:
        h = round(img.height * w / img.width)
        red = img.resize((w, h), Image.LANCZOS)
        for fmt, ext, kw in FORMATOS:
            destino = pasta / f"{prefixo}_{w}.{ext}"
            red.save(destino, fmt, **kw)
            saidas.append(destino)
    return saidas


def zoom_range(bounds_utm, crs):
    from rasterio.warp import transform_bounds

    o, s, l, n = transform_bounds(crs, "EPSG:4326", *bounds_utm, densify_pts=21)
    lat_c = (s + n) / 2
    z_max = max(math.ceil(math.log2(156543.03392 * math.cos(math.radians(lat_c)) / RES_M)), 1)
    return max(z_max - 6, 1), z_max


def regenerar_tiles(cena, bruto, proc, temp):
    """Regenera tiles de NDVI e MNDWI com as rampas revisadas."""
    with rasterio.open(bruto / f"{cena}_ndvi.tif") as src:
        z_min, z_max = zoom_range(src.bounds, src.crs)
    rgbs = {}
    for nome in ("ndvi", "mndwi"):
        rampa = escrever_rampa(nome, temp)
        rgb = temp / f"{nome}_rgb.tif"
        run(["gdaldem", "color-relief", "-alpha", bruto / f"{cena}_{nome}.tif", rampa, rgb,
             "-co", "COMPRESS=DEFLATE"])
        rgbs[nome] = rgb
        pasta = proc / "tiles" / nome
        if pasta.exists():
            shutil.rmtree(pasta)
        run(["gdal2tiles.py", "--xyz", "-z", f"{z_min}-{z_max}", "-w", "none",
             "--processes", "4", "--tiledriver", "WEBP", "--webp-quality", "75",
             "-r", "average", rgb, pasta])
    return rgbs


def camadas_alinhadas(cena, img_realce, rgbs, pasta):
    """Três camadas na mesma grade, redimensionadas identicamente a 1600 px."""
    pasta.mkdir(parents=True, exist_ok=True)
    w = 1600
    h = round(img_realce.height * w / img_realce.width)
    saidas = []
    camadas = {"cor": img_realce}
    for nome, rgb_tif in rgbs.items():
        with rasterio.open(rgb_tif) as src:
            arr = np.transpose(src.read((1, 2, 3)), (1, 2, 0)).astype(np.uint8)
        assert arr.shape[:2] == (img_realce.height, img_realce.width), "grades divergem"
        camadas[nome] = Image.fromarray(arr)
    for nome, img in camadas.items():
        red = img.resize((w, h), Image.LANCZOS)
        for fmt, ext, kw in FORMATOS:
            destino = pasta / f"{cena}_camada-{nome}_{w}.{ext}"
            red.save(destino, fmt, **kw)
            saidas.append(destino)
    return saidas


def _tabela_rampa_md():
    linhas = ["NDVI — sequencial de matiz único (verde), claro→escuro, passos",
              "interpolados em CIELAB (luminosidade monotônica); valores < 0 em",
              "cinza neutro `#b0aeaa` (não interpretáveis: água/sombra):", "",
              "| NDVI | cor |", "|---|---|", f"| < 0 | `{rgb_hex(CINZA_NDVI)}` (cinza neutro) |"]
    linhas += [f"| {v:.2f} | `{rgb_hex(c)}` |" for v, c in STOPS_NDVI]
    linhas += ["| ≥ 0.90 | idem 0.90 (saturado) |", "",
               "MNDWI — divergente com ponto médio neutro em 0 (limiar terra/água),",
               "cada lado com luminosidade monotônica (interpolação em CIELAB):", "",
               "| MNDWI | cor |", "|---|---|"]
    linhas += [f"| {v:.2f} | `{rgb_hex(c)}` |" for v, c in STOPS_MNDWI_TERRA]
    linhas += [f"| 0.00 | `{rgb_hex(NEUTRO_MNDWI[1])}` (neutro) |"]
    linhas += [f"| {v:.2f} | `{rgb_hex(c)}` |" for v, c in STOPS_MNDWI_AGUA]
    linhas += ["| ≥ 0.80 | idem 0.80 (saturado) |"]
    return "\n".join(linhas)


MARCA_INI = "<!-- realce-web:inicio -->"
MARCA_FIM = "<!-- realce-web:fim -->"


def _inserir_secao(arquivo, secao):
    texto = arquivo.read_text()
    if MARCA_INI in texto:
        texto = re.sub(re.escape(MARCA_INI) + r".*?" + re.escape(MARCA_FIM), secao,
                       texto, flags=re.S)
    else:
        rodape = "\n---\nGerado automaticamente"
        pos = texto.rfind(rodape)
        texto = texto[:pos] + "\n" + secao + "\n" + texto[pos:] if pos != -1 else texto + "\n" + secao + "\n"
    arquivo.write_text(texto)


def atualizar_ficha(proc, percentis):
    tab_pct = "\n".join(f"| {b} | {p[0]} | {p[1]} |" for b, p in percentis.items())
    secao = f"""{MARCA_INI}
## Realce aplicado nas imagens de exibição

As imagens `*_cor-verdadeira-realce_*` e as camadas alinhadas em
`web/camadas/` são versões de **EXIBIÇÃO**: o realce serve à leitura
visual na página e **não substitui o dado**. As versões originais — as
estáticas `*_cor-verdadeira_*` com esticamento linear declarado
(refletância 0.00–0.25) e os GeoTIFF/COG — permanecem intactas.

Parâmetros exatos desta cena, aplicados sobre a base linear 0.00–0.25 já
exportada (DN 8 bits), calculados apenas em pixels válidos:

| Distribuição | p{PCT_INF} (DN 8 bits) | p{PCT_SUP} (DN 8 bits) |
|---|---|---|
{tab_pct}

1. Esticamento linear único p{PCT_INF} → 0, p{PCT_SUP} → 255, aplicado
   igualmente a R, G e B (percentis da distribuição conjunta das três
   bandas, para preservar o matiz);
2. Correção gama suave: saída = entrada^(1/{GAMA});
3. Saturação ×{SATURACAO} (PIL `ImageEnhance.Color`).

As camadas alinhadas (`camada-cor`, `camada-ndvi`, `camada-mndwi`, 1600 px)
partilham a mesma grade UTM e as mesmas dimensões, para transição por
sobreposição (crossfade CSS) sem deslocamento.

### Rampas de cor das camadas NDVI e MNDWI (exibição)

{_tabela_rampa_md()}
{MARCA_FIM}"""
    _inserir_secao(proc / "FICHA.md", secao)


def atualizar_procedencia(proc, arquivos, agora):
    todos_tiles = sorted((proc / "tiles").rglob("*.webp"))
    agregado = hashlib.sha256("".join(sorted(sha256(t) for t in todos_tiles)).encode()).hexdigest()
    texto = (proc / "PROCEDENCIA-S2.md").read_text()
    texto = re.sub(r"\| Tiles XYZ \| \d+ arquivos WebP em `([^`]+)` \(hash agregado sha256 `[0-9a-f]+`\) \|",
                   f"| Tiles XYZ | {len(todos_tiles)} arquivos WebP em `\\1` (hash agregado sha256 `{agregado}`; "
                   f"NDVI/MNDWI regenerados com rampas revisadas em {agora}) |", texto)
    (proc / "PROCEDENCIA-S2.md").write_text(texto)
    linhas = "\n".join(f"| `{a.relative_to(REPO)}` | {a.stat().st_size / 1024:.0f} KB | `{sha256(a)}` |"
                       for a in arquivos)
    secao = f"""{MARCA_INI}
## Imagens de exibição (realce e camadas alinhadas)

Geradas por `scripts/sensoriamento/realce_web.py` em {agora}, a partir dos
GeoTIFF brutos locais (sem novo download). Os produtos originais não foram
modificados.

| Arquivo | Tamanho | SHA-256 |
|---|---|---|
{linhas}
{MARCA_FIM}"""
    _inserir_secao(proc / "PROCEDENCIA-S2.md", secao)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cena", required=True)
    args = ap.parse_args()
    cena = args.cena

    bruto = REPO / "dados" / "bruto" / "sensoriamento" / cena
    proc = REPO / "dados" / "processado" / "sensoriamento" / cena
    if not (bruto / f"{cena}_cor-verdadeira.tif").exists():
        sys.exit(f"GeoTIFFs brutos de '{cena}' não encontrados — rode o pipeline antes.")
    temp = proc / "_temp_realce"
    temp.mkdir(parents=True, exist_ok=True)

    img, percentis = realcar(bruto / f"{cena}_cor-verdadeira.tif", bruto / f"{cena}_ndvi.tif")
    novas = salvar_larguras(img, proc / "web", f"{cena}_cor-verdadeira-realce")
    rgbs = regenerar_tiles(cena, bruto, proc, temp)
    novas += camadas_alinhadas(cena, img, rgbs, proc / "web" / "camadas")
    shutil.rmtree(temp)

    agora = dt.datetime.now().astimezone().isoformat(timespec="seconds")
    atualizar_ficha(proc, percentis)
    atualizar_procedencia(proc, novas, agora)

    print(json.dumps({
        "cena": cena,
        "percentis_dn8": percentis,
        "gama": GAMA,
        "saturacao": SATURACAO,
        "arquivos": [{"arquivo": str(a.relative_to(REPO)), "kb": round(a.stat().st_size / 1024, 1)}
                     for a in novas],
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
