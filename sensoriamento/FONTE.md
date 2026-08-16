# FONTE

Página gerada a partir do pipeline de sensoriamento remoto deste mesmo
repositório.

| Campo | Valor |
|---|---|
| Origem | `scripts/sensoriamento/pipeline.py` + `scripts/sensoriamento/realce_web.py`, configurados por `scripts/sensoriamento/cenas.yaml` |
| Commit do pipeline | `fbdd2fa` |
| Dados | Sentinel-2 L2A, coleção `COPERNICUS/S2_SR_HARMONIZED` (Google Earth Engine), earthengine-api 1.7.39 |
| Execuções das cenas | fortaleza e foz-sao-francisco e tres-marias e barragem-salinas, todas em 2026-08-16 |
| Imagens desta pasta | estáticas com realce de exibição (WebP e AVIF, 600/1000/1600 px) e camadas alinhadas NDVI/MNDWI a 1600 px |
| Fichas | `fichas/<cena>.md`, copiadas de `dados/processado/sensoriamento/<cena>/FICHA.md` |
| Publicado em | 2026-08-16 |

Os dados brutos e processados (GeoTIFF, COG, tiles), os hashes SHA-256 de
cada arquivo e os relatórios de execução ficam em
`dados/{bruto,processado}/sensoriamento/` na máquina de processamento;
arquivos acima de 50 MB não são versionados e têm hash registrado na
`PROCEDENCIA-S2.md` de cada cena.
