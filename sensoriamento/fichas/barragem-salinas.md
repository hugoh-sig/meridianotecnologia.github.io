# FICHA — Sensoriamento remoto: barragem-salinas

## Fonte e período

| Campo | Valor |
|---|---|
| Sensor | Sentinel-2 MSI (missões S2A/S2B/S2C, ESA/Copernicus) |
| Nível de processamento | Level-2A, refletância de superfície (correção Sen2Cor) |
| Coleção exata (Earth Engine) | `COPERNICUS/S2_SR_HARMONIZED` |
| Período filtrado | 2026-05-01 a 2026-08-01 (data final exclusiva) |
| Justificativa do período | Norte de Minas (semiárido): estação chuvosa de ~outubro a março e estação seca de ~abril a setembro. Em 2026-08-16, a janela de 3 meses mais recente completa e contida na estação seca é mai-jul/2026. data_final é exclusiva. |
| Nuvem máxima por cena | 20% (metadado `CLOUDY_PIXEL_PERCENTAGE`) |
| Cenas usadas na composição | 12 |
| Datas de aquisição distintas | 8: 2026-05-17, 2026-06-06, 2026-06-16, 2026-06-21, 2026-07-11, 2026-07-13, 2026-07-23, 2026-07-26 |

## Área de interesse

bbox WGS84 (O, S, L, N): `[-42.36, -16.174, -42.173, -15.993]`

Memória de cálculo do bbox:

> bbox em WGS84 (EPSG:4326), ordem [oeste, sul, leste, norte].
> 
> Memória de cálculo:
> Corpo d'água localizado ANTES de definir o bbox, via
> OpenStreetMap/Overpass API (consulta em 2026-08-16):
> way 298415728, nome "Barragem de Salinas", centroide
> (-16.085, -42.262), polígono de ~10.8 km2 entre
> lon -42.304..-42.232 e lat -16.115..-16.051, ~10 km ao
> norte da cidade de Salinas-MG. Nome oficial do barramento:
> Barragem do Rio Salinas (CEMIG, anos 1990, perenização do
> rio Salinas e abastecimento; fontes: salinas.mg.gov.br e
> minasgerais.com.br). Escolhido pelo usuário entre 4
> candidatos (era o maior e o único compatível com o
> "principal reservatório do município").
> Recorte de ~20x20 km (menor que o padrão de 40 km porque o
> reservatório é pequeno), centrado no centroide do polígono.
> Na latitude ~-16.08:
> 1 grau de latitude  ≈ 110.60 km  ->  20 km ≈ 0.181 graus
> 1 grau de longitude ≈ 111.32 x cos(16.08 graus) ≈ 106.98 km
> ->  20 km ≈ 0.187 graus
> Longitude: -42.360 a -42.173 (delta 0.187 ≈ 20.0 km).
> Latitude: -16.174 a -15.993 (delta 0.181 ≈ 20.0 km).
> Fuso UTM (verificação na divisa 23/24): a zona 24 começa em
> -42.000; a borda LESTE do bbox (-42.173) ainda está a oeste
> de -42.000, logo o bbox inteiro cai na zona 23. Centro
> lon -42.2665 -> fuso = floor((180-42.2665)/6)+1 = 23 ->
> SIRGAS 2000 / UTM 23S (EPSG:31983), o mesmo de Três Marias
> e diferente do 24S de Fortaleza/foz.

## Máscara de nuvem e sombra

Banda `SCL` (Scene Classification, Sen2Cor). Pixels removidos nas classes:
3 (sombra de nuvem), 8 (nuvem, prob. média), 9 (nuvem, prob. alta), 10 (cirrus fino), 11 (neve/gelo). A composição usa apenas observações restantes.

## Composição e camadas

Composição por **MEDIANA** pixel a pixel das 12 cenas mascaradas.

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
| Área de água (MNDWI > 0) | 8.38 km² |
| Área de continente | 404.11 km² |
| NDVI no continente — mín | -0.4844 |
| NDVI no continente — p25 | 0.3602 |
| NDVI no continente — mediana | 0.4723 |
| NDVI no continente — p75 | 0.644 |
| NDVI no continente — máx | 0.9246 |
| Perímetro do corpo d'água principal (medido a 10 m) | 65.1 km |

Esta cena é um reservatório, não oceano: a métrica de "linha de costa" não
se aplica e foi substituída pelo **perímetro do corpo d'água principal**
(o reservatório da Barragem do Rio Salinas, com 7.6 km² dos 8.38 km² de
água da cena). Método: contorno (marching squares) do maior corpo d'água
conectado no MNDWI > 0, medido na resolução de 10 m, excluindo segmentos
que correm pela borda da imagem; corpos d'água interiores não entram. O
valor depende da resolução de medida (efeito de escala em perímetros de
feições naturais).

#### Efeito da escala no perímetro

O mesmo contorno, simplificado por Douglas-Peucker (tolerâncias aplicadas
às cadeias fora da borda), encolhe conforme a escala de medição engrossa:

| Medido a 10 m (grade) | Simplificado 50 m | Simplificado 100 m | Simplificado 500 m |
|---|---|---|---|
| 65.1 km | 56.6 km | 53.3 km | 35.8 km |

### Datas de aquisição de todas as cenas

| Data (UTC) | Tile MGRS | Nuvem | ID da cena |
|---|---|---|---|
| 2026-05-17 13:06:33 | 23LQC | 1.11% | `20260517T130239_20260517T130241_T23LQC` |
| 2026-05-17 13:06:30 | 23LRC | 0.02% | `20260517T130239_20260517T130241_T23LRC` |
| 2026-06-06 13:06:34 | 23LQC | 15.82% | `20260606T130239_20260606T130242_T23LQC` |
| 2026-06-16 13:06:35 | 23LQC | 7.19% | `20260616T130249_20260616T130243_T23LQC` |
| 2026-06-16 13:06:31 | 23LRC | 3.79% | `20260616T130249_20260616T130243_T23LRC` |
| 2026-06-21 13:06:36 | 23LQC | 17.02% | `20260621T130251_20260621T130350_T23LQC` |
| 2026-06-21 13:06:33 | 23LRC | 0.83% | `20260621T130251_20260621T130350_T23LRC` |
| 2026-07-11 13:06:37 | 23LQC | 15.98% | `20260711T130251_20260711T130246_T23LQC` |
| 2026-07-11 13:06:34 | 23LRC | 0.53% | `20260711T130251_20260711T130246_T23LRC` |
| 2026-07-13 13:06:53 | 23LQC | 19.35% | `20260713T130301_20260713T130500_T23LQC` |
| 2026-07-23 13:06:54 | 23LQC | 16.74% | `20260723T130301_20260723T130302_T23LQC` |
| 2026-07-26 13:06:37 | 23LQC | 1.81% | `20260726T130249_20260726T130246_T23LQC` |

## LIMITAÇÕES

* **NDVI não é interpretável sobre água** — os valores sobre o oceano e
  corpos d'água não medem vegetação; use a máscara MNDWI antes de ler NDVI.
* **Reservatório em região semiárida: o nível varia muito entre anos e
  entre estações.** A superfície de água mapeada corresponde à cota do
  período composto (mai–jul/2026) e pode diferir bastante de outros
  períodos — a área medida (7.6 km² no corpo principal) fica abaixo do
  polígono de cota cheia do OpenStreetMap (~10.8 km²).
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
| RGB conjunta | 19.0 | 150.0 |

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
Gerado automaticamente por `scripts/sensoriamento/pipeline.py` em 2026-08-16T16:43:38-03:00.
