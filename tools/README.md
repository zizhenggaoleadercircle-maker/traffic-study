# tools

Development and maintenance scripts that are not part of the installable package (`src/traffic_study`).

Examples: one-off data fixes, codegen, or local automation. Add scripts here instead of the package when they are not meant for `pip install` distribution.

## North York Centre right-of-way map

`nyc_row_map/` overlays Table 3-15 (existing / planned ROW and excess pavement) from the *North York at the Centre* Phase 1 Background Report, Appendix A §3.4.1, on OpenStreetMap.

Public map: https://zizhenggaoleadercircle-maker.github.io/traffic-study/

Open [`nyc_row_map/index.html`](nyc_row_map/index.html) locally in a browser (needs network for OSM tiles). After changing the table, rebuild and copy the two published files into `docs/`:

```bash
python3 tools/nyc_row_map/build_row_map.py
cp tools/nyc_row_map/index.html docs/index.html
cp tools/nyc_row_map/table-3-15.geojson docs/table-3-15.geojson
```

The builder calls Overpass for street centrelines in North York Centre, or reuses `overpass-cache.json` if present. Lines are OSM centreline, not legal ROW polygons.
