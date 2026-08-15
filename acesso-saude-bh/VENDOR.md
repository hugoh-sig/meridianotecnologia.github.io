# VENDOR — bibliotecas e fontes self-hosted

Baixados em 2026-08-14. Página não faz nenhuma chamada a unpkg nem ao Google Fonts.
Única dependência externa restante em runtime: o basemap raster do Carto
(`basemaps.cartocdn.com`), mantido externo por decisão nesta etapa.

| Arquivo | Versão | Origem | Licença |
|---|---|---|---|
| `vendor/maplibre-gl.js` (803.086 B) | MapLibre GL JS **4.7.1** | https://unpkg.com/maplibre-gl@4.7.1/dist/maplibre-gl.js | BSD-3-Clause |
| `vendor/maplibre-gl.css` (65.534 B) | MapLibre GL JS **4.7.1** | https://unpkg.com/maplibre-gl@4.7.1/dist/maplibre-gl.css | BSD-3-Clause |
| `vendor/pmtiles.js` (51.739 B) | PMTiles JS **3.2.1** | https://unpkg.com/pmtiles@3.2.1/dist/pmtiles.js | BSD-3-Clause |
| `fonts/inter-variable-latin.woff2` (48.432 B) | Inter (fonte variável, eixo de peso cobre 400/500/700), subset latin | Google Fonts (css2?family=Inter:wght@400;500;700), arquivo estático do fonts.gstatic.com | SIL Open Font License 1.1 |
| `fonts/inter-variable-latin-ext.woff2` (85.272 B) | Inter (variável), subset latin-ext | idem | SIL Open Font License 1.1 |

Nota: o Google Fonts serve a Inter como fonte variável; um único woff2 por
subset cobre os três pesos usados (400/500/700), declarado no `@font-face`
com `font-weight: 400 700` e `font-display: swap`. O subset latin (peso
principal do texto) tem `<link rel="preload">` no head.
