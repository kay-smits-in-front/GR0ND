"""Maak gr0nd/data/nederland_rd.json: de omtrek van Nederland in RD New (meters).

Gebruik (eenmalig, uit de projectmap):
    mkdir /tmp/wa && cd /tmp/wa && npm install world-atlas@2.0.2
    uv run python scripts/maak_nederland.py /tmp/wa/node_modules/world-atlas/countries-10m.json

Bron: Natural Earth via world-atlas (publiek domein). De omtrek is bedoeld voor het overzicht,
niet voor metingen. Transformatie: pyproj WGS 84 naar EPSG:28992 zonder rasterbestand.
"""

import json
import sys
from pathlib import Path

from pyproj import Transformer

UITVOER = Path(__file__).parent.parent / "gr0nd" / "data" / "nederland_rd.json"
NEDERLAND_ID = "528"  # ISO 3166-1 numeriek
EUROPA = (3.0, 50.6, 7.6, 53.8)  # lon_min, lat_min, lon_max, lat_max: sluit Caribische delen uit
TOLERANTIE_M = 150.0


def lees_topologie(pad: Path) -> dict:
    """Lees het TopoJSON-bestand."""
    return json.loads(pad.read_text())


def decodeer_bogen(topologie: dict) -> list[list[tuple[float, float]]]:
    """Zet de delta-gecodeerde bogen om in lon/lat-lijsten."""
    schaal = topologie["transform"]["scale"]
    verschuiving = topologie["transform"]["translate"]
    bogen = []
    for boog in topologie["arcs"]:
        x = y = 0
        punten = []
        for dx, dy in boog:
            x += dx
            y += dy
            punten.append((x * schaal[0] + verschuiving[0], y * schaal[1] + verschuiving[1]))
        bogen.append(punten)
    return bogen


def bouw_ring(boog_indexen: list[int], bogen: list[list[tuple[float, float]]]) -> list:
    """Plak bogen aan elkaar tot één ring. Een negatieve index betekent omgekeerd (~i)."""
    ring: list[tuple[float, float]] = []
    for index in boog_indexen:
        punten = bogen[~index][::-1] if index < 0 else bogen[index]
        ring.extend(punten if not ring else punten[1:])
    return ring


def vind_nederland(topologie: dict) -> list[list[list[int]]]:
    """Geef de polygonen (elk een lijst ringen van boogindexen) van Nederland."""
    for geometrie in topologie["objects"]["countries"]["geometries"]:
        if geometrie.get("id") == NEDERLAND_ID:
            if geometrie["type"] == "Polygon":
                return [geometrie["arcs"]]
            return geometrie["arcs"]
    raise SystemExit("Nederland niet gevonden in het bestand.")


def ligt_in_europa(ring: list[tuple[float, float]]) -> bool:
    """Alleen ringen waarvan het eerste punt in Europees Nederland ligt."""
    lon, lat = ring[0]
    return EUROPA[0] <= lon <= EUROPA[2] and EUROPA[1] <= lat <= EUROPA[3]


def vereenvoudig(ring: list[tuple[float, float]]) -> list[list[float]]:
    """Laat punten weg die minder dan TOLERANTIE_M van het vorige behouden punt liggen."""
    behouden = [ring[0]]
    for punt in ring[1:-1]:
        dx, dy = punt[0] - behouden[-1][0], punt[1] - behouden[-1][1]
        if (dx * dx + dy * dy) ** 0.5 >= TOLERANTIE_M:
            behouden.append(punt)
    behouden.append(ring[0])
    return [[round(x, 1), round(y, 1)] for x, y in behouden]


def main(pad: Path) -> None:
    topologie = lees_topologie(pad)
    bogen = decodeer_bogen(topologie)
    naar_rd = Transformer.from_crs("EPSG:4326", "EPSG:28992", always_xy=True)
    polygonen = []
    for polygoon in vind_nederland(topologie):
        buitenring = bouw_ring(polygoon[0], bogen)
        if not ligt_in_europa(buitenring):
            continue
        rd = [naar_rd.transform(lon, lat) for lon, lat in buitenring]
        polygonen.append(vereenvoudig(rd))
    UITVOER.parent.mkdir(parents=True, exist_ok=True)
    UITVOER.write_text(json.dumps({"crs": "EPSG:28992", "polygonen": polygonen}))
    punten = sum(len(p) for p in polygonen)
    print(f"{len(polygonen)} polygonen, {punten} punten geschreven naar {UITVOER}")


if __name__ == "__main__":
    main(Path(sys.argv[1]))
