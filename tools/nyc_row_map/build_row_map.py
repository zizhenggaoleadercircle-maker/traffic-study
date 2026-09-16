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
BBOX = (43.736, -79.456, 43.799, -79.378)  # s, w, n, e — Mobility Study Area
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
    "Franklin Avenue",
    "Cummer Avenue",
    "Steeles Avenue East",
    "Steeles Avenue West",
    "Bathurst Street",
    "Bayview Avenue",
    "Wilson Avenue",
    "Byng Avenue",
    "Willowdale Avenue",
    "Empress Avenue",
    "Senlac Road",
    "Cactus Avenue",
    "Peckham Avenue",
    "Moore Park Avenue",
    "Churchill Avenue",
    "Tamworth Road",
    "Grantbrook Street",
    "Drewry Avenue",
    "Hilda Avenue",
    "Pleasant Avenue",
    "Kenneth Avenue",
    "Newton Drive",
    "Dumont Street",
    "Patricia Avenue",
    "Chelmsford Avenue",
    "Talbot Road",
    "Newtonbrook Boulevard",
    "Fairchild Avenue",
    "Lorraine Drive",
    "Wilfred Avenue",
    "Kingsdale Avenue",
    "Parkview Avenue",
    "Burndale Avenue",
    "Bangor Road",
    "Burnett Avenue",
    "Quilter Road",
    "Harlandale Avenue",
    "Duplex Avenue",
    "Hendon Avenue",
    "Cushendale Drive",
    "Cushenale Drive",
    "Silverview Drive",
    "Bowerbank Drive",
    "Deering Crescent",
    "Glendora Avenue",
    "Burnwell Street",
    "Dudley Avenue",
    "Basswood Road",
    "Basil Hall Court",
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

# Tables 3-16 (arterial), 3-17 (collector), 3-18 (local Poor) — Mobility Review §3.4.3.
CONDITION_SEGMENTS = [
    {
        "id": "cond-yonge-franklin-finch",
        "label": "Yonge Street (Franklin Avenue to Finch Avenue East)",
        "street": "Yonge Street",
        "from_street": "Franklin Avenue",
        "to_street": "Finch Avenue East",
        "clazz": "Arterial",
        "table": "3-16",
        "condition": "Fair",
        "opportunity": "Implement the REimagining Yonge cross section and associated improvements.",
        "to_note": "Report start is 43 m south of Franklin Avenue.",
    },
    {
        "id": "cond-yonge-cummer-steeles",
        "label": "Yonge Street (Cummer Avenue to Steeles Avenue East)",
        "street": "Yonge Street",
        "from_street": "Cummer Avenue",
        "to_street": "Steeles Avenue East",
        "clazz": "Arterial",
        "table": "3-16",
        "condition": "Fair",
        "opportunity": "Yonge Street North TMP includes reconfiguration of this segment similar to REimagining Yonge; opportunity to bundle with future work.",
    },
    {
        "id": "cond-sheppard-e-yonge-bonnington",
        "label": "Sheppard Avenue East (Yonge Street to Bonnington Place)",
        "street": "Sheppard Avenue East",
        "from_street": "Yonge Street",
        "to_street": "Bonnington Place",
        "clazz": "Arterial",
        "table": "3-16",
        "condition": "Fair",
        "opportunity": "Segment from Yonge Street to Bonnington Place is to be bundled with planned Doris Avenue Extension and will include extending cycle tracks to Yonge Street.",
    },
    {
        "id": "cond-sheppard-e-bonnington-bayview",
        "label": "Sheppard Avenue East (Bonnington Place to Bayview Avenue)",
        "street": "Sheppard Avenue East",
        "from_street": "Bonnington Place",
        "to_street": "Bayview Avenue",
        "clazz": "Arterial",
        "table": "3-16",
        "condition": "Fair",
        "opportunity": "Major street resurfacing underway to be completed in 2024 from Bonnington Place to Bayview Avenue includes addition of cycle tracks and sidewalk repairs.",
    },
    {
        "id": "cond-sheppard-w-bathurst-yonge",
        "label": "Sheppard Avenue West (Bathurst Street to Yonge Street)",
        "street": "Sheppard Avenue West",
        "from_street": "Bathurst Street",
        "to_street": "Yonge Street",
        "clazz": "Arterial",
        "table": "3-16",
        "condition": "Fair",
        "opportunity": "Narrow existing lanes, widen existing sidewalks where under 2.1 m, add cycle tracks, potential early works to support future Sheppard Subway Extension.",
    },
    {
        "id": "cond-finch-w-bathurst-yonge",
        "label": "Finch Avenue West (Bathurst Street to Yonge Street)",
        "street": "Finch Avenue West",
        "from_street": "Bathurst Street",
        "to_street": "Yonge Street",
        "clazz": "Arterial",
        "table": "3-16",
        "condition": "Poor",
        "opportunity": "Narrow existing lanes, widen existing sidewalks where under 2.1 m, consider priority measures for surface transit, consider cycling facilities or streetscaping, potential early works to support future Finch West LRT Extension.",
    },
    {
        "id": "cond-finch-e-yonge-bayview",
        "label": "Finch Avenue East (Yonge Street to Bayview Avenue)",
        "street": "Finch Avenue East",
        "from_street": "Yonge Street",
        "to_street": "Bayview Avenue",
        "clazz": "Arterial",
        "table": "3-16",
        "condition": "Fair",
        "opportunity": "Narrow existing lanes, widen existing sidewalks where under 2.1 m, consider priority measures for surface transit, consider cycling facilities or streetscaping, consider road diet.",
    },
    {
        "id": "cond-doris-church-byng",
        "label": "Doris Avenue (Church Avenue to Byng Avenue)",
        "street": "Doris Avenue",
        "from_street": "Church Avenue",
        "to_street": "Byng Avenue",
        "clazz": "Arterial",
        "table": "3-16",
        "condition": "Fair",
        "opportunity": "Narrow existing lanes, widen existing sidewalks where under 2.1 m, consider new pedestrian crossing(s), consider cycling facilities, consider road diet.",
    },
    {
        "id": "cond-beecroft-parkhome-poyntz",
        "label": "Beecroft Road (Park Home Avenue to Poyntz Avenue)",
        "street": "Beecroft Road",
        "from_street": "Park Home Avenue",
        "to_street": "Poyntz Avenue",
        "clazz": "Arterial",
        "table": "3-16",
        "condition": "Fair",
        "opportunity": "Narrow existing lanes, widen existing sidewalks where under 2.1 m, consider new pedestrian crossing(s), consider cycling facilities, consider road diet, consider a wider boulevard.",
    },
    {
        "id": "cond-steeles-w-bathurst-yonge",
        "label": "Steeles Avenue West (Bathurst Street to Yonge Street)",
        "street": "Steeles Avenue West",
        "from_street": "Bathurst Street",
        "to_street": "Yonge Street",
        "clazz": "Arterial",
        "table": "3-16",
        "condition": "Fair",
        "opportunity": "Narrow existing lanes, widen existing sidewalks where under 2.1 m, consider conversion of curb lanes to bus lanes, add cycling facilities.",
    },
    {
        "id": "cond-steeles-e-yonge-bayview",
        "label": "Steeles Avenue East (Yonge Street to Bayview Avenue)",
        "street": "Steeles Avenue East",
        "from_street": "Yonge Street",
        "direction": "east",
        "clazz": "Arterial",
        "table": "3-16",
        "condition": "Poor",
        "opportunity": "Narrow existing lanes, widen existing sidewalks where under 2.1 m, consider conversion of curb lanes to bus lanes, add cycling facilities.",
        "to_note": "Report names Bayview Avenue N.",
    },
    {
        "id": "cond-bathurst-wilson-sheppard",
        "label": "Bathurst Street (Wilson Avenue to Sheppard Avenue)",
        "street": "Bathurst Street",
        "from_street": "Wilson Avenue",
        "to_street": "Sheppard Avenue West",
        "clazz": "Arterial",
        "table": "3-16",
        "condition": "Poor",
        "opportunity": "Narrow existing lanes, widen existing sidewalks where under 2.1 m, implement the cycling facility included in the City's Near-Term Implementation Plan.",
        "to_note": "Report names Sheppard Avenue East as the north end of this Bathurst segment.",
    },
    {
        "id": "cond-bathurst-sheppard-ellerslie",
        "label": "Bathurst Street (Sheppard Avenue to Ellerslie Avenue)",
        "street": "Bathurst Street",
        "from_street": "Sheppard Avenue West",
        "to_street": "Ellerslie Avenue",
        "clazz": "Arterial",
        "table": "3-16",
        "condition": "Fair",
        "opportunity": "Narrow existing lanes, widen existing sidewalks where under 2.1 m, implement the cycling facility included in the City's Near-Term Implementation Plan.",
    },
    {
        "id": "cond-bathurst-ellerslie-finch",
        "label": "Bathurst Street (Ellerslie Avenue to Finch Avenue West)",
        "street": "Bathurst Street",
        "from_street": "Ellerslie Avenue",
        "to_street": "Finch Avenue West",
        "clazz": "Arterial",
        "table": "3-16",
        "condition": "Poor",
        "opportunity": "Narrow existing lanes, widen existing sidewalks where under 2.1 m, implement the cycling facility included in the City's Near-Term Implementation Plan.",
    },
    {
        "id": "cond-poyntz-beecroft-yonge",
        "label": "Poyntz Avenue (Beecroft Road to Yonge Street)",
        "street": "Poyntz Avenue",
        "from_street": "Beecroft Road",
        "to_street": "Yonge Street",
        "clazz": "Arterial",
        "table": "3-16",
        "condition": "Fair",
        "opportunity": "Narrow existing lanes, enhance pedestrian realm with buffer on south side.",
    },
    {
        "id": "cond-senlac-finch-sheppard",
        "label": "Senlac Road (Finch Avenue West to Sheppard Avenue West)",
        "street": "Senlac Road",
        "from_street": "Finch Avenue West",
        "to_street": "Sheppard Avenue West",
        "clazz": "Arterial",
        "table": "3-16",
        "condition": "Fair",
        "opportunity": "Retrofit cycle tracks or bike lanes within existing roadway.",
        "to_note": "Report names Finch Avenue and Sheppard Avenue East.",
    },
    {
        "id": "cond-willowdale-empress-sheppard",
        "label": "Willowdale Avenue (Empress Avenue to Sheppard Avenue East)",
        "street": "Willowdale Avenue",
        "from_street": "Empress Avenue",
        "to_street": "Sheppard Avenue East",
        "clazz": "Arterial",
        "table": "3-16",
        "condition": "Fair",
        "opportunity": "Consider new pedestrian crossing(s), widen sidewalks, enhance pedestrian realm with landscaping.",
    },
    {
        "id": "cond-willowdale-cummer-bishop",
        "label": "Willowdale Avenue (Cummer Avenue to Bishop Avenue)",
        "street": "Willowdale Avenue",
        "from_street": "Cummer Avenue",
        "to_street": "Bishop Avenue",
        "clazz": "Arterial",
        "table": "3-16",
        "condition": "Fair",
        "opportunity": "Widen existing sidewalks where under 2.1 m, extend existing cycling tracks south of Bishop Avenue north to Steeles Avenue, enhance pedestrian realm with landscaping.",
    },
    {
        "id": "cond-norton-yonge-doris",
        "label": "Norton Avenue (Yonge Street to Doris Avenue)",
        "street": "Norton Avenue",
        "from_street": "Yonge Street",
        "to_street": "Doris Avenue",
        "clazz": "Collector",
        "table": "3-17",
        "condition": "Poor",
        "opportunity": "Narrow lanes, enhance pedestrian realm with landscaping and amenities (benches etc.), implement traffic calming measures.",
    },
    {
        "id": "cond-bishop-maxome-willowdale",
        "label": "Bishop Avenue (Maxome Avenue to Willowdale Avenue)",
        "street": "Bishop Avenue",
        "from_street": "Maxome Avenue",
        "to_street": "Willowdale Avenue",
        "clazz": "Collector",
        "table": "3-17",
        "condition": "Fair",
        "opportunity": "Build a pedestrian facility on the north side, narrow lanes, enhance pedestrian realm with landscaping and amenities (benches etc.), implement traffic calming measures.",
    },
    {
        "id": "cond-cactus-peckham-moorepark",
        "label": "Cactus Avenue (Peckham Avenue to Moore Park Avenue)",
        "street": "Cactus Avenue",
        "from_street": "Peckham Avenue",
        "to_street": "Moore Park Avenue",
        "clazz": "Collector",
        "table": "3-17",
        "condition": "Fair",
        "opportunity": "Enhance pedestrian realm with landscaping and amenities (benches etc.), implement traffic calming measures.",
    },
    {
        "id": "cond-churchill-senlac-tamworth",
        "label": "Churchill Avenue (Senlac Road to Tamworth Road)",
        "street": "Churchill Avenue",
        "from_street": "Senlac Road",
        "to_street": "Tamworth Road",
        "clazz": "Collector",
        "table": "3-17",
        "condition": "Fair",
        "opportunity": "Build a pedestrian facility on the south side, narrow lanes, widen existing sidewalk, enhance pedestrian realm with landscaping and amenities (benches etc.), implement traffic calming measures.",
    },
    {
        "id": "cond-grantbrook-finch-drewry",
        "label": "Grantbrook Street (Finch Avenue West to Drewry Avenue)",
        "street": "Grantbrook Street",
        "from_street": "Finch Avenue West",
        "to_street": "Drewry Avenue",
        "clazz": "Collector",
        "table": "3-17",
        "condition": "Fair",
        "opportunity": "Build a pedestrian facility on the east side, narrow lanes, enhance pedestrian realm with landscaping and amenities (benches etc.), implement traffic calming measures.",
    },
    {
        "id": "cond-hilda-pleasant-drewry",
        "label": "Hilda Avenue (Pleasant Avenue to Drewry Avenue)",
        "street": "Hilda Avenue",
        "from_street": "Pleasant Avenue",
        "to_street": "Drewry Avenue",
        "clazz": "Collector",
        "table": "3-17",
        "condition": "Fair",
        "opportunity": "Fill in gaps in the pedestrian network on the west side, narrow lanes, enhance pedestrian realm with landscaping and amenities (benches etc.), implement traffic calming measures, consider cycling lanes.",
    },
    {
        "id": "cond-kenneth-finch-sheppard",
        "label": "Kenneth Avenue (Finch Avenue East to Sheppard Avenue East)",
        "street": "Kenneth Avenue",
        "from_street": "Finch Avenue East",
        "to_street": "Sheppard Avenue East",
        "clazz": "Collector",
        "table": "3-17",
        "condition": "Fair",
        "opportunity": "Fill in gaps in the pedestrian network on the west side, widen existing sidewalks, narrow lanes, enhance pedestrian realm with a wider buffer, landscaping and amenities (benches etc.), implement traffic calming measures, consider cycling facilities.",
    },
    {
        "id": "cond-maxome-steeles-newton",
        "label": "Maxome Avenue (Steeles Avenue East to Newton Drive)",
        "street": "Maxome Avenue",
        "from_street": "Newton Drive",
        "direction": "north",
        "clazz": "Collector",
        "table": "3-17",
        "condition": "Fair",
        "opportunity": "Narrow lanes, enhance pedestrian realm with landscaping and amenities (benches etc.), implement traffic calming measures, consider cycling facilities.",
    },
    {
        "id": "cond-maxome-cummer-finch",
        "label": "Maxome Avenue (Cummer Avenue to Finch Avenue East)",
        "street": "Maxome Avenue",
        "from_street": "Cummer Avenue",
        "to_street": "Finch Avenue East",
        "clazz": "Collector",
        "table": "3-17",
        "condition": "Fair",
        "opportunity": "Widen existing sidewalks, narrow lanes, enhance pedestrian realm with landscaping and amenities (benches etc.), implement traffic calming measures, consider cycling facilities.",
    },
    {
        "id": "cond-newton-yonge-dumont",
        "label": "Newton Drive (Yonge Street to Dumont Street)",
        "street": "Newton Drive",
        "from_street": "Yonge Street",
        "to_street": "Dumont Street",
        "clazz": "Collector",
        "table": "3-17",
        "condition": "Fair",
        "opportunity": "Build a sidewalk on the south side, widen existing sidewalk, narrow lanes, enhance pedestrian realm with landscaping and amenities (benches etc.), implement traffic calming measures.",
    },
    {
        "id": "cond-newton-willowdale-bayview",
        "label": "Newton Drive (Willowdale Avenue to Bayview Avenue)",
        "street": "Newton Drive",
        "from_street": "Willowdale Avenue",
        "direction": "east",
        "clazz": "Collector",
        "table": "3-17",
        "condition": "Fair",
        "opportunity": "Fill in gaps in the pedestrian network on the west side, widen existing sidewalks, narrow lanes, enhance pedestrian realm with landscaping and amenities (benches etc.), implement traffic calming measures, consider cycling facilities.",
    },
    {
        "id": "cond-parkhome-beecroft-yonge",
        "label": "Park Home Avenue (Beecroft Road to Yonge Street)",
        "street": "Park Home Avenue",
        "from_street": "Beecroft Road",
        "to_street": "Yonge Street",
        "clazz": "Collector",
        "table": "3-17",
        "condition": "Fair",
        "opportunity": "Widen existing sidewalk, narrow lanes, enhance pedestrian realm with wider buffer on south side, landscaping and amenities (benches etc.), implement traffic calming measures.",
    },
    {
        "id": "cond-patricia-chelmsford-peckham",
        "label": "Patricia Avenue (Chelmsford Avenue to Peckham Avenue)",
        "street": "Patricia Avenue",
        "from_street": "Chelmsford Avenue",
        "to_street": "Peckham Avenue",
        "clazz": "Collector",
        "table": "3-17",
        "condition": "Fair",
        "opportunity": "Widen existing sidewalk, narrow lanes, enhance pedestrian realm with landscaping and amenities (benches etc.), implement traffic calming measures.",
    },
    {
        "id": "cond-patricia-peckham-cactus",
        "label": "Patricia Avenue (Peckham Avenue to Cactus Avenue)",
        "street": "Patricia Avenue",
        "from_street": "Peckham Avenue",
        "to_street": "Cactus Avenue",
        "clazz": "Collector",
        "table": "3-17",
        "condition": "Poor",
        "opportunity": "Widen existing sidewalk, narrow lanes, enhance pedestrian realm with landscaping and amenities (benches etc.), implement traffic calming measures.",
    },
    {
        "id": "cond-patricia-cactus-hilda",
        "label": "Patricia Avenue (Cactus Avenue to Hilda Avenue)",
        "street": "Patricia Avenue",
        "from_street": "Cactus Avenue",
        "to_street": "Hilda Avenue",
        "clazz": "Collector",
        "table": "3-17",
        "condition": "Fair",
        "opportunity": "Build a sidewalk on the north side, widen existing sidewalk, narrow lanes, enhance pedestrian realm with landscaping and amenities (benches etc.), implement traffic calming measures.",
    },
    {
        "id": "cond-talbot-newtonbrook-fairchild",
        "label": "Talbot Road (Newtonbrook Boulevard to Fairchild Avenue)",
        "street": "Talbot Road",
        "from_street": "Newtonbrook Boulevard",
        "to_street": "Fairchild Avenue",
        "clazz": "Collector",
        "table": "3-17",
        "condition": "Poor",
        "opportunity": "Narrow vehicle lanes, widen sidewalks, consider bicycle lanes, enhance pedestrian realm with landscaping and amenities (benches etc.), implement traffic calming measures.",
    },
    {
        "id": "cond-talbot-fairchild-lorraine",
        "label": "Talbot Road (Fairchild Avenue to Lorraine Drive)",
        "street": "Talbot Road",
        "from_street": "Fairchild Avenue",
        "to_street": "Lorraine Drive",
        "clazz": "Collector",
        "table": "3-17",
        "condition": "Fair",
        "opportunity": "Narrow vehicle lanes, widen sidewalks, consider bicycle lanes, enhance pedestrian realm with landscaping and amenities (benches etc.), implement traffic calming measures.",
    },
    {
        "id": "cond-wilfred-finch-sheppard",
        "label": "Wilfred Avenue (Finch Avenue East to Sheppard Avenue East)",
        "street": "Wilfred Avenue",
        "from_street": "Finch Avenue East",
        "to_street": "Sheppard Avenue East",
        "clazz": "Collector",
        "table": "3-17",
        "condition": "Fair",
        "opportunity": "Narrow vehicle lanes, widen sidewalks, enhance pedestrian realm with a greater buffer on the east side and amenities (benches etc.), implement traffic calming measures.",
    },
    {
        "id": "cond-byng-yonge-kenneth",
        "label": "Byng Avenue (Yonge Street to Kenneth Avenue)",
        "street": "Byng Avenue",
        "from_street": "Yonge Street",
        "to_street": "Kenneth Avenue",
        "clazz": "Local",
        "table": "3-18",
        "condition": "Poor",
        "opportunity": "Widen existing sidewalks where under 2.1 m, enhance pedestrian realm with landscaping and amenities (benches etc.).",
    },
    {
        "id": "cond-kingsdale-doris-kenneth",
        "label": "Kingsdale Avenue (Doris Avenue to Kenneth Avenue)",
        "street": "Kingsdale Avenue",
        "from_street": "Doris Avenue",
        "to_street": "Kenneth Avenue",
        "clazz": "Local",
        "table": "3-18",
        "condition": "Poor",
        "opportunity": "Narrowing vehicle lanes, enhance pedestrian realm with landscaping and amenities (benches etc.).",
    },
    {
        "id": "cond-parkview-yonge-doris",
        "label": "Parkview Avenue (Yonge Street to Doris Avenue)",
        "street": "Parkview Avenue",
        "from_street": "Yonge Street",
        "to_street": "Doris Avenue",
        "clazz": "Local",
        "table": "3-18",
        "condition": "Poor",
        "opportunity": "Enhance pedestrian realm with green buffer, landscaping and amenities (benches etc.).",
    },
    {
        "id": "cond-burndale-bangor-burnett",
        "label": "Burndale Avenue (Bangor Road to Burnett Avenue)",
        "street": "Burndale Avenue",
        "from_street": "Bangor Road",
        "to_street": "Burnett Avenue",
        "clazz": "Local",
        "table": "3-18",
        "condition": "Poor",
        "opportunity": "Build pedestrian facility.",
    },
    {
        "id": "cond-elmhurst-senlac-quilter",
        "label": "Elmhurst Avenue (Senlac Road to Quilter Road)",
        "street": "Elmhurst Avenue",
        "from_street": "Senlac Road",
        "to_street": "Quilter Road",
        "clazz": "Local",
        "table": "3-18",
        "condition": "Poor",
        "opportunity": "Build pedestrian facility.",
    },
    {
        "id": "cond-harlandale-senlac-elmhurst",
        "label": "Harlandale Avenue (Senlac Road to Elmhurst Avenue)",
        "street": "Harlandale Avenue",
        "from_street": "Senlac Road",
        "to_street": "Elmhurst Avenue",
        "clazz": "Local",
        "table": "3-18",
        "condition": "Poor",
        "opportunity": "Enhance pedestrian realm with landscaping.",
    },
    {
        "id": "cond-duplex-hendon-finch",
        "label": "Duplex Avenue (Hendon Avenue to Finch Avenue West)",
        "street": "Duplex Avenue",
        "from_street": "Hendon Avenue",
        "to_street": "Finch Avenue West",
        "clazz": "Local",
        "table": "3-18",
        "condition": "Poor",
        "opportunity": "Enhance pedestrian realm with green buffer, landscaping and amenities (benches etc.), potential for cycling facility (connections to Finch Recreational Trail).",
    },
    {
        "id": "cond-cushendale-silverview-bowerbank",
        "label": "Cushendale Drive (Silverview Drive to Bowerbank Drive)",
        "street": "Cushendale Drive",
        "from_street": "Silverview Drive",
        "to_street": "Bowerbank Drive",
        "clazz": "Local",
        "table": "3-18",
        "condition": "Poor",
        "opportunity": "Build pedestrian facility.",
        "to_note": "Report spells this Cushenale Drive.",
    },
    {
        "id": "cond-bowerbank-silverview-deering",
        "label": "Bowerbank Drive (Silverview Drive to Deering Crescent)",
        "street": "Bowerbank Drive",
        "from_street": "Silverview Drive",
        "to_street": "Deering Crescent",
        "clazz": "Local",
        "table": "3-18",
        "condition": "Poor",
        "opportunity": "Build pedestrian facility.",
    },
    {
        "id": "cond-bonnington-sheppard-avondale",
        "label": "Bonnington Place (Sheppard Avenue East to Avondale Avenue)",
        "street": "Bonnington Place",
        "from_street": "Sheppard Avenue East",
        "direction": "south",
        "clazz": "Local",
        "table": "3-18",
        "condition": "Poor",
        "opportunity": "Enhance pedestrian realm with green buffer, landscaping and amenities (benches etc.).",
    },
    {
        "id": "cond-tradewind-sheppard-avondale",
        "label": "Tradewind Avenue (Sheppard Avenue East to Avondale Avenue)",
        "street": "Tradewind Avenue",
        "from_street": "Avondale Avenue",
        "direction": "north",
        "clazz": "Local",
        "table": "3-18",
        "condition": "Poor",
        "opportunity": "Enhance pedestrian realm with green buffer, landscaping and amenities (benches etc.).",
        "to_note": "Report groups Bonnington Place / Tradewind Avenue as one corridor.",
    },
    {
        "id": "cond-glendora-burnwell-dudley",
        "label": "Glendora Avenue (Burnwell Street to Dudley Avenue)",
        "street": "Glendora Avenue",
        "from_street": "Burnwell Street",
        "to_street": "Dudley Avenue",
        "clazz": "Local",
        "table": "3-18",
        "condition": "Poor",
        "opportunity": "Build pedestrian facility.",
    },
    {
        "id": "cond-basswood",
        "label": "Basswood Road (100 m north of Churchill Avenue)",
        "street": "Basswood Road",
        "whole_street": True,
        "clazz": "Local",
        "table": "3-18",
        "condition": "Poor",
        "opportunity": "Build pedestrian facility.",
        "to_note": "Report locates the poor segment 100 m north of Churchill Avenue; mapped as Basswood Road in the study area.",
    },
    {
        "id": "cond-basil-hall",
        "label": "Basil Hall Court (Beecroft Road)",
        "street": "Basil Hall Court",
        "whole_street": True,
        "clazz": "Local",
        "table": "3-18",
        "condition": "Poor",
        "opportunity": "Widen existing sidewalk.",
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

    def between_box(self, starts: set[int], ends: set[int]) -> list[list[tuple[float, float]]]:
        pts = [self.coord[n] for n in starts | ends if n in self.coord]
        if len(pts) < 2:
            return []
        lats = [p[0] for p in pts]
        lons = [p[1] for p in pts]
        pad = 0.0004
        minlat, maxlat = min(lats) - pad, max(lats) + pad
        minlon, maxlon = min(lons) - pad, max(lons) + pad
        keep = {
            n
            for n, (lat, lon) in self.coord.items()
            if minlat <= lat <= maxlat and minlon <= lon <= maxlon
        }
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
    if seg.get("whole_street"):
        return net._lines_from_nodes(set(net.coord))

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
    lines = net.between(starts, ends)
    if lines:
        return lines
    return net.between_box(starts, ends)


def color_for(excess: float) -> str:
    if excess <= 0.3:
        return "#4c6b58"
    if excess <= 1.0:
        return "#c4a35a"
    if excess <= 2.0:
        return "#c47a3a"
    return "#b42318"


def condition_color(condition: str) -> str:
    return "#7a1f1a" if condition == "Poor" else "#8a6a28"


def feature_collection(segs_with_geom: list[tuple[dict, list]], kind: str) -> dict:
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
            if k not in {"from_offset", "to_offset", "whole_street"}
        }
        props["kind"] = kind
        if kind == "row":
            props["color"] = color_for(seg["excess_pavement_m"])
        else:
            props["color"] = condition_color(seg["condition"])
        features.append({"type": "Feature", "geometry": geom, "properties": props})
    return {"type": "FeatureCollection", "features": features}


def parking_feature_collection() -> dict:
    lots = json.loads((HERE / "parking-lots.json").read_text())
    cache = json.loads((HERE / "parking-geocode-cache.json").read_text())
    used: dict[tuple[float, float], int] = {}
    features = []
    for lot in lots:
        hit = cache.get(lot["address"])
        if not hit:
            print(f"  WARNING: no geocode for {lot['id']} {lot['address']}")
            continue
        lat, lon = hit["lat"], hit["lon"]
        key = (round(lat, 5), round(lon, 5))
        n = used.get(key, 0)
        used[key] = n + 1
        # Nudge stacked lots at the same address so both markers stay clickable.
        lon = lon + n * 0.00012
        color = {
            "Public off-street": "#1f4e79",
            "TTC commuter": "#5b2c6f",
            "Private off-street": "#2e5a3c",
        }[lot["clazz"]]
        props = dict(lot)
        props["kind"] = "parking"
        props["color"] = color
        features.append(
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [lon, lat]},
                "properties": props,
            }
        )
        print(f"{lot['id']}: {lat:.5f},{lon:.5f}")
    return {"type": "FeatureCollection", "features": features}


HTML = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>North York Centre — Mobility Review 3.4</title>
  <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
  <style>
    html, body, #map { height: 100%; margin: 0; }
    body { font-family: Georgia, "Times New Roman", serif; }
    .panel {
      position: absolute; z-index: 1000; top: 12px; left: 12px;
      background: #fff; padding: 12px 14px; max-width: 360px; max-height: calc(100% - 24px);
      overflow: auto; border: 1px solid #222; font-size: 13px; line-height: 1.35;
    }
    .panel h1 { font-size: 16px; margin: 0 0 6px; font-weight: 600; }
    .panel p { margin: 0 0 8px; }
    .legend span { display: inline-block; width: 18px; height: 6px; margin-right: 6px; vertical-align: middle; }
    .legend div { margin: 3px 0; }
    .legend h2 { font-size: 12px; margin: 10px 0 4px; font-weight: 600; }
    .layers label { display: block; margin: 3px 0; }
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
    <h1>North York Centre mobility map</h1>
    <p>Appendix A, <em>North York at the Centre</em> Phase 1 Background Report. Street lines are OSM centreline, not legal ROW polygons. Parking markers are geocoded from the report addresses.</p>
    <div class="layers">
      <label><input type="checkbox" id="toggle-row" checked /> 3.4.1 Right-of-way / excess pavement</label>
      <label><input type="checkbox" id="toggle-pavement" /> 3.4.3 Pavement condition (Fair / Poor)</label>
      <label><input type="checkbox" id="toggle-parking" checked /> 3.5 Parking lots</label>
    </div>
    <form class="search" id="search-form" role="search">
      <label class="visually-hidden" for="street-search" style="position:absolute;left:-9999px">Street</label>
      <input id="street-search" name="q" type="search" list="street-names" placeholder="Search a street" autocomplete="off" />
      <button type="submit">Search</button>
    </form>
    <datalist id="street-names"></datalist>
    <p id="search-status"></p>
    <ul id="search-results" hidden></ul>
    <div class="legend" id="legend-row">
      <h2>3.4.1 Excess pavement</h2>
      <div><span style="background:#4c6b58"></span> 0–0.3 m</div>
      <div><span style="background:#c4a35a"></span> 0.3–1.0 m</div>
      <div><span style="background:#c47a3a"></span> 1.0–2.0 m</div>
      <div><span style="background:#b42318"></span> over 2.0 m</div>
    </div>
    <div class="legend" id="legend-pavement" hidden>
      <h2>3.4.3 Condition</h2>
      <div><span style="background:#8a6a28;height:0;border-top:3px dashed #8a6a28"></span> Fair</div>
      <div><span style="background:#7a1f1a;height:0;border-top:3px dashed #7a1f1a"></span> Poor</div>
    </div>
    <div class="legend" id="legend-parking">
      <h2>3.5 Parking</h2>
      <div><span style="background:#1f4e79;width:10px;height:10px;border-radius:50%"></span> Public (TPA)</div>
      <div><span style="background:#5b2c6f;width:10px;height:10px;border-radius:50%"></span> TTC commuter</div>
      <div><span style="background:#2e5a3c;width:10px;height:10px;border-radius:50%"></span> Private off-street</div>
    </div>
    <p style="margin-top:8px;font-size:12px">Click a corridor or marker for details. Source: City of Toronto report · basemap © OpenStreetMap</p>
  </div>
  <div id="map"></div>
  <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
  <script>
    const rowData = ROW_GEOJSON_PLACEHOLDER;
    const pavementData = PAVEMENT_GEOJSON_PLACEHOLDER;
    const parkingData = PARKING_GEOJSON_PLACEHOLDER;
    const map = L.map("map").setView([43.7615, -79.411], 13);
    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
      maxZoom: 19,
      attribution: "&copy; OpenStreetMap"
    }).addTo(map);

    const corridors = [];
    function rowStyle(feat) {
      return { color: feat.properties.color, weight: 7, opacity: 0.85 };
    }
    function pavementStyle(feat) {
      return { color: feat.properties.color, weight: 4, opacity: 1, dashArray: "8 6" };
    }
    function popupHtml(p) {
      if (p.kind === "parking") {
        const spaces = p.spaces == null ? "Not stated" : p.spaces;
        return `<div class="popup">
            <strong>${p.label}</strong>
            <dl>
              <dt>Type</dt><dd>${p.clazz}</dd>
              <dt>Address</dt><dd>${p.address}</dd>
              ${p.location ? `<dt>Report location</dt><dd>${p.location}</dd>` : ""}
              <dt>Spaces</dt><dd>${spaces}${p.structure ? ` · ${p.structure}` : ""}</dd>
              <dt>Occupancy</dt><dd>${p.occupancy}</dd>
              <dt>Table</dt><dd>${p.table}</dd>
            </dl>
            ${p.notes ? `<p>${p.notes}</p>` : ""}
          </div>`;
      }
      if (p.kind === "pavement") {
        return `<div class="popup">
            <strong>${p.label}</strong>
            <dl>
              <dt>Condition</dt><dd>${p.condition} (${p.clazz})</dd>
              <dt>Table</dt><dd>${p.table}</dd>
              <dt>Opportunity</dt><dd>${p.opportunity}</dd>
            </dl>
            ${p.to_note ? `<p>${p.to_note}</p>` : ""}
          </div>`;
      }
      const vary = p.travel_width_varies ? "*" : "";
      return `<div class="popup">
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
          </div>`;
    }

    const rowLayer = L.geoJSON(rowData, {
      style: rowStyle,
      onEachFeature(feat, lyr) {
        lyr.bindPopup(popupHtml(feat.properties));
        corridors.push(lyr);
      }
    }).addTo(map);
    const parkingLayer = L.geoJSON(parkingData, {
      pointToLayer(feat, latlng) {
        const spaces = feat.properties.spaces;
        const radius = spaces ? Math.max(7, Math.min(14, 6 + Math.sqrt(spaces) / 3)) : 9;
        return L.circleMarker(latlng, {
          radius,
          color: "#fff",
          weight: 1,
          fillColor: feat.properties.color,
          fillOpacity: 0.95
        });
      },
      onEachFeature(feat, lyr) {
        lyr.bindPopup(popupHtml(feat.properties));
        corridors.push(lyr);
      }
    }).addTo(map);
    const pavementLayer = L.geoJSON(pavementData, {
      style: pavementStyle,
      onEachFeature(feat, lyr) {
        lyr.bindPopup(popupHtml(feat.properties));
        corridors.push(lyr);
      }
    });

    const rowBounds = rowLayer.getBounds();
    if (rowBounds.isValid()) map.fitBounds(rowBounds, { padding: [40, 40] });

    const names = [...new Set(corridors.map((lyr) => lyr.feature.properties.street || lyr.feature.properties.label))].sort();
    const datalist = document.getElementById("street-names");
    names.forEach((name) => {
      const opt = document.createElement("option");
      opt.value = name;
      datalist.appendChild(opt);
    });

    const statusEl = document.getElementById("search-status");
    const resultsEl = document.getElementById("search-results");
    const toggleRow = document.getElementById("toggle-row");
    const togglePavement = document.getElementById("toggle-pavement");
    const toggleParking = document.getElementById("toggle-parking");

    function layerVisible(lyr) {
      const kind = lyr.feature.properties.kind;
      if (kind === "pavement") return togglePavement.checked;
      if (kind === "parking") return toggleParking.checked;
      return toggleRow.checked;
    }

    function resetStyles() {
      rowLayer.eachLayer((lyr) => lyr.setStyle(rowStyle(lyr.feature)));
      pavementLayer.eachLayer((lyr) => lyr.setStyle(pavementStyle(lyr.feature)));
      parkingLayer.eachLayer((lyr) => {
        const p = lyr.feature.properties;
        lyr.setStyle({ color: "#fff", weight: 1, fillColor: p.color, fillOpacity: 0.95 });
      });
    }

    function focusCorridor(lyr) {
      resetStyles();
      const p = lyr.feature.properties;
      if (p.kind === "parking") {
        lyr.setStyle({ color: "#111", weight: 2, fillColor: "#111", fillOpacity: 1 });
        map.setView(lyr.getLatLng(), 17);
      } else {
        lyr.setStyle({ color: "#111", weight: 9, opacity: 1, dashArray: null });
        lyr.bringToFront();
        const bounds = lyr.getBounds();
        if (bounds.isValid()) map.fitBounds(bounds, { padding: [48, 48], maxZoom: 17 });
      }
      lyr.openPopup();
    }

    function haystack(p) {
      return [p.label, p.street, p.from_street, p.to_street, p.id, p.condition, p.clazz, p.opportunity, p.address, p.operator]
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
      const matches = corridors.filter((lyr) => haystack(lyr.feature.properties).includes(q));
      const hits = matches.filter(layerVisible);
      if (!hits.length) {
        statusEl.textContent = matches.length
          ? `${matches.length} matches are in a layer that is turned off.`
          : `No corridor matches “${query.trim()}”.`;
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
        const p = lyr.feature.properties;
        btn.textContent = p.kind === "pavement"
          ? `${p.label} — ${p.condition}`
          : p.kind === "parking"
            ? `${p.label} (${p.clazz})`
            : p.label;
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
    toggleRow.addEventListener("change", () => {
      if (toggleRow.checked) map.addLayer(rowLayer); else map.removeLayer(rowLayer);
      document.getElementById("legend-row").hidden = !toggleRow.checked;
    });
    togglePavement.addEventListener("change", () => {
      document.getElementById("legend-pavement").hidden = !togglePavement.checked;
      if (!togglePavement.checked) {
        map.removeLayer(pavementLayer);
        return;
      }
      map.addLayer(pavementLayer);
      const bounds = pavementLayer.getBounds();
      if (bounds.isValid()) map.fitBounds(bounds, { padding: [40, 40] });
    });
    toggleParking.addEventListener("change", () => {
      document.getElementById("legend-parking").hidden = !toggleParking.checked;
      if (toggleParking.checked) map.addLayer(parkingLayer); else map.removeLayer(parkingLayer);
    });
  </script>
</body>
</html>
"""


def build_layer(segments: list[dict], nets: dict[str, StreetNet], kind: str) -> dict:
    built = []
    for seg in segments:
        geom = geometry_for(seg, nets)
        npts = sum(len(g) for g in geom)
        print(f"{seg['id']}: {len(geom)} parts, {npts} vertices")
        if geom:
            built.append((seg, geom))
        else:
            print("  WARNING: no geometry")
    return feature_collection(built, kind)


def main() -> None:
    data = overpass_query()
    nets = nets_from_overpass(data)
    print("OSM streets:", {k: len(v.coord) for k, v in sorted(nets.items())})
    print("--- 3.4.1 ROW ---")
    row_fc = build_layer(SEGMENTS, nets, "row")
    print("--- 3.4.3 pavement ---")
    pavement_fc = build_layer(CONDITION_SEGMENTS, nets, "pavement")
    print("--- 3.5 parking ---")
    parking_fc = parking_feature_collection()
    (HERE / "table-3-15.geojson").write_text(json.dumps(row_fc))
    (HERE / "table-3-16-18.geojson").write_text(json.dumps(pavement_fc))
    (HERE / "table-3-21-26.geojson").write_text(json.dumps(parking_fc))
    html = (
        HTML.replace("ROW_GEOJSON_PLACEHOLDER", json.dumps(row_fc))
        .replace("PAVEMENT_GEOJSON_PLACEHOLDER", json.dumps(pavement_fc))
        .replace("PARKING_GEOJSON_PLACEHOLDER", json.dumps(parking_fc))
    )
    (HERE / "index.html").write_text(html)
    print(f"wrote {HERE / 'table-3-15.geojson'}")
    print(f"wrote {HERE / 'table-3-16-18.geojson'}")
    print(f"wrote {HERE / 'table-3-21-26.geojson'}")
    print(f"wrote {HERE / 'index.html'}")


if __name__ == "__main__":
    main()
