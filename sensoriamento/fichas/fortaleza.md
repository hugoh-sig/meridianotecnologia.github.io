# FICHA — Sensoriamento remoto: fortaleza

## Fonte e período

| Campo | Valor |
|---|---|
| Sensor | Sentinel-2 MSI (missões S2A/S2B/S2C, ESA/Copernicus) |
| Nível de processamento | Level-2A, refletância de superfície (correção Sen2Cor) |
| Coleção exata (Earth Engine) | `COPERNICUS/S2_SR_HARMONIZED` |
| Período filtrado | 2025-10-01 a 2026-01-01 (data final exclusiva) |
| Justificativa do período | Estação seca de Fortaleza: aproximadamente julho a dezembro (a quadra chuvosa vai de fevereiro a maio). Em 2026-08-16, a janela de 3 meses mais recente contida integralmente na estação seca é out-dez/2025 (jul/2026 até hoje daria só ~1,5 mês). data_final é exclusiva. |
| Nuvem máxima por cena | 20% (metadado `CLOUDY_PIXEL_PERCENTAGE`) |
| Cenas usadas na composição | 23 |
| Datas de aquisição distintas | 19: 2025-10-04, 2025-10-06, 2025-10-09, 2025-10-14, 2025-10-16, 2025-10-24, 2025-10-29, 2025-11-03, 2025-11-05, 2025-11-08, 2025-11-13, 2025-11-15, 2025-11-18, 2025-11-23, 2025-11-28, 2025-12-03, 2025-12-08, 2025-12-13, 2025-12-28 |

## Área de interesse

bbox WGS84 (O, S, L, N): `[-38.71, -3.9, -38.35, -3.54]`

Memória de cálculo do bbox:

> bbox em WGS84 (EPSG:4326), ordem [oeste, sul, leste, norte].
> 
> Memória de cálculo (registrada também na FICHA.md):
> Centro de referência: centro de Fortaleza (Praça do Ferreira),
> aprox. lon -38.527, lat -3.728. A linha de costa corre a N/NE
> da cidade, então o quadrado é centrado em lon -38.53 e
> deslocado para que ~40% da metade norte seja oceano.
> Na latitude ~-3.7:
> 1 grau de latitude  ≈ 110.57 km  ->  40 km ≈ 0.362 graus
> 1 grau de longitude ≈ 111.32 x cos(3.7 graus) ≈ 111.08 km
> ->  40 km ≈ 0.360 graus
> Longitude: -38.71 a -38.35 (delta 0.36 graus ≈ 40.0 km),
> da Barra do Ceará (oeste) ao Porto das Dunas/Aquiraz (leste).
> Latitude: -3.90 a -3.54 (delta 0.36 graus ≈ 39.8 km),
> ~18 km de oceano ao norte da costa e ~22 km de continente.

## Máscara de nuvem e sombra

Banda `SCL` (Scene Classification, Sen2Cor). Pixels removidos nas classes:
3 (sombra de nuvem), 8 (nuvem, prob. média), 9 (nuvem, prob. alta), 10 (cirrus fino), 11 (neve/gelo). A composição usa apenas observações restantes.

## Composição e camadas

Composição por **MEDIANA** pixel a pixel das 23 cenas mascaradas.

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
| Pixels válidos após a máscara | 99.89% da grade exportada |
| Área de água (MNDWI > 0) | 860.23 km² |
| Área de continente | 731.68 km² |
| NDVI no continente — mín | -0.5267 |
| NDVI no continente — p25 | 0.148 |
| NDVI no continente — mediana | 0.2862 |
| NDVI no continente — p75 | 0.5069 |
| NDVI no continente — máx | 0.9318 |
| Linha de costa (medida a 10 m) | 156.1 km |

Método da linha de costa: contorno (marching squares) do maior corpo d'água
conectado no MNDWI > 0, medido na resolução de 10 m, excluindo segmentos que
correm pela borda da imagem; corpos d'água interiores não entram. O valor
depende da resolução de medida (efeito de escala em linhas costeiras).

#### Efeito da escala na linha de costa

A mesma linha, simplificada por Douglas-Peucker (tolerâncias aplicadas às
cadeias costeiras, já sem os trechos de borda), encolhe conforme a escala
de medição engrossa:

| Medida a 10 m (grade) | Simplificada 50 m | Simplificada 100 m | Simplificada 500 m |
|---|---|---|---|
| 156.1 km | 107.5 km | 91.8 km | 68.6 km |

### Datas de aquisição de todas as cenas

| Data (UTC) | Tile MGRS | Nuvem | ID da cena |
|---|---|---|---|
| 2025-10-04 13:03:28 | 24MWA | 0.99% | `20251004T130301_20251004T130300_T24MWA` |
| 2025-10-04 13:03:14 | 24MWB | 10.25% | `20251004T130301_20251004T130300_T24MWB` |
| 2025-10-06 13:03:14 | 24MWB | 12.26% | `20251006T130301_20251006T130300_T24MWB` |
| 2025-10-09 13:02:57 | 24MWB | 18.53% | `20251009T130249_20251009T130243_T24MWB` |
| 2025-10-14 13:03:10 | 24MWB | 12.83% | `20251014T130301_20251014T130257_T24MWB` |
| 2025-10-16 13:03:27 | 24MWA | 4.94% | `20251016T130301_20251016T130259_T24MWA` |
| 2025-10-16 13:03:12 | 24MWB | 9.27% | `20251016T130301_20251016T130259_T24MWB` |
| 2025-10-24 13:03:11 | 24MWB | 11.82% | `20251024T130301_20251024T130258_T24MWB` |
| 2025-10-29 13:03:12 | 24MWA | 15.06% | `20251029T130249_20251029T130244_T24MWA` |
| 2025-10-29 13:02:58 | 24MWB | 11.19% | `20251029T130249_20251029T130244_T24MWB` |
| 2025-11-03 13:03:11 | 24MWB | 7.06% | `20251103T130301_20251103T130258_T24MWB` |
| 2025-11-05 13:03:15 | 24MWB | 7.81% | `20251105T130301_20251105T130301_T24MWB` |
| 2025-11-08 13:02:55 | 24MWB | 13.91% | `20251108T130239_20251108T130241_T24MWB` |
| 2025-11-13 13:03:23 | 24MWA | 16.47% | `20251113T130301_20251113T130255_T24MWA` |
| 2025-11-13 13:03:08 | 24MWB | 7.3% | `20251113T130301_20251113T130255_T24MWB` |
| 2025-11-15 13:03:29 | 24MWA | 17.5% | `20251115T130301_20251115T130300_T24MWA` |
| 2025-11-18 13:02:54 | 24MWB | 14.09% | `20251118T130239_20251118T130240_T24MWB` |
| 2025-11-23 13:03:08 | 24MWB | 13.49% | `20251123T130301_20251123T130255_T24MWB` |
| 2025-11-28 13:02:51 | 24MWB | 12.73% | `20251128T130239_20251128T130238_T24MWB` |
| 2025-12-03 13:03:06 | 24MWB | 8.09% | `20251203T130251_20251203T130253_T24MWB` |
| 2025-12-08 13:02:56 | 24MWB | 2.93% | `20251208T130239_20251208T130242_T24MWB` |
| 2025-12-13 13:03:07 | 24MWB | 17.47% | `20251213T130251_20251213T130253_T24MWB` |
| 2025-12-28 13:02:58 | 24MWB | 16.01% | `20251228T130249_20251228T130244_T24MWB` |

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
* **A extensão da linha de costa depende da resolução de medição.**
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
| RGB conjunta | 38.0 | 255.0 |

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
Gerado automaticamente por `scripts/sensoriamento/pipeline.py` em 2026-08-16T16:20:06-03:00.
