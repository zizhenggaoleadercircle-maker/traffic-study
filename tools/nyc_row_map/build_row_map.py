#!/usr/bin/env python3
"""Build an interactive OpenStreetMap overlay for Mobility Review §3.4.1.

Reads Table 3-15 (existing / planned ROW and pavement widths) from the
North York at the Centre Phase 1 Background Report, matches each corridor
to OpenStreetMap ways via Overpass, and writes:

  tools/nyc_row_map/table-3-15.geojson
  tools/nyc_row_map/index.html
"""

from __future__ import annotations

import json
import math
import urllib.parse
import urllib.request
from collections import defaultdict, deque
from pathlib import Path

HERE = Path(__file__).resolve().parent
OVERPASS_URL = "https://overpass-api.de/api/interpreter"
BBOX = (43.748, -79.430, 43.786, -79.395)  # s, w, n, e — North York Centre
USER_AGENT = "traffic-study-nyc-row-map/0.1"

STREET_NAMES = [
    "Yonge Street",
    "Bishop Avenue",
    "Church Avenue",
    "Beecroft Road",
    "Park Home Avenue",
    "North York Boulevard",
    "Elmhurst Avenue",
    "Poyntz Avenue",
    "Doris Avenue",
    "Greenfield Avenue",
    "Avondale Avenue",
    "Finch Avenue West",
    "Finch Avenue East",
    "Sheppard Avenue East",
    "Sheppard Avenue West",
    "Maxome Avenue",
    "Norton Avenue",
    "Hollywood Avenue",
    "Bonnington Place",
    "Ellerslie Avenue",
    "Tradewind Avenue",
]

# Table 3-15, Appendix A Mobility Review pp. 80–81.
# existing_row_m / planned_row_m are legal right-of-way, not curb-to-curb.
SEGMENTS = [
    {
        "id": "bishop-yonge-maxome",
        "label": "Bishop Avenue (Yonge Street to Maxome Avenue)",
        "street": "Bishop Avenue",
        "from_street": "Yonge Street",
        "to_street": "Maxome Avenue",
        "existing_row_m": 23,
        "planned_row_m": 23,
        "travel_width_m": 14.2,
        "travel_width_varies": True,
        "lanes": 4,
        "typical_width_m": 12.6,
        "excess_pavement_m": 1.6,
    },
    {
        "id": "church-yonge-doris",
        "label": "Church Avenue (Yonge Street to Doris Avenue)",
        "street": "Church Avenue",
        "from_street": "Yonge Street",
        "to_street": "Doris Avenue",
        "existing_row_m": 30,
        "planned_row_m": 30,
        "travel_width_m": 12.7,
        "travel_width_varies": False,
        "lanes": 4,
        "typical_width_m": 12.6,
        "excess_pavement_m": 0.1,
    },
    {
        "id": "beecroft-ellerslie-parkhome",
        "label": "Beecroft Road (Ellerslie Avenue to Park Home Avenue)",
        "street": "Beecroft Road",
        "from_street": "Ellerslie Avenue",
        "to_street": "Park Home Avenue",
        "existing_row_m": 30,
        "planned_row_m": 30,
        "travel_width_m": 16.9,
        "travel_width_varies": True,
        "lanes": 5,
        "typical_width_m": 15.6,
        "excess_pavement_m": 1.3,
    },
    {
        "id": "beecroft-parkhome-n-elmhurst",
        "label": "Beecroft Road (Park Home Avenue to 200 m north of Elmhurst Avenue)",
        "street": "Beecroft Road",
        "from_street": "Park Home Avenue",
        "to_offset": {"along": "Elmhurst Avenue", "direction": "north", "meters": 200},
        "existing_row_m": 27,
        "planned_row_m": 27,
        "travel_width_m": 16.2,
        "travel_width_varies": True,
        "lanes": 5,
        "typical_width_m": 15.6,
        "excess_pavement_m": 0.6,
    },
    {
        "id": "beecroft-n-elmhurst-sheppard",
        "label": "Beecroft Road (200 m north of Elmhurst Avenue to Sheppard Avenue West)",
        "street": "Beecroft Road",
        "from_offset": {"along": "Elmhurst Avenue", "direction": "north", "meters": 200},
        "to_street": "Sheppard Avenue West",
        "existing_row_m": 36,
        "planned_row_m": 36,
        "travel_width_m": 16.5,
        "travel_width_varies": True,
        "lanes": 5,
        "typical_width_m": 15.6,
        "excess_pavement_m": 0.9,
    },
    {
        "id": "beecroft-sheppard-poyntz",
        "label": "Beecroft Road (Sheppard Avenue West to Poyntz Avenue)",
        "street": "Beecroft Road",
        "from_street": "Sheppard Avenue West",
        "to_street": "Poyntz Avenue",
        "existing_row_m": 27,
        "planned_row_m": 27,
        "travel_width_m": 13.3,
        "travel_width_varies": True,
        "lanes": 4,
        "typical_width_m": 12.6,
        "excess_pavement_m": 0.7,
    },
    {
        "id": "parkhome-beecroft-yonge",
        "label": "Park Home Avenue (Beecroft Road to Yonge Street)",
        "street": "Park Home Avenue",
        "from_street": "Beecroft Road",
        "to_street": "Yonge Street",
        "existing_row_m": 27,
        "planned_row_m": 27,
        "travel_width_m": 18.1,
        "travel_width_varies": False,
        "lanes": 5,
        "typical_width_m": 15.6,
        "excess_pavement_m": 2.5,
    },
    {
        "id": "nyb-beecroft-yonge",
        "label": "North York Boulevard (Beecroft Road to Yonge Street)",
        "street": "North York Boulevard",
        "from_street": "Beecroft Road",
        "to_street": "Yonge Street",
        "existing_row_m": 30,
        "planned_row_m": 30,
        "travel_width_m": 12.6,
        "travel_width_varies": True,
        "lanes": 4,
        "typical_width_m": 12.6,
        "excess_pavement_m": 0.0,
    },
    {
        "id": "elmhurst-beecroft-yonge",
        "label": "Elmhurst Avenue (Beecroft Road to Yonge Street)",
        "street": "Elmhurst Avenue",
        "from_street": "Beecroft Road",
        "to_street": "Yonge Street",
        "existing_row_m": 27,
        "planned_row_m": 27,
        "travel_width_m": 12.9,
        "travel_width_varies": False,
        "lanes": 4,
        "typical_width_m": 12.6,
        "excess_pavement_m": 0.3,
    },
    {
        "id": "poyntz-beecroft-yonge",
        "label": "Poyntz Avenue (Beecroft Road to Yonge Street)",
        "street": "Poyntz Avenue",
        "from_street": "Beecroft Road",
        "to_street": "Yonge Street",
        "existing_row_m": 30,
        "planned_row_m": 30,
        "travel_width_m": 14.3,
        "travel_width_varies": False,
        "lanes": 4,
        "typical_width_m": 12.6,
        "excess_pavement_m": 1.7,
    },
    {
        "id": "doris-norton-hollywood",
        "label": "Doris Avenue (Norton Avenue to Hollywood Avenue)",
        "street": "Doris Avenue",
        "from_street": "Norton Avenue",
        "to_street": "Hollywood Avenue",
        "existing_row_m": 36,
        "planned_row_m": 36,
        "travel_width_m": 13.2,
        "travel_width_varies": False,
        "lanes": 4,
        "typical_width_m": 12.6,
        "excess_pavement_m": 0.6,
    },
    {
        "id": "doris-hollywood-sheppard",
        "label": "Doris Avenue (Hollywood Avenue to Sheppard Avenue East)",
        "street": "Doris Avenue",
        "from_street": "Hollywood Avenue",
        "to_street": "Sheppard Avenue East",
        "existing_row_m": 27,
        "planned_row_m": 27,
        "travel_width_m": 13.2,
        "travel_width_varies": False,
        "lanes": 4,
        "typical_width_m": 12.6,
        "excess_pavement_m": 0.6,
    },
    {
        "id": "greenfield-yonge-doris",
        "label": "Greenfield Avenue (Yonge Street to Doris Avenue)",
        "street": "Greenfield Avenue",
        "from_street": "Yonge Street",
        "to_street": "Doris Avenue",
        "existing_row_m": 27,
        "planned_row_m": 27,
        "travel_width_m": 12.8,
        "travel_width_varies": False,
        "lanes": 4,
        "typical_width_m": 12.6,
        "excess_pavement_m": 0.2,
    },
    {
        "id": "avondale-yonge-service",
        "label": "Avondale Avenue (Yonge Street to South Downtown Service Road)",
        "street": "Avondale Avenue",
        "from_street": "Yonge Street",
        "to_street": "Tradewind Avenue",
        "to_note": "Mapped to Tradewind Avenue; the report names South Downtown Service Road.",
        "existing_row_m": 27,
        "planned_row_m": 27,
        "travel_width_m": 13.8,
        "travel_width_varies": False,
        "lanes": 4,
        "typical_width_m": 12.6,
        "excess_pavement_m": 1.2,
    },
    {
        "id": "finch-west-of-yonge",
        "label": "Finch Avenue West (west of Yonge Street)",
        "street": "Finch Avenue West",
        "from_street": "Yonge Street",
        "direction": "west",
        "existing_row_m": 36,
        "planned_row_m": 36,
        "travel_width_m": 17.5,
        "travel_width_varies": True,
        "lanes": 5,
        "typical_width_m": 15.6,
        "excess_pavement_m": 1.9,
    },
    {
        "id": "finch-east-of-yonge",
        "label": "Finch Avenue East (east of Yonge Street)",
        "street": "Finch Avenue East",
        "from_street": "Yonge Street",
        "direction": "east",
        "existing_row_m": 36,
        "planned_row_m": 36,
        "travel_width_m": 17.2,
        "travel_width_varies": True,
        "lanes": 5,
        "typical_width_m": 15.6,
        "excess_pavement_m": 1.6,
    },
    {
        "id": "sheppard-east-yonge-bonnington",
        "label": "Sheppard Avenue East (Yonge Street to Bonnington Place)",
        "street": "Sheppard Avenue East",
        "from_street": "Yonge Street",
        "to_street": "Bonnington Place",
        "existing_row_m": 36,
        "planned_row_m": 36,
        "travel_width_m": 25.6,
        "travel_width_varies": True,
        "lanes": 7,
        "typical_width_m": 21.6,
        "excess_pavement_m": 4.0,
    },
    {
        "id": "sheppard-east-of-bonnington",
        "label": "Sheppard Avenue East (east of Bonnington Place)",
        "street": "Sheppard Avenue East",
        "from_street": "Bonnington Place",
        "direction": "east",
        "existing_row_m": 36,
        "planned_row_m": 36,
        "travel_width_m": 17.6,
        "travel_width_varies": True,
        "lanes": 5,
        "typical_width_m": 15.6,
        "excess_pavement_m": 2.0,
    },
    {
        "id": "sheppard-west-yonge-beecroft",
        "label": "Sheppard Avenue West (Yonge Street to Beecroft Road)",
        "street": "Sheppard Avenue West",
        "from_street": "Yonge Street",
        "to_street": "Beecroft Road",
        "existing_row_m": 36,
        "planned_row_m": 36,
        "travel_width_m": 25.3,
        "travel_width_varies": True,
        "lanes": 7,
        "typical_width_m": 21.6,
        "excess_pavement_m": 3.7,
    },
    {
        "id": "sheppard-west-of-beecroft",
        "label": "Sheppard Avenue West (west of Beecroft Road)",
        "street": "Sheppard Avenue West",
        "from_street": "Beecroft Road",
        "direction": "west",
        "existing_row_m": 36,
        "planned_row_m": 36,
        "travel_width_m": 17.6,
        "travel_width_varies": True,
        "lanes": 5,
        "typical_width_m": 15.6,
        "excess_pavement_m": 2.0,
    },
]


def haversine_m(a: tuple[float, float], b: tuple[float, float]) -> float:
    lat1, lon1 = a
    lat2, lon2 = b
    r = 6371000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    h = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(h))


def overpass_query() -> dict:
    s, w, n, e = BBOX
    names = "".join(
        f'  way["highway"]["name"="{name}"]({s},{w},{n},{e});\n' for name in STREET_NAMES
    )
    query = f"[out:json][timeout:90];\n(\n{names});\nout geom;\n"
    cache = HERE / "overpass-cache.json"
    if cache.exists():
        return json.loads(cache.read_text())
    body = urllib.parse.urlencode({"data": query}).encode()
    req = urllib.request.Request(
        OVERPASS_URL, data=body, headers={"User-Agent": USER_AGENT}
    )
    with urllib.request.urlopen(req, timeout=120) as resp:
        data = json.loads(resp.read().decode())
    cache.write_text(json.dumps(data))
    return data


class StreetNet:
    def __init__(self, ways: list[dict]):
        self.adj: dict[int, set[int]] = defaultdict(set)
        self.coord: dict[int, tuple[float, float]] = {}
        for way in ways:
            nodes = way["nodes"]
            geom = way["geometry"]
            for nid, pt in zip(nodes, geom):
                self.coord[nid] = (pt["lat"], pt["lon"])
            for a, b in zip(nodes, nodes[1:]):
                self.adj[a].add(b)
                self.adj[b].add(a)

    def intersection_nodes(self, other: StreetNet, max_m: float = 28.0) -> set[int]:
        shared = set(self.coord) & set(other.coord)
        if shared:
            return shared
        hits: set[int] = set()
        other_pts = list(other.coord.values())
        for nid, pt in self.coord.items():
            for opt in other_pts:
                if haversine_m(pt, opt) <= max_m:
                    hits.add(nid)
                    break
        return hits

    def walk(self, starts: set[int], weight=True) -> dict[int, float]:
        dist = {n: 0.0 for n in starts if n in self.coord}
        q = deque(dist)
        while q:
            u = q.popleft()
            for v in self.adj[u]:
                step = haversine_m(self.coord[u], self.coord[v]) if weight else 1.0
                nd = dist[u] + step
                if v not in dist or nd < dist[v] - 1e-6:
                    dist[v] = nd
                    q.append(v)
        return dist

    def _representative(self, nodes: set[int]) -> int:
        lat = sum(self.coord[n][0] for n in nodes) / len(nodes)
        lon = sum(self.coord[n][1] for n in nodes) / len(nodes)
        return min(nodes, key=lambda n: haversine_m(self.coord[n], (lat, lon)))

    def between(self, starts: set[int], ends: set[int]) -> list[list[tuple[float, float]]]:
        if not starts or not ends:
            return []
        s0 = self._representative(starts)
        e0 = self._representative(ends)
        ds = self.walk({s0})
        if e0 not in ds:
            ds = self.walk(starts)
            de = self.walk(ends)
            reachable_ends = [e for e in ends if e in ds]
            if not reachable_ends:
                return []
            target = min(ds[e] for e in reachable_ends)
            keep = {
                n
                for n, d0 in ds.items()
                if n in de and abs(d0 + de[n] - target) <= 12.0
            }
            return self._lines_from_nodes(keep)
        de = self.walk({e0})
        target = ds[e0]
        spine = {n for n, d0 in ds.items() if n in de and abs(d0 + de[n] - target) <= 8.0}
        keep = set(spine)
        for n, pt in self.coord.items():
            if n in keep:
                continue
            if any(haversine_m(pt, self.coord[s]) <= 22.0 for s in spine):
                keep.add(n)
        return self._lines_from_nodes(keep)

    def ray(self, starts: set[int], direction: str) -> list[list[tuple[float, float]]]:
        """Keep the connected component on the named side of the origin.

        OpenStreetMap dual carriageways jog north/south at intersections, so a
        strict 'always move west' walk dies after one block. Filter by
        position relative to the origin instead.
        """
        if not starts:
            return []
        reachable = set(self.walk(starts))
        o_lat = sum(self.coord[n][0] for n in starts) / len(starts)
        o_lon = sum(self.coord[n][1] for n in starts) / len(starts)
        pad = 0.00012  # ~10 m, covers intersection fillets
        keep = set()
        for n in reachable:
            lat, lon = self.coord[n]
            ok = {
                "west": lon <= o_lon + pad,
                "east": lon >= o_lon - pad,
                "north": lat >= o_lat - pad,
                "south": lat <= o_lat + pad,
            }[direction]
            if ok:
                keep.add(n)
        return self._lines_from_nodes(keep)

    def offset_nodes(self, origin: set[int], direction: str, meters: float) -> set[int]:
        dist = self.walk(origin)
        best = None
        best_err = 1e9
        for nid, d in dist.items():
            lat, lon = self.coord[nid]
            olat = sum(self.coord[n][0] for n in origin) / len(origin)
            olon = sum(self.coord[n][1] for n in origin) / len(origin)
            progress = {
                "north": lat - olat,
                "south": olat - lat,
                "east": lon - olon,
                "west": olon - lon,
            }[direction]
            if progress <= 0:
                continue
            err = abs(d - meters)
            if err < best_err:
                best_err = err
                best = nid
        return {best} if best is not None else set()

    def _lines_from_nodes(self, keep: set[int]) -> list[list[tuple[float, float]]]:
        remaining: set[tuple[int, int]] = set()
        adj: dict[int, set[int]] = defaultdict(set)
        for u in keep:
            for v in self.adj[u]:
                if v in keep:
                    e = (u, v) if u < v else (v, u)
                    remaining.add(e)
                    adj[u].add(v)
                    adj[v].add(u)

        def pop_edge(u: int, v: int) -> None:
            e = (u, v) if u < v else (v, u)
            remaining.discard(e)
            adj[u].discard(v)
            adj[v].discard(u)

        lines: list[list[tuple[float, float]]] = []
        while remaining:
            a, b = next(iter(remaining))
            pop_edge(a, b)
            chain = deque([a, b])
            # extend forward
            while adj[chain[-1]]:
                nxt = next(iter(adj[chain[-1]]))
                pop_edge(chain[-1], nxt)
                chain.append(nxt)
            # extend backward
            while adj[chain[0]]:
                nxt = next(iter(adj[chain[0]]))
                pop_edge(chain[0], nxt)
                chain.appendleft(nxt)
            if len(chain) >= 2:
                lines.append([self.coord[n] for n in chain])
        return lines


def nets_from_overpass(data: dict) -> dict[str, StreetNet]:
    grouped: dict[str, list] = defaultdict(list)
    for el in data.get("elements", []):
        name = el.get("tags", {}).get("name")
        if name:
            grouped[name].append(el)
    return {name: StreetNet(ways) for name, ways in grouped.items()}


def resolve_nodes(nets: dict[str, StreetNet], street: str, other: str) -> set[int]:
    if street not in nets or other not in nets:
        return set()
    return nets[street].intersection_nodes(nets[other])


def geometry_for(seg: dict, nets: dict[str, StreetNet]) -> list[list[tuple[float, float]]]:
    street = seg["street"]
    net = nets.get(street)
    if net is None:
        return []

    def nodes_from_spec(spec_key: str, offset_key: str) -> set[int]:
        if spec_key in seg:
            return resolve_nodes(nets, street, seg[spec_key])
        off = seg.get(offset_key)
        if not off:
            return set()
        origin = resolve_nodes(nets, street, off["along"])
        return net.offset_nodes(origin, off["direction"], off["meters"])

    starts = nodes_from_spec("from_street", "from_offset")
    if "direction" in seg:
        return net.ray(starts, seg["direction"])
    ends = nodes_from_spec("to_street", "to_offset")
    return net.between(starts, ends)


def color_for(excess: float) -> str:
    if excess <= 0.3:
        return "#4c6b58"
    if excess <= 1.0:
        return "#c4a35a"
    if excess <= 2.0:
        return "#c47a3a"
    return "#b42318"


def feature_collection(segs_with_geom: list[tuple[dict, list]]) -> dict:
    features = []
    for seg, lines in segs_with_geom:
        coords = [[[lon, lat] for lat, lon in line] for line in lines]
        geom = (
            {"type": "LineString", "coordinates": coords[0]}
            if len(coords) == 1
            else {"type": "MultiLineString", "coordinates": coords}
        )
        props = {
            k: v
            for k, v in seg.items()
            if k not in {"from_offset", "to_offset"}
        }
        props["color"] = color_for(seg["excess_pavement_m"])
        features.append({"type": "Feature", "geometry": geom, "properties": props})
    return {"type": "FeatureCollection", "features": features}


HTML = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>North York Centre — Table 3-15 Right-of-Way</title>
  <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
  <style>
    html, body, #map { height: 100%; margin: 0; }
    body { font-family: Georgia, "Times New Roman", serif; }
    .panel {
      position: absolute; z-index: 1000; top: 12px; left: 12px;
      background: #fff; padding: 12px 14px; max-width: 340px;
      border: 1px solid #222; font-size: 13px; line-height: 1.35;
    }
    .panel h1 { font-size: 16px; margin: 0 0 6px; font-weight: 600; }
    .panel p { margin: 0 0 8px; }
    .legend span { display: inline-block; width: 18px; height: 6px; margin-right: 6px; vertical-align: middle; }
    .legend div { margin: 3px 0; }
    .popup dt { font-weight: 600; }
    .popup dd { margin: 0 0 6px; }
    .search { display: flex; gap: 6px; margin: 8px 0 6px; }
    .search input {
      flex: 1; min-width: 0; font: inherit; padding: 4px 6px;
      border: 1px solid #222; background: #fff;
    }
    .search button {
      font: inherit; padding: 4px 10px; border: 1px solid #222;
      background: #222; color: #fff; cursor: pointer;
    }
    #search-status { margin: 0; font-size: 12px; min-height: 1.2em; }
    #search-results { list-style: none; margin: 6px 0 0; padding: 0; max-height: 140px; overflow: auto; }
    #search-results button {
      display: block; width: 100%; text-align: left; font: inherit;
      font-size: 12px; padding: 4px 0; border: 0; border-top: 1px solid #ddd;
      background: transparent; cursor: pointer;
    }
  </style>
</head>
<body>
  <div class="panel">
    <h1>3.4 Right-of-Way on OpenStreetMap</h1>
    <p>Table 3-15 from Appendix A, <em>North York at the Centre</em> Phase 1 Background Report. Lines are OSM street centreline, not legal ROW polygons. Colour is excess pavement vs. the City lane-width target.</p>
    <form class="search" id="search-form" role="search">
      <label class="visually-hidden" for="street-search" style="position:absolute;left:-9999px">Street</label>
      <input id="street-search" name="q" type="search" list="street-names" placeholder="Search a street" autocomplete="off" />
      <button type="submit">Search</button>
    </form>
    <datalist id="street-names"></datalist>
    <p id="search-status"></p>
    <ul id="search-results" hidden></ul>
    <div class="legend">
      <div><span style="background:#4c6b58"></span> 0–0.3 m excess</div>
      <div><span style="background:#c4a35a"></span> 0.3–1.0 m</div>
      <div><span style="background:#c47a3a"></span> 1.0–2.0 m</div>
      <div><span style="background:#b42318"></span> over 2.0 m</div>
    </div>
    <p style="margin-top:8px;font-size:12px">Click a corridor for existing / planned ROW. Source: City of Toronto report · basemap © OpenStreetMap</p>
  </div>
  <div id="map"></div>
  <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
  <script>
    const data = GEOJSON_PLACEHOLDER;
    const map = L.map("map").setView([43.7615, -79.411], 14);
    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
      maxZoom: 19,
      attribution: "&copy; OpenStreetMap"
    }).addTo(map);
    const corridors = [];
    function baseStyle(feat) {
      return { color: feat.properties.color, weight: 6, opacity: 0.9 };
    }
    const layer = L.geoJSON(data, {
      style: baseStyle,
      onEachFeature(feat, lyr) {
        const p = feat.properties;
        const vary = p.travel_width_varies ? "*" : "";
        lyr.bindPopup(`
          <div class="popup">
            <strong>${p.label}</strong>
            <dl>
              <dt>Existing / planned ROW</dt>
              <dd>${p.existing_row_m} m / ${p.planned_row_m} m</dd>
              <dt>Travel width / lanes</dt>
              <dd>${p.travel_width_m}${vary} m / ${p.lanes} lanes</dd>
              <dt>Typical new-street width</dt>
              <dd>${p.typical_width_m} m</dd>
              <dt>Excess pavement</dt>
              <dd>${p.excess_pavement_m} m</dd>
            </dl>
            ${p.to_note ? `<p>${p.to_note}</p>` : ""}
          </div>`);
        corridors.push(lyr);
      }
    }).addTo(map);
    if (layer.getBounds().isValid()) map.fitBounds(layer.getBounds(), { padding: [40, 40] });

    const names = [...new Set(corridors.map((lyr) => lyr.feature.properties.street))].sort();
    const datalist = document.getElementById("street-names");
    names.forEach((name) => {
      const opt = document.createElement("option");
      opt.value = name;
      datalist.appendChild(opt);
    });

    const statusEl = document.getElementById("search-status");
    const resultsEl = document.getElementById("search-results");

    function resetStyles() {
      layer.eachLayer((lyr) => lyr.setStyle(baseStyle(lyr.feature)));
    }

    function focusCorridor(lyr) {
      resetStyles();
      lyr.setStyle({ color: "#111", weight: 9, opacity: 1 });
      lyr.bringToFront();
      const bounds = lyr.getBounds();
      if (bounds.isValid()) map.fitBounds(bounds, { padding: [48, 48], maxZoom: 17 });
      lyr.openPopup();
    }

    function haystack(p) {
      return [p.label, p.street, p.from_street, p.to_street, p.id]
        .filter(Boolean)
        .join(" ")
        .toLowerCase();
    }

    function searchStreets(query) {
      const q = query.trim().toLowerCase();
      resultsEl.replaceChildren();
      resultsEl.hidden = true;
      if (!q) {
        statusEl.textContent = "Type a street name, then search.";
        return;
      }
      const hits = corridors.filter((lyr) => haystack(lyr.feature.properties).includes(q));
      if (!hits.length) {
        statusEl.textContent = `No corridor matches “${query.trim()}”.`;
        return;
      }
      if (hits.length === 1) {
        statusEl.textContent = hits[0].feature.properties.label;
        focusCorridor(hits[0]);
        return;
      }
      statusEl.textContent = `${hits.length} corridors match.`;
      resultsEl.hidden = false;
      hits.forEach((lyr) => {
        const item = document.createElement("li");
        const btn = document.createElement("button");
        btn.type = "button";
        btn.textContent = lyr.feature.properties.label;
        btn.addEventListener("click", () => focusCorridor(lyr));
        item.appendChild(btn);
        resultsEl.appendChild(item);
      });
      focusCorridor(hits[0]);
    }

    document.getElementById("search-form").addEventListener("submit", (event) => {
      event.preventDefault();
      searchStreets(document.getElementById("street-search").value);
    });
  </script>
</body>
</html>
"""


def main() -> None:
    data = overpass_query()
    nets = nets_from_overpass(data)
    print("OSM streets:", {k: len(v.coord) for k, v in sorted(nets.items())})
    built = []
    for seg in SEGMENTS:
        geom = geometry_for(seg, nets)
        npts = sum(len(g) for g in geom)
        print(f"{seg['id']}: {len(geom)} parts, {npts} vertices")
        if geom:
            built.append((seg, geom))
        else:
            print("  WARNING: no geometry")
    fc = feature_collection(built)
    geo_path = HERE / "table-3-15.geojson"
    geo_path.write_text(json.dumps(fc))
    html = HTML.replace("GEOJSON_PLACEHOLDER", json.dumps(fc))
    (HERE / "index.html").write_text(html)
    print(f"wrote {geo_path}")
    print(f"wrote {HERE / 'index.html'}")


if __name__ == "__main__":
    main()
