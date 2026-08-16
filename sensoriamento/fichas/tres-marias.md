# FICHA — Sensoriamento remoto: tres-marias

## Fonte e período

| Campo | Valor |
|---|---|
| Sensor | Sentinel-2 MSI (missões S2A/S2B/S2C, ESA/Copernicus) |
| Nível de processamento | Level-2A, refletância de superfície (correção Sen2Cor) |
| Coleção exata (Earth Engine) | `COPERNICUS/S2_SR_HARMONIZED` |
| Período filtrado | 2026-05-01 a 2026-08-01 (data final exclusiva) |
| Justificativa do período | Centro-oeste de MG: regime distinto do litoral do Nordeste — estação chuvosa de ~outubro a março e estação seca de ~maio a setembro. Em 2026-08-16, a janela de 3 meses mais recente completa e contida na estação seca é mai-jul/2026 (jun-ago ainda não fechou). data_final é exclusiva. |
| Nuvem máxima por cena | 20% (metadado `CLOUDY_PIXEL_PERCENTAGE`) |
| Cenas usadas na composição | 13 |
| Datas de aquisição distintas | 13: 2026-05-05, 2026-05-07, 2026-06-04, 2026-06-19, 2026-06-24, 2026-06-29, 2026-07-04, 2026-07-06, 2026-07-14, 2026-07-19, 2026-07-24, 2026-07-26, 2026-07-29 |

## Área de interesse

bbox WGS84 (O, S, L, N): `[-45.59, -18.57, -45.21, -18.21]`

Memória de cálculo do bbox:

> bbox em WGS84 (EPSG:4326), ordem [oeste, sul, leste, norte].
> 
> Memória de cálculo:
> Referência: barragem de Três Marias, alto São Francisco-MG,
> aprox. lon -45.264, lat -18.214. O reservatório se estende da
> barragem para S/SW por mais de 40 km, então um recorte de
> 40x40 km não cobre o reservatório inteiro: o quadrado é
> centrado no corpo d'água principal (porção norte-central),
> incluindo a barragem na borda norte e os braços dos rios
> Borrachudo e Indaiá a oeste; os braços ao sul (região de
> Morada Nova de Minas/Pompéu) ficam parcialmente fora.
> Na latitude ~-18.4:
> 1 grau de latitude  ≈ 110.60 km  ->  40 km ≈ 0.362 graus
> 1 grau de longitude ≈ 111.32 x cos(18.4 graus) ≈ 105.63 km
> ->  40 km ≈ 0.379 graus
> Longitude: -45.59 a -45.21 (delta 0.38 graus ≈ 40.1 km).
> Latitude: -18.57 a -18.21 (delta 0.36 graus ≈ 39.8 km).

## Máscara de nuvem e sombra

Banda `SCL` (Scene Classification, Sen2Cor). Pixels removidos nas classes:
3 (sombra de nuvem), 8 (nuvem, prob. média), 9 (nuvem, prob. alta), 10 (cirrus fino), 11 (neve/gelo). A composição usa apenas observações restantes.

## Composição e camadas

Composição por **MEDIANA** pixel a pixel das 13 cenas mascaradas.

| Camada | Fórmula (bandas nomeadas) | Observações |
|---|---|---|
| Cor verdadeira | R=`B4` (665 nm), G=`B3` (560 nm), B=`B2` (490 nm) | Esticamento linear declarado: refletância 0.00–0.25 (DN 0–2500) → 0–255 (8 bits) |
| NDVI | (`B8` − `B4`) / (`B8` + `B4`) | B8 = NIR 842 nm; float32, nodata -9999 |
| MNDWI | (`B3` − `B11`) / (`B3` + `B11`) | B11 = SWIR1 1610 nm, nativa 20 m, **reamostrada bilinearmente a 10 m**; float32, nodata -9999 |

## Projeções

| Etapa | CRS |
|---|---|
| bbox de entrada | WGS84 (EPSG:4326) |
| GeoTIFF/COG exportados | SIRGAS 2000 / UTM zone 23S (EPSG:31983), fuso derivado do centro do bbox (fuso 23), resolução 10 m |
| Tiles XYZ | Web Mercator (EPSG:3857), zooms 8–14 |

## Métricas

| Métrica | Valor |
|---|---|
| Pixels válidos após a máscara | 100.0% da grade exportada |
| Área de água (MNDWI > 0) | 451.16 km² |
| Área de continente | 1155.63 km² |
| NDVI no continente — mín | -0.5818 |
| NDVI no continente — p25 | 0.3853 |
| NDVI no continente — mediana | 0.5407 |
| NDVI no continente — p75 | 0.7399 |
| NDVI no continente — máx | 0.948 |
| Perímetro do corpo d'água principal (medido a 10 m) | 803.0 km |

Esta cena é um reservatório, não oceano: a métrica de "linha de costa" não
se aplica e foi substituída pelo **perímetro do corpo d'água principal**
(o reservatório de Três Marias). Método: contorno (marching squares) do
maior corpo d'água conectado no MNDWI > 0, medido na resolução de 10 m,
excluindo segmentos que correm pela borda da imagem (braços que saem do
recorte são truncados); corpos d'água interiores não entram. O valor
depende da resolução de medida (efeito de escala em perímetros de
feições naturais).

#### Efeito da escala no perímetro

O mesmo contorno, simplificado por Douglas-Peucker (tolerâncias aplicadas
às cadeias fora da borda), encolhe conforme a escala de medição engrossa:

| Medido a 10 m (grade) | Simplificado 50 m | Simplificado 100 m | Simplificado 500 m |
|---|---|---|---|
| 803.0 km | 720.6 km | 692.1 km | 559.6 km |

### Datas de aquisição de todas as cenas

| Data (UTC) | Tile MGRS | Nuvem | ID da cena |
|---|---|---|---|
| 2026-05-05 13:17:26 | 23KMV | 0.14% | `20260505T131241_20260505T131455_T23KMV` |
| 2026-05-07 13:17:38 | 23KMV | 3.8% | `20260507T131251_20260507T131539_T23KMV` |
| 2026-06-04 13:17:24 | 23KMV | 4.48% | `20260604T131241_20260604T131638_T23KMV` |
| 2026-06-19 13:17:24 | 23KMV | 0.47% | `20260619T131239_20260619T131449_T23KMV` |
| 2026-06-24 13:17:25 | 23KMV | 18.36% | `20260624T131241_20260624T131241_T23KMV` |
| 2026-06-29 13:17:23 | 23KMV | 0.21% | `20260629T131239_20260629T131615_T23KMV` |
| 2026-07-04 13:17:25 | 23KMV | 0.06% | `20260704T131241_20260704T131240_T23KMV` |
| 2026-07-06 13:17:41 | 23KMV | 11.25% | `20260706T131301_20260706T131506_T23KMV` |
| 2026-07-14 13:17:26 | 23KMV | 0.0% | `20260714T131241_20260714T131242_T23KMV` |
| 2026-07-19 13:17:26 | 23KMV | 1.61% | `20260719T131239_20260719T131502_T23KMV` |
| 2026-07-24 13:17:27 | 23KMV | 0.0% | `20260724T131241_20260724T131243_T23KMV` |
| 2026-07-26 13:17:43 | 23KMV | 0.0% | `20260726T131301_20260726T131258_T23KMV` |
| 2026-07-29 13:17:26 | 23KMV | 0.0% | `20260729T131239_20260729T131241_T23KMV` |

## LIMITAÇÕES

* **NDVI não é interpretável sobre água** — os valores sobre o oceano e
  corpos d'água não medem vegetação; use a máscara MNDWI antes de ler NDVI.
* **O nível do reservatório varia com a operação da usina**: a superfície
  de água mapeada corresponde à cota do período composto (mai–jul/2026) e
  não representa o nível médio nem a cota máxima do reservatório.
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
| RGB conjunta | 9.0 | 153.0 |

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
Gerado automaticamente por `scripts/sensoriamento/pipeline.py` em 2026-08-16T16:38:27-03:00.
