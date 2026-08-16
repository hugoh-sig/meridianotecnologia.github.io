# FICHA — Sensoriamento remoto: foz-sao-francisco

## Fonte e período

| Campo | Valor |
|---|---|
| Sensor | Sentinel-2 MSI (missões S2A/S2B/S2C, ESA/Copernicus) |
| Nível de processamento | Level-2A, refletância de superfície (correção Sen2Cor) |
| Coleção exata (Earth Engine) | `COPERNICUS/S2_SR_HARMONIZED` |
| Período filtrado | 2025-11-01 a 2026-02-01 (data final exclusiva) |
| Justificativa do período | Litoral AL/SE: a estação chuvosa vai de ~abril a agosto (chuvas de outono-inverno); a estação seca vai de ~outubro a março, com núcleo mais seco de novembro a janeiro. Em 2026-08-16, a janela de 3 meses mais recente contida no núcleo seco é nov/2025 a jan/2026. data_final é exclusiva. |
| Nuvem máxima por cena | 20% (metadado `CLOUDY_PIXEL_PERCENTAGE`) |
| Cenas usadas na composição | 24 |
| Datas de aquisição distintas | 17: 2025-11-02, 2025-11-07, 2025-11-12, 2025-11-17, 2025-11-19, 2025-12-02, 2025-12-09, 2025-12-12, 2025-12-17, 2025-12-19, 2025-12-27, 2025-12-29, 2026-01-01, 2026-01-04, 2026-01-06, 2026-01-16, 2026-01-31 |

## Área de interesse

bbox WGS84 (O, S, L, N): `[-36.58, -10.7, -36.215, -10.34]`

Memória de cálculo do bbox:

> bbox em WGS84 (EPSG:4326), ordem [oeste, sul, leste, norte].
> 
> Memória de cálculo:
> Referência: a foz do rio São Francisco, na divisa AL/SE,
> aprox. lon -36.395, lat -10.505 (entre Piaçabuçu-AL e
> Brejo Grande-SE). O oceano fica a SE da foz e o rio chega
> de NW, então o quadrado é centrado próximo à foz, com o
> quadrante SE sobre o oceano.
> Na latitude ~-10.5:
> 1 grau de latitude  ≈ 110.60 km  ->  40 km ≈ 0.362 graus
> 1 grau de longitude ≈ 111.32 x cos(10.5 graus) ≈ 109.46 km
> ->  40 km ≈ 0.365 graus
> Longitude: -36.58 a -36.215 (delta 0.365 graus ≈ 40.0 km),
> do baixo curso perto de Piaçabuçu até ~18 km mar adentro.
> Latitude: -10.70 a -10.34 (delta 0.36 graus ≈ 39.8 km),
> cobrindo delta, bancos de areia e a planície costeira das
> duas margens (Pontal do Peba-AL ao litoral de Pacatuba-SE).

## Máscara de nuvem e sombra

Banda `SCL` (Scene Classification, Sen2Cor). Pixels removidos nas classes:
3 (sombra de nuvem), 8 (nuvem, prob. média), 9 (nuvem, prob. alta), 10 (cirrus fino), 11 (neve/gelo). A composição usa apenas observações restantes.

## Composição e camadas

Composição por **MEDIANA** pixel a pixel das 24 cenas mascaradas.

| Camada | Fórmula (bandas nomeadas) | Observações |
|---|---|---|
| Cor verdadeira | R=`B4` (665 nm), G=`B3` (560 nm), B=`B2` (490 nm) | Esticamento linear declarado: refletância 0.00–0.25 (DN 0–2500) → 0–255 (8 bits) |
| NDVI | (`B8` − `B4`) / (`B8` + `B4`) | B8 = NIR 842 nm; float32, nodata -9999 |
| MNDWI | (`B3` − `B11`) / (`B3` + `B11`) | B11 = SWIR1 1610 nm, nativa 20 m, **reamostrada bilinearmente a 10 m**; float32, nodata -9999 |

## Projeções

| Etapa | CRS |
|---|---|
| bbox de entrada | WGS84 (EPSG:4326) |
| GeoTIFF/COG exportados | SIRGAS 2000 / UTM zone 24S (EPSG:31984), fuso derivado do centro do bbox (fuso 24), resolução 10 m |
| Tiles XYZ | Web Mercator (EPSG:3857), zooms 8–14 |

## Métricas

| Métrica | Valor |
|---|---|
| Pixels válidos após a máscara | 100.0% da grade exportada |
| Área de água (MNDWI > 0) | 1121.48 km² |
| Área de continente | 498.98 km² |
| NDVI no continente — mín | -0.7862 |
| NDVI no continente — p25 | 0.3377 |
| NDVI no continente — mediana | 0.514 |
| NDVI no continente — p75 | 0.6865 |
| NDVI no continente — máx | 0.9462 |
| Perímetro do corpo d'água principal (medido a 10 m) | 456.2 km |

Método do perímetro: contorno (marching squares) do maior corpo d'água
conectado no MNDWI > 0, medido na resolução de 10 m, excluindo segmentos que
correm pela borda da imagem; corpos d'água interiores não entram. O valor
depende da resolução de medida (efeito de escala em perímetros de feições
naturais).
Atenção: nesta cena o maior corpo d'água conectado inclui o rio São
Francisco e o estuário ligados ao mar, então o valor soma a costa oceânica
às margens do rio, dos bancos de areia e das ilhas do delta — não é apenas
a linha de praia. Por isso a métrica é rotulada como perímetro, não como
"linha de costa".

#### Efeito da escala no perímetro

O mesmo contorno, simplificado por Douglas-Peucker (tolerâncias aplicadas às
cadeias fora da borda), encolhe conforme a escala de medição engrossa:

| Medido a 10 m (grade) | Simplificado 50 m | Simplificado 100 m | Simplificado 500 m |
|---|---|---|---|
| 456.2 km | 348.3 km | 330.6 km | 273.4 km |

### Datas de aquisição de todas as cenas

| Data (UTC) | Tile MGRS | Nuvem | ID da cena |
|---|---|---|---|
| 2025-11-02 12:44:52 | 24LZP | 4.24% | `20251102T124249_20251102T124246_T24LZP` |
| 2025-11-07 12:45:09 | 24LYP | 10.78% | `20251107T124331_20251107T124329_T24LYP` |
| 2025-11-07 12:45:06 | 24LZP | 19.67% | `20251107T124331_20251107T124329_T24LZP` |
| 2025-11-12 12:44:54 | 24LYP | 18.91% | `20251112T124249_20251112T124245_T24LYP` |
| 2025-11-12 12:44:51 | 24LZP | 5.64% | `20251112T124249_20251112T124245_T24LZP` |
| 2025-11-17 12:45:04 | 24LZP | 1.58% | `20251117T124331_20251117T124326_T24LZP` |
| 2025-11-19 12:45:14 | 24LYP | 4.28% | `20251119T124331_20251119T124332_T24LYP` |
| 2025-11-19 12:45:11 | 24LZP | 13.78% | `20251119T124331_20251119T124332_T24LZP` |
| 2025-12-02 12:44:50 | 24LZP | 17.2% | `20251202T124249_20251202T124439_T24LZP` |
| 2025-12-09 12:45:12 | 24LYP | 16.83% | `20251209T124331_20251209T124330_T24LYP` |
| 2025-12-09 12:45:09 | 24LZP | 10.28% | `20251209T124331_20251209T124330_T24LZP` |
| 2025-12-12 12:44:55 | 24LYP | 15.07% | `20251212T124249_20251212T124247_T24LYP` |
| 2025-12-12 12:55:07 | 24LYP | 17.86% | `20251212T125321_20251212T125320_T24LYP` |
| 2025-12-12 12:44:52 | 24LZP | 9.58% | `20251212T124249_20251212T124247_T24LZP` |
| 2025-12-17 12:45:03 | 24LZP | 2.58% | `20251217T124301_20251217T124257_T24LZP` |
| 2025-12-19 12:45:14 | 24LYP | 16.88% | `20251219T124331_20251219T124332_T24LYP` |
| 2025-12-27 12:45:05 | 24LYP | 16.77% | `20251227T124301_20251227T124257_T24LYP` |
| 2025-12-27 12:45:02 | 24LZP | 5.74% | `20251227T124301_20251227T124257_T24LZP` |
| 2025-12-29 12:45:15 | 24LZP | 18.79% | `20251229T124341_20251229T124336_T24LZP` |
| 2026-01-01 12:44:54 | 24LZP | 13.68% | `20260101T124249_20260101T124248_T24LZP` |
| 2026-01-04 12:54:52 | 24LYP | 7.7% | `20260104T125309_20260104T125441_T24LYP` |
| 2026-01-06 12:45:00 | 24LZP | 15.36% | `20260106T124251_20260106T124254_T24LZP` |
| 2026-01-16 12:44:55 | 24LZP | 9.76% | `20260116T124251_20260116T124420_T24LZP` |
| 2026-01-31 12:44:52 | 24LYP | 8.53% | `20260131T124249_20260131T124324_T24LYP` |

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
* **O perímetro do corpo d'água depende da resolução de medição.**
  O valor foi obtido sobre a grade de 10 m e não é comparável a
  valores oficiais medidos em outra escala. Perímetros de feições
  naturais crescem conforme a resolução aumenta.

<!-- realce-web:inicio -->
## Realce aplicado nas imagens de exibição

As imagens `*_cor-verdadeira-realce_*` e as camadas alinhadas em
`web/camadas/` são versões de **EXIBIÇÃO**: o realce serve à leitura
visual na página e **não substitui o dado**. As versões originais — as
estáticas `*_cor-verdadeira_*` com esticamento linear declarado
(refletância 0.00–0.25) e os GeoTIFF/COG — permanecem intactas.

Parâmetros exatos desta cena, aplicados sobre a base linear 0.00–0.25 já
exportada (DN 8 bits), calculados apenas em pixels válidos:

| Distribuição | p2 (DN 8 bits) | p98 (DN 8 bits) |
|---|---|---|
| RGB conjunta | 19.0 | 252.0 |

1. Esticamento linear único p2 → 0, p98 → 255, aplicado
   igualmente a R, G e B (percentis da distribuição conjunta das três
   bandas, para preservar o matiz);
2. Correção gama suave: saída = entrada^(1/1.2);
3. Saturação ×1.15 (PIL `ImageEnhance.Color`).

As camadas alinhadas (`camada-cor`, `camada-ndvi`, `camada-mndwi`, 1600 px)
partilham a mesma grade UTM e as mesmas dimensões, para transição por
sobreposição (crossfade CSS) sem deslocamento.

### Rampas de cor das camadas NDVI e MNDWI (exibição)

NDVI — sequencial de matiz único (verde), claro→escuro, passos
interpolados em CIELAB (luminosidade monotônica); valores < 0 em
cinza neutro `#b0aeaa` (não interpretáveis: água/sombra):

| NDVI | cor |
|---|---|
| < 0 | `#b0aeaa` (cinza neutro) |
| 0.00 | `#f1f5e6` |
| 0.15 | `#cad5c1` |
| 0.30 | `#a3b69e` |
| 0.45 | `#7e977c` |
| 0.60 | `#5b7a5b` |
| 0.75 | `#385d3c` |
| 0.90 | `#14421f` |
| ≥ 0.90 | idem 0.90 (saturado) |

MNDWI — divergente com ponto médio neutro em 0 (limiar terra/água),
cada lado com luminosidade monotônica (interpolação em CIELAB):

| MNDWI | cor |
|---|---|
| -1.00 | `#5a4632` |
| -0.75 | `#7e6c5b` |
| -0.50 | `#a39688` |
| -0.25 | `#c9c1b7` |
| -0.02 | `#f0eee8` |
| 0.00 | `#e8e8e6` (neutro) |
| 0.02 | `#d8e6f2` |
| 0.20 | `#a7b8cf` |
| 0.40 | `#778cad` |
| 0.60 | `#48638b` |
| 0.80 | `#0a3d6b` |
| ≥ 0.80 | idem 0.80 (saturado) |
<!-- realce-web:fim -->

---
Gerado automaticamente por `scripts/sensoriamento/pipeline.py` em 2026-08-16T16:33:31-03:00.
