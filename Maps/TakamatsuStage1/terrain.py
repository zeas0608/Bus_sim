"""Sample GSI DEM tiles, and optionally an original PLATEAU building CityGML tile."""

import math
import xml.etree.ElementTree as ET

import numpy as np

from shapely.geometry import Polygon, box
from survey import BBOX, ORIGIN, project


def pixels(lon, lat):
    size = 256 * 2**14
    return (lon + 180) / 360 * size, (1 - math.asinh(math.tan(math.radians(lat))) / math.pi) / 2 * size


def tile_ids():
    west, south, east, north = BBOX
    x0, y0 = pixels(west, north)
    x1, y1 = pixels(east, south)
    return [
        (x, y)
        for x in range(int(x0) // 256, int(x1) // 256 + 1)
        for y in range(int(y0) // 256, int(y1) // 256 + 1)
    ]


class Elevation:
    def __init__(self, tiles):
        self.tiles = tiles
        self.x0, self.y0 = pixels(*ORIGIN)
        de, _ = project(ORIGIN[0] + 0.001, ORIGIN[1])
        _, dn = project(ORIGIN[0], ORIGIN[1] + 0.001)
        self.dx = (pixels(ORIGIN[0] + 0.001, ORIGIN[1])[0] - self.x0) / de
        self.dy = (pixels(ORIGIN[0], ORIGIN[1] + 0.001)[1] - self.y0) / dn
        self.variable = bool(tiles)
        self.filled = {}
        self.reference = self.sample(0, 0) if tiles else 0

    def sample(self, e, n):
        # Values describe pixel centres, bilinear interpolation across tile edges.
        x, y = self.x0 + self.dx * e - 0.5, self.y0 + self.dy * n - 0.5
        i, j = math.floor(x), math.floor(y)
        h = 0.0
        for ix, fx in ((i, 1 - (x - i)), (i + 1, x - i)):
            for iy, fy in ((j, 1 - (y - j)), (j + 1, y - j)):
                tile = self.tiles.get((ix // 256, iy // 256))
                raw = tile[iy % 256][ix % 256] if tile is not None else "e"
                if raw == "e":
                    key = ix, iy
                    if key not in self.filled:
                        # Bound nearest-neighbour repair to two DEM pixels; larger holes use the documented flat fallback.
                        neighbours = []
                        for u in range(ix - 2, ix + 3):
                            for v in range(iy - 2, iy + 3):
                                source = self.tiles.get((u // 256, v // 256))
                                if source and source[v % 256][u % 256] != "e":
                                    neighbours.append(
                                        ((ix - u) ** 2 + (iy - v) ** 2, float(source[v % 256][u % 256]))
                                    )
                        if not neighbours:
                            raise ValueError("GSI DEM has no sample inside the extent")
                        self.filled[key] = min(neighbours)[1]
                    raw = self.filled[key]
                h += float(raw) * fx * fy
        return h

    def __call__(self, e, n):
        return self.sample(e, n) - self.reference if self.variable else 0.0


def plateau_buildings(path, roof_faces=None):
    # Japan PLATEAU uses lat,lon,height (JGD2011 + vertical datum, EPSG:6697).
    root = ET.parse(path).getroot()
    ns = {"b": "http://www.opengis.net/citygml/building/2.0", "g": "http://www.opengis.net/gml"}
    envelope = root.find(".//g:Envelope", ns)
    if envelope is None or envelope.get("srsName", "").split("/")[-1].split(":")[-1] != "6697":
        raise ValueError("PLATEAU input requires CityGML 2.0 EPSG:6697")
    extent = box(*project(*BBOX[:2]), *project(*BBOX[2:]))

    def ring(e):
        if e is None or not e.text or e.get("srsDimension", "3") != "3":
            return [], []
        values = list(map(float, e.text.split()))
        if len(values) % 3 or not all(math.isfinite(v) for v in values):
            return [], []
        return [project(lon, lat) for lat, lon in zip(values[::3], values[1::3])], values[2::3]

    def patch(p):
        xy, z = ring(p.find("g:exterior//g:posList", ns))
        if len(xy) < 4:
            return None
        holes = [ring(e)[0] for e in p.findall("g:interior//g:posList", ns)]
        poly = Polygon(xy, [r for r in holes if len(r) >= 4])
        if poly.is_valid and poly.area > 0.05 and poly.intersects(extent):
            return poly, xy, z
        return None

    result = []
    for b in root.findall(".//b:Building", ns):
        height = b.find("b:measuredHeight", ns)
        if height is None or height.get("uom", "m") != "m" or not height.text:
            continue
        h = float(height.text)
        if not 0 < h < 400:
            continue
        candidates = b.findall(".//b:lod0FootPrint//g:Polygon", ns) or b.findall(
            ".//b:GroundSurface//g:Polygon", ns
        )
        if not candidates:
            candidates = b.findall(".//b:lod1Solid//g:Polygon", ns)
        surfaces = []
        for item in candidates:
            face = patch(item)
            if face is not None and face[0].area > 1:
                poly, xy, z = face
                surfaces.append((sum(z) / len(z), poly))
        if not surfaces:
            continue
        fid = "PLATEAU/" + b.get("{" + ns["g"] + "}id", "unknown")
        ground = min(item[0] for item in surfaces)
        for z, poly in surfaces:
            if z - ground < 1:
                result.append((poly, h, fid, "CityGML measuredHeight, LOD footprint"))
        if roof_faces is None:
            continue
        faces = []
        for item in b.findall(".//b:RoofSurface/b:lod2MultiSurface//g:Polygon", ns):
            face = patch(item)
            if face is None:
                continue
            poly, xy, z = face
            coords = np.array([(x, y, 1.0) for x, y in xy])
            levels = np.array(z) - ground
            slope, _, rank, _ = np.linalg.lstsq(coords, levels, rcond=None)
            if (
                rank == 3
                and max(abs(coords @ slope - levels)) < 0.15
                and min(levels) > 1
                and max(levels) < h + 3
            ):
                faces.append((poly, slope))
        if faces:
            roof_faces[fid] = faces
    return result
