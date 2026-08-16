# Comparativo das cenas Sentinel-2

Cada coluna é uma composição **mediana** independente, com período próprio
— os valores **não são simultâneos** (composições de 2025 e de 2026) e cada
um corresponde à janela indicada na linha "Período da composição". Detalhes,
métodos e limitações de cada cena estão na respectiva `FICHA.md`.

| Métrica | Fortaleza | Foz do São Francisco | Três Marias | Barragem de Salinas |
|---|---|---|---|---|
| Período da composição | out–dez/2025 (2025-10-01 a 2026-01-01) | nov/2025–jan/2026 (2025-11-01 a 2026-02-01) | mai–jul/2026 (2026-05-01 a 2026-08-01) | mai–jul/2026 (2026-05-01 a 2026-08-01) |
| Nº de cenas na composição | 23 | 24 | 13 | 12 |
| Datas extremas de aquisição | 2025-10-04 a 2025-12-28 | 2025-11-02 a 2026-01-31 | 2026-05-05 a 2026-07-29 | 2026-05-17 a 2026-07-26 |
| Área de água (MNDWI > 0) | 860,2 km² | 1.121,5 km² | 451,2 km² | 8,4 km² |
| Área de continente | 731,7 km² | 499,0 km² | 1.155,6 km² | 404,1 km² |
| Pixels válidos após a máscara | 99,89% | 100,0% | 100,0% | 100,0% |
| NDVI no continente — mediana | 0,286 | 0,514 | 0,541 | 0,472 |
| NDVI no continente — p25–p75 | 0,148–0,507 | 0,338–0,687 | 0,385–0,740 | 0,360–0,644 |
| NDVI no continente — mín/máx | −0,527 / 0,932 | −0,786 / 0,946 | −0,582 / 0,948 | −0,484 / 0,925 |

Notas de leitura:

* As datas final de período são exclusivas; as justificativas de cada
  janela (estação seca de cada regime climático) estão nas FICHAs.
* A métrica de contorno d'água (perímetro do corpo d'água principal,
  medido a 10 m, com tolerâncias de simplificação) não é comparável entre
  cenas de naturezas distintas (costa oceânica, estuário, reservatórios) e
  por isso não entra nesta tabela — ver a FICHA de cada cena.
* Recortes: ~40×40 km nas três primeiras cenas; ~20×20 km na Barragem de
  Salinas (por isso as áreas absolutas não são diretamente comparáveis
  entre recortes de tamanhos diferentes).
