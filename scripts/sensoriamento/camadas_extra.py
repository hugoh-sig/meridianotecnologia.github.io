#!/usr/bin/env python3
"""Camadas espectrais adicionais das cenas Sentinel-2 já processadas.

Uso:
    python scripts/sensoriamento/camadas_extra.py --cena fortaleza

Acrescenta, por cena, três camadas às três já existentes (cor verdadeira,
NDVI, MNDWI), SEM refazer nem alterar nenhum produto existente:

  1. Falsa cor infravermelha — R=B8, G=B4, B=B3 (vegetação em vermelho,
     água escura). Bruto em uint16 (refletância DN); exibição com
     esticamento por percentis conjuntos p2-p98 + gama, como no realce
     atual (realce_web.py).
  2. Composição SWIR — R=B12, G=B8A, B=B4 (solo exposto, umidade,
     distinção de superfícies). Mesmo tratamento de exibição.
  3. NBR — (B8 - B12) / (B8 + B12), float32, rampa divergente definida
     na fonte única de rampas (realce_web.py).

A reexecução no Earth Engine serve APENAS para baixar as bandas que
faltam localmente: reconstrói a MESMA composição (mesma coleção, mesmo
período, mesma máscara SCL, mesma mediana) e ABORTA se o conjunto de
cenas divergir do registrado em relatorio_execucao.json — garantia de
alinhamento pixel a pixel com as camadas existentes. B8A e B12 (20 m)
são reamostradas bilinearmente à grade de 10 m, como já feito com B11.

Saídas por cena (mesmo tratamento das camadas existentes):
  - dados/bruto/sensoriamento/<cena>/<cena>_{falsa-cor,swir,nbr}.tif
  - COGs em dados/processado/sensoriamento/<cena>/
  - estáticas WebP e AVIF em 600/1000/1600 px em web/
  - versão 1600 px alinhada para crossfade em web/camadas/
  - FICHA.md e PROCEDENCIA-S2.md atualizados (seções idempotentes)
  - relatorio_camadas_extra.json

Autenticação: credenciais de usuário do earthengine-api já presentes na
máquina (fora do repositório). Nenhuma credencial é lida ou gravada aqui.
"""

import argparse
import datetime as dt
import json
import re
import shutil
import sys
import time
from pathlib import Path

import numpy as np
import rasterio
import yaml
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))

from pipeline import (  # noqa: E402
    NODATA_F, REPO, atualizar_gitignore, baixar_camada, gerar_cog, grade_utm,
    listar_cenas, log, montar_colecao, run, sha256, utm_sirgas2000_epsg,
)
from realce_web import (  # noqa: E402
    GAMA, NEUTRO_NBR, PCT_INF, PCT_SUP, STOPS_NBR_NEG, STOPS_NBR_POS,
    escrever_rampa, rgb_hex, salvar_larguras,
)

MARCA_INI = "<!-- camadas-extra:inicio -->"
MARCA_FIM = "<!-- camadas-extra:fim -->"

# Bandas por composição RGB (ordem R, G, B) e comprimentos de onda nominais
COMPOSICOES = {
    "falsa-cor": ["B8", "B4", "B3"],
    "swir": ["B12", "B8A", "B4"],
}


def compor_mediana_extra(ee, col, scl_classes):
    """Mesma máscara SCL, mesma reamostragem bilinear e mesma MEDIANA de
    pipeline.compor_mediana — apenas com o conjunto de bandas das camadas
    novas. A mediana é por banda e por pixel, então as bandas partilhadas
    (B3, B4, B8) reproduzem exatamente a composição existente."""
    def preparar(img):
        scl = img.select("SCL")
        ruim = ee.Image(0)
        for c in scl_classes:
            ruim = ruim.Or(scl.eq(c))
        img = img.updateMask(ruim.Not())
        # bilinear: neutro nas bandas de 10 m; interpola B8A e B12 (20 m)
        # ao serem lidas na grade de 10 m, como já feito com B11
        return img.select(["B3", "B4", "B8", "B8A", "B12"]).resample("bilinear")

    return col.map(preparar).median()


def conferir_mesmas_cenas(cenas, proc):
    """Aborta se o conjunto de cenas divergir da execução original."""
    rel = json.loads((proc / "relatorio_execucao.json").read_text())
    antes = {c["id"] for c in rel["cenas_s2"]}
    agora = {c["id"] for c in cenas}
    if antes != agora:
        sys.exit(
            "Conjunto de cenas divergiu da execução original — a composição não "
            f"seria idêntica. Faltando: {sorted(antes - agora)}; novas: {sorted(agora - antes)}"
        )
    log(f"  conjunto de cenas confere com relatorio_execucao.json ({len(agora)} cenas)")


def exibicao_percentis(tif, valido):
    """RGB de exibição: esticamento por percentis CONJUNTOS p2-p98 das três
    bandas + gama, como no realce atual (sem esticamento por banda, para
    preservar o matiz da composição)."""
    with rasterio.open(tif) as src:
        dados = src.read().astype(np.float32)
    p2, p98 = np.percentile(dados[:, valido], [PCT_INF, PCT_SUP])
    x = np.clip((dados - p2) / max(p98 - p2, 1e-6), 0, 1)
    saida = np.power(x, 1.0 / GAMA)
    arr = (np.transpose(saida, (1, 2, 0)) * 255).round().astype(np.uint8)
    arr[~valido] = 0
    return Image.fromarray(arr), (round(float(p2), 1), round(float(p98), 1))


def nbr_exibicao(tif_nbr, temp):
    """RGB do NBR pela rampa divergente da fonte única (realce_web.py)."""
    rampa = escrever_rampa("nbr", temp)
    rgb = temp / "nbr_rgb.tif"
    run(["gdaldem", "color-relief", "-alpha", tif_nbr, rampa, rgb, "-co", "COMPRESS=DEFLATE"])
    with rasterio.open(rgb) as src:
        arr = np.transpose(src.read((1, 2, 3)), (1, 2, 0)).astype(np.uint8)
    return Image.fromarray(arr)


def conferir_alinhamento(cena, bruto):
    """As seis camadas precisam ter exatamente a mesma grade."""
    grades = {}
    for camada in ("cor-verdadeira", "ndvi", "mndwi", "falsa-cor", "swir", "nbr"):
        with rasterio.open(bruto / f"{cena}_{camada}.tif") as src:
            grades[camada] = (src.width, src.height, str(src.crs), tuple(src.transform[:6]))
    ref = grades["cor-verdadeira"]
    divergentes = {c: g for c, g in grades.items() if g != ref}
    if divergentes:
        sys.exit(f"Grades divergentes em {cena}: {divergentes}")
    log(f"  alinhamento OK: 6 camadas em {ref[0]}x{ref[1]} px, {ref[2]}, mesma transformação")
    return ref


def _tabela_rampa_nbr():
    linhas = ["NBR — divergente com ponto médio neutro em 0, lado negativo",
              "(solo exposto/área queimada/sem vegetação) em tons queimados e lado",
              "positivo (vegetação com dossel/umidade) em verdes, cada lado com",
              "luminosidade monotônica (interpolação em CIELAB):", "",
              "| NBR | cor |", "|---|---|"]
    linhas += [f"| {v:.2f} | `{rgb_hex(c)}` |" for v, c in STOPS_NBR_NEG]
    linhas += [f"| 0.00 | `{rgb_hex(NEUTRO_NBR[1])}` (neutro) |"]
    linhas += [f"| {v:.2f} | `{rgb_hex(c)}` |" for v, c in STOPS_NBR_POS]
    linhas += ["| ≥ 0.80 | idem 0.80 (saturado) |"]
    return "\n".join(linhas)


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
    tab_pct = "\n".join(f"| {nome} | {p[0]} | {p[1]} |" for nome, p in percentis.items())
    secao = f"""{MARCA_INI}
## Camadas espectrais adicionais

Geradas por `scripts/sensoriamento/camadas_extra.py` sobre a MESMA
composição mediana (mesma coleção, mesmo período, mesma máscara SCL,
mesmo conjunto de cenas — conferido contra `relatorio_execucao.json`) e
na mesma grade UTM de 10 m das camadas originais, alinhadas pixel a
pixel. B8A e B12 (nativas 20 m) foram reamostradas bilinearmente a 10 m,
como já feito com B11 no MNDWI.

| Camada | Fórmula (bandas nomeadas) | Observações |
|---|---|---|
| Falsa cor infravermelha | R=`B8` (NIR 842 nm), G=`B4` (665 nm), B=`B3` (560 nm) | Bruto em uint16 (refletância ×10⁴); vegetação em vermelho, água escura |
| Composição SWIR | R=`B12` (SWIR2 2190 nm), G=`B8A` (NIR estreito 865 nm), B=`B4` (665 nm) | Bruto em uint16 (refletância ×10⁴); B12 e B8A nativas 20 m, **reamostradas bilinearmente a 10 m**; realça solo exposto e umidade |
| NBR | (`B8` − `B12`) / (`B8` + `B12`) | B8 = NIR 842 nm, B12 = SWIR2 2190 nm (bilinear a 10 m); float32, nodata {NODATA_F:.0f} |

### Realce das composições de exibição

As estáticas `*_falsa-cor_*` e `*_swir_*` (WebP/AVIF, 600/1000/1600 px)
e as camadas alinhadas em `web/camadas/` são versões de **EXIBIÇÃO**; os
GeoTIFF brutos uint16 e os COGs permanecem em refletância. Realce igual
ao da cor verdadeira realçada: esticamento linear único p{PCT_INF} → 0,
p{PCT_SUP} → 255 sobre a distribuição CONJUNTA das três bandas (preserva
o matiz) seguido de gama (saída = entrada^(1/{GAMA})), calculado apenas
em pixels válidos. Percentis desta cena, em DN de refletância (×10⁴):

| Composição | p{PCT_INF} (DN) | p{PCT_SUP} (DN) |
|---|---|---|
{tab_pct}

### Rampa de cor da camada NBR (exibição)

{_tabela_rampa_nbr()}

### Limitações das camadas adicionais

* **NBR é um índice de severidade de queima por diferença temporal**: em
  uma única composição ele separa vegetação (valores altos) de solo
  exposto/área queimada (valores baixos), mas a atribuição a fogo exige
  comparação pré/pós-evento (dNBR), que esta camada isolada não fornece.
* **NBR não é interpretável sobre água** — como o NDVI, os valores sobre
  corpos d'água não medem vegetação nem queima.
* As composições partilham as limitações da mediana já documentadas
  (não representam uma data específica; máscara SCL imperfeita).
{MARCA_FIM}"""
    _inserir_secao(proc / "FICHA.md", secao)


def atualizar_procedencia(proc, arquivos, agora):
    linhas = "\n".join(f"| `{a.relative_to(REPO)}` | {a.stat().st_size / 1e6:.1f} MB | `{sha256(a)}` |"
                       if a.stat().st_size >= 1e6 else
                       f"| `{a.relative_to(REPO)}` | {a.stat().st_size / 1024:.0f} KB | `{sha256(a)}` |"
                       for a in arquivos)
    secao = f"""{MARCA_INI}
## Camadas espectrais adicionais (falsa cor, SWIR, NBR)

Geradas por `scripts/sensoriamento/camadas_extra.py` em {agora}. A
reexecução no Earth Engine baixou apenas as bandas que faltavam
localmente, reconstruindo a mesma composição mediana (conjunto de cenas
conferido contra `relatorio_execucao.json`). Nenhum produto existente
foi modificado.

| Arquivo | Tamanho | SHA-256 |
|---|---|---|
{linhas}
{MARCA_FIM}"""
    _inserir_secao(proc / "PROCEDENCIA-S2.md", secao)


def main():
    t0 = time.monotonic()
    ap = argparse.ArgumentParser(description="Camadas espectrais adicionais (falsa cor, SWIR, NBR)")
    ap.add_argument("--cena", required=True, help="nome da cena em cenas.yaml")
    ap.add_argument("--config", default=str(Path(__file__).parent / "cenas.yaml"))
    args = ap.parse_args()

    cfg = yaml.safe_load(Path(args.config).read_text())
    if args.cena not in cfg["cenas"]:
        sys.exit(f"Cena '{args.cena}' não encontrada em {args.config}")
    cena_cfg = cfg["cenas"][args.cena]
    cena = args.cena

    bruto = REPO / "dados" / "bruto" / "sensoriamento" / cena
    proc = REPO / "dados" / "processado" / "sensoriamento" / cena
    if not (proc / "relatorio_execucao.json").exists():
        sys.exit(f"Cena '{cena}' ainda não processada pelo pipeline — rode-o antes.")

    import ee

    log(f"Inicializando Earth Engine (projeto {cfg['projeto_ee']})…")
    ee.Initialize(project=cfg["projeto_ee"])

    bbox = cena_cfg["bbox"]
    fuso, epsg, crs_nome = utm_sirgas2000_epsg(bbox)
    x0, y0, largura, altura = grade_utm(bbox, epsg)
    log(f"CRS de exportação: {crs_nome} (EPSG:{epsg}); grade {largura}x{altura} px a 10 m")

    regiao, col = montar_colecao(ee, cfg, cena_cfg)
    cenas = listar_cenas(col)
    conferir_mesmas_cenas(cenas, proc)

    comp = compor_mediana_extra(ee, col, cfg["scl_mascara"])

    imagens = {
        nome: comp.select(bandas).round().toUint16().unmask(0)
        for nome, bandas in COMPOSICOES.items()
    }
    nbr = comp.normalizedDifference(["B8", "B12"]).rename("NBR").unmask(NODATA_F).toFloat()

    tifs = {nome: bruto / f"{cena}_{nome}.tif" for nome in (*COMPOSICOES, "nbr")}
    for nome, bandas in COMPOSICOES.items():
        log(f"Baixando {nome} ({', '.join(bandas)})…")
        baixar_camada(ee, imagens[nome], bandas, epsg, x0, y0, largura, altura,
                      tifs[nome], "uint16", 0)
    log("Baixando NBR…")
    baixar_camada(ee, nbr, ["NBR"], epsg, x0, y0, largura, altura, tifs["nbr"], "float32", NODATA_F)

    log("Conferindo alinhamento das 6 camadas…")
    conferir_alinhamento(cena, bruto)

    log("Gerando COGs…")
    cogs = {}
    for nome in COMPOSICOES:
        cogs[nome] = proc / f"{cena}_{nome}_cog.tif"
        # uint16: DEFLATE com predictor inteiro (JPEG exigiria 8 bits)
        run(["gdal_translate", "-of", "COG", "-co", "OVERVIEW_RESAMPLING=AVERAGE",
             "-co", "BLOCKSIZE=512", "-co", "COMPRESS=DEFLATE", "-co", "PREDICTOR=2",
             tifs[nome], cogs[nome]])
    cogs["nbr"] = proc / f"{cena}_nbr_cog.tif"
    gerar_cog(tifs["nbr"], cogs["nbr"], fotografico=False)

    log("Gerando estáticas WebP/AVIF e camadas alinhadas…")
    temp = proc / "_temp_extra"
    temp.mkdir(parents=True, exist_ok=True)
    with rasterio.open(tifs["nbr"]) as src:
        valido = src.read(1) != NODATA_F

    percentis, exibicoes = {}, {}
    for nome in COMPOSICOES:
        exibicoes[nome], percentis[nome] = exibicao_percentis(tifs[nome], valido)
    exibicoes["nbr"] = nbr_exibicao(tifs["nbr"], temp)

    estaticas = []
    for nome, img in exibicoes.items():
        estaticas += salvar_larguras(img, proc / "web", f"{cena}_{nome}")
    w = 1600
    camadas = []
    for nome, img in exibicoes.items():
        h = round(img.height * w / img.width)
        red = img.resize((w, h), Image.LANCZOS)
        for fmt, ext, kw in (("WEBP", "webp", {"quality": 80, "method": 6}),
                             ("AVIF", "avif", {"quality": 55})):
            destino = proc / "web" / "camadas" / f"{cena}_camada-{nome}_{w}.{ext}"
            destino.parent.mkdir(parents=True, exist_ok=True)
            red.save(destino, fmt, **kw)
            camadas.append(destino)
    shutil.rmtree(temp)

    novos = [*tifs.values(), *cogs.values(), *estaticas, *camadas]
    grandes = atualizar_gitignore(novos)

    log("Atualizando FICHA.md e PROCEDENCIA-S2.md…")
    agora = dt.datetime.now().astimezone().isoformat(timespec="seconds")
    atualizar_ficha(proc, percentis)
    atualizar_procedencia(proc, novos, agora)

    relatorio = {
        "cena": cena,
        "percentis_dn_refletancia": percentis,
        "gama": GAMA,
        "arquivos": [{"arquivo": str(a.relative_to(REPO)), "kb": round(a.stat().st_size / 1024, 1)}
                     for a in novos],
        "gitignore_50mb": grandes,
        "tempo_execucao_s": round(time.monotonic() - t0, 1),
        "executado_em": agora,
    }
    (proc / "relatorio_camadas_extra.json").write_text(json.dumps(relatorio, ensure_ascii=False, indent=2))
    total_mb = sum(a.stat().st_size for a in novos) / 1e6
    log(f"Concluído: {len(novos)} arquivos novos ({total_mb:.1f} MB) em {relatorio['tempo_execucao_s']} s.")


if __name__ == "__main__":
    main()
