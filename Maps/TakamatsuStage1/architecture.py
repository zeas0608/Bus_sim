"""Building envelopes retain their survey footprints. Facade fittings are original, estimated artwork."""

import hashlib
import json
import math
from pathlib import Path

from shapely import constrained_delaunay_triangles, get_parts, orient_polygons
from shapely.geometry import LineString, Point
from shapely.ops import unary_union

from street_mesh import Frame, number
from survey import normalized, project


def parts(geom):
    if geom.geom_type == "Polygon" and not geom.is_empty and geom.area > 0.02:
        yield orient_polygons(geom)
    elif hasattr(geom, "geoms"):
        for g in geom.geoms:
            yield from parts(g)


def wall(f, mat, left, right, bottom, top, out):
    if right > left and top > bottom:
        f.face(mat, [(left, -out, bottom), (right, -out, bottom), (right, -out, top), (left, -out, top)])


def station_front(f, length, h):
    """An arched glazed concourse screen, external steel ribs and sheltered entrance."""
    span = min(35, length * 0.94)
    spring = h * 0.61
    crown = h * 0.95
    bays = max(8, min(20, round(span / 1.8)))

    def arch(x):
        return crown - (crown - spring) * (2 * x / span) ** 2

    for i in range(bays):
        x = span * (i / bays - 0.5)
        y = x + span / bays
        bottom = 0.38
        f.face(
            "WindowGlass" if i % 5 != 1 else "WindowShade",
            [(x, -0.13, bottom), (y, -0.13, bottom), (y, -0.13, arch(y)), (x, -0.13, arch(x))],
        )
        f.tube("CanopyLining", (x, -0.26, arch(x)), (y, -0.26, arch(y)), 0.135, sides=10)
        wall(f, "Frame", x - 0.038, x + 0.038, bottom, arch(x), 0.18)
        # The glazing sits behind a projecting arched brow. A folded metal edge casts a real shadow.
        f.face(
            "RoofMetal",
            [
                (x, -0.27, arch(x) + 0.09),
                (x, -1.08, arch(x) + 0.09),
                (y, -1.08, arch(y) + 0.09),
                (y, -0.27, arch(y) + 0.09),
            ],
        )
        f.tube("CanopyLining", (x, -1.09, arch(x)), (y, -1.09, arch(y)), 0.11, sides=10)
        if i % 3 == 0:
            f.tube("Frame", (x, -0.22, arch(x) - 0.55), (x, -1.07, arch(x)), 0.055, sides=8)
    for i in range(1, max(2, int(crown / 1.75))):
        z = i * 1.75
        if z >= crown:
            break
        width = span * min(1, math.sqrt((crown - z) / (crown - spring)))
        wall(f, "Frame", -width / 2, width / 2, z, z + 0.06, 0.19)
    # Raised fascia behind the bilingual lettering, kept within the mapped footprint's frontage.
    hsign = min(2.2, h * 0.18)
    f.box("StopSign", (0, -0.26, spring + 0.18), (min(span * 0.52, hsign * 3.5), 0.16, hsign))
    f.print_panel(12, 0, -0.345, spring + 0.18, min(span * 0.50, hsign * 3.45), hsign * 0.94)
    f.box("RoofMetal", (0, -0.71, 3.12), (span * 0.67, 1.40, 0.13))
    f.box("Frame", (0, -1.38, 3.04), (span * 0.67, 0.085, 0.12))
    for i in range(9):
        u = span * 0.62 * (i / 8 - 0.5)
        f.tube("Frame", (u, -0.20, 3.66), (u, -1.32, 3.17), 0.026, sides=6)
    for x in (-span * 0.19, 0, span * 0.19):
        wall(f, "WindowShade", x - 0.88, x + 0.88, 0.14, 2.76, 0.22)
        f.box("Frame", (x, -0.245, 2.71), (1.81, 0.070, 0.095))
        for jamb in (-0.87, 0, 0.87):
            f.box("Frame", (x + jamb, -0.245, 1.43), (0.05, 0.065, 2.58))
        for leaf in (-0.42, 0.42):
            wall(f, "Blind", x + leaf - 0.38, x + leaf + 0.38, 1.03, 1.075, 0.255)
            f.box("Frame", (x + leaf, -0.267, 0.22), (0.80, 0.038, 0.12))


def facade(f, length, low, top, kind, focal, near, seed, finish):
    # A little depth at the sill and on the mullions reads at driver's eye level.
    wall(f, finish, -length / 2, length / 2, low + 0.02, top, 0.012)
    if kind == "station" and focal and top - low > 5 and length > 10 and low < 1:
        station_front(f, length, top)
        return
    height = top - low
    if length < 2.6 or height < 2.4:
        return
    grid = kind in ("office", "tower", "station")
    floors = max(1, min(42, round(height / (3.8 if grid else 3.15))))
    bays = max(1, min(40, int(length / (2.35 if grid else 3.2))))
    step = length / bays
    for j in range(floors):
        z = low + height * j / floors
        dz = height / floors
        sill = z + dz * (0.14 if grid else 0.28)
        head = z + dz * (0.86 if grid else 0.78)
        if grid:
            wall(f, "Spandrel", -length / 2, length / 2, z + 0.03, sill, 0.028)
        wall(f, "Frame" if grid else finish, -length / 2, length / 2, head, head + 0.085, 0.070)
        for i in range(bays):
            mid = step * (i + 0.5 - bays / 2)
            width = step * (0.92 if grid else 0.60)
            mat = "WindowShade" if (seed + i * 7 + j * 11) % 9 in (0, 1) else "WindowGlass"
            wall(f, mat, mid - width / 2, mid + width / 2, sill, head, 0.046)
            if near:
                wall(f, "Frame", mid - 0.025, mid + 0.025, sill, head, 0.057)
                if (seed + i * 5 + j * 9) % 11 == 0:
                    wall(f, "Blind", mid - width / 2, mid + width / 2, head - dz * 0.16, head, 0.054)
        if near and j == 0 and low < 1 and focal:
            door = min(length * 0.30, 2.6)
            wall(f, "WindowShade", -door / 2, door / 2, 0.12, min(2.66, head), 0.088)
            wall(f, "Frame", -0.035, 0.035, 0.12, min(2.66, head), 0.10)
    if kind in ("tower", "hotel") and focal and length > 7 and low < 1:
        # The two files identify facilities, not a real sign design or installation height.
        hsign = min(1.25, height * 0.12)
        f.box("StopSign", (0, -0.16, 3.6), (min(length * 0.6, 5.5), 0.20, hsign + 0.12))
        f.print_panel(13 if kind == "tower" else 14, 0, -0.265, 3.6, min(length * 0.6 - 0.08, 5.4), hsign)
    if kind == "tower" and height > 65:
        # The city's skyline photograph shows tall contrasting piers and a split crown.
        w = min(1.65, length * 0.072)
        for x in (-length * 0.425, length * 0.425):
            wall(f, "WallWarm", x - w / 2, x + w / 2, low, top, 0.15)
        wall(f, "Frame", -length / 2, length / 2, top - 0.46, top, 0.13)


def roof_shell(layers, outline, roof_faces, base):
    """Use a measured roof only when its projected faces cover this footprint."""
    chosen = []
    for geom, plane in roof_faces:
        clipped = geom.intersection(outline)
        for p in parts(clipped):
            chosen.append((p, plane))
    if not chosen or unary_union([p for p, _ in chosen]).area < 0.985 * outline.area:
        return None
    eave = min(a * x + b * y + c for p, (a, b, c) in chosen for x, y in p.exterior.coords)
    if eave < 2:
        return None
    for p, (a, b, c) in chosen:
        for tri in get_parts(constrained_delaunay_triangles(p)):
            ring = list(orient_polygons(tri).exterior.coords)[:3]
            layers.face("RoofMetal", [(x, y, base + a * x + b * y + c) for x, y in ring])
        for ring in (p.exterior, *p.interiors):
            for (x, y), (u, v) in zip(ring.coords, list(ring.coords)[1:]):
                z, h = a * x + b * y + c, a * u + b * v + c
                if max(z, h) > eave + 0.008:
                    pt = [(x, y, base + eave), (u, v, base + eave), (u, v, base + h), (x, y, base + z)]
                    layers.face("Buildings", pt[:3])
                    layers.face("Buildings", [pt[0], pt[2], pt[3]])
    return eave


def name_kind(tags):
    name = normalized(tags.get("name:ja") or tags.get("name", "")).upper()
    if name in ("高松駅", "高松駅駅舎", "TAKAMATSUSTATION"):
        return "station"
    if "ホテルクレメント高松" in name or "HOTELCLEMENTTAKAMATSU" in name:
        return "hotel"
    if "高松シンボルタワー" in name or "TAKAMATSUSYMBOLTOWER" in name:
        return "tower"
    return None


def buildings(layers, footprints, plateau, records, extent, route, stop, roof_faces, evidence):
    source = json.loads(Path(__file__).with_name("landmarks.json").read_text(encoding="utf-8"))
    anchors = [(Point(project(row["lon"], row["lat"])), row) for row in source["facilities"]]
    tags = {fid: t for fid, t, _, _ in records}
    named_points = [
        (geom, name_kind(t), fid) for fid, t, geom, _ in records if geom.geom_type == "Point" and name_kind(t)
    ]
    # OSM names/colours can augment a PLATEAU envelope covering the same building.
    outlines = []
    for geom, h, fid, basis in plateau:
        overlap = []
        for g, _, oid, _ in footprints:
            if geom.intersects(g):
                area = geom.intersection(g).area
                if area > 0.5 * min(geom.area, g.area):
                    overlap.append((area / geom.union(g).area, oid))
        match = max(overlap)[1] if overlap else None
        outlines.append((geom, h, fid, basis, tags.get(match, {}), 0))
    for geom, h, fid, basis in footprints:
        if any(
            geom.intersects(g) and geom.intersection(g).area > 0.5 * min(geom.area, g.area)
            for g, *_ in plateau
        ):
            continue
        outlines.append((geom, h, fid, basis, tags[fid], 0))

    # Mapped above-ground building parts can carry measured tower/podium heights.
    # Clip each part to its parent and use its actual min_height. Leave uncovered parent space intact.
    pieces = [
        (fid, t, g)
        for fid, t, g, _ in records
        if t.get("building:part") not in (None, "no")
        and g.geom_type in ("Polygon", "MultiPolygon")
        and g.intersects(extent)
    ]
    envelopes = []
    partitioned = set()
    for g, h, fid, basis, t, low in outlines:
        child = []
        if not fid.startswith("PLATEAU/"):
            for pid, pt, pg in pieces:
                if not g.covers(pg.representative_point()):
                    continue
                ph = number(pt.get("height"), None, 1, 300) or 3.2 * number(
                    pt.get("building:levels"), 0, 1, 85
                )
                bottom = number(pt.get("min_height"), None, 0, 290)
                if bottom is None:
                    bottom = 3.2 * number(pt.get("building:min_level"), 0, 0, 80)
                if ph > bottom + 0.5:
                    child.append(
                        (
                            g.intersection(pg),
                            ph,
                            pid,
                            "OSM part height" if "height" in pt else "part levels × 3.2 m",
                            dict(t, **pt),
                            bottom,
                        )
                    )
        if child:
            partitioned.add(fid)
            partitioned.update(p[2] for p in child)
            # A raised section still needs the documented parent's volume below it.
            for pg, _, _, _, _, plow in child:
                if plow > 0:
                    envelopes.append((pg, min(plow, h), fid, basis, t, 0))
            g = g.difference(unary_union([pg for pg, *_ in child]))
            envelopes.extend(child)
        envelopes.append((g, h, fid, basis, t, low))
    tower_anchor = next(p for p, r in anchors if r["kind"] == "tower")
    tower_neighbours = {
        fid
        for g, h, fid, _, _, _ in envelopes
        if h >= 100 and g.distance(tower_anchor) <= 55 and not g.is_empty
    }
    focus = route if route is not None else stop
    for g, h, fid, basis, t, low in envelopes:
        seed = int.from_bytes(hashlib.sha256(fid.encode()).digest()[:4], "big")
        for poly in parts(g.intersection(extent)):
            base = layers.elevation(*poly.representative_point().coords[0])
            named = name_kind(t)
            identity = fid if named else None
            if not named:
                matches = [(kind, oid) for p, kind, oid in named_points if poly.covers(p)]
                if len({k for k, _ in matches}) == 1:
                    named, identity = matches[0]
            civic = [row for pt, row in anchors if poly.covers(pt)]
            # A facility point cannot by itself make a tower out of an unrelated low building.
            if not named and len(civic) == 1 and ("name" not in t or not t["name"]):
                row = civic[0]
                if poly.area > 180 and (row["kind"] == "station" or h >= 12):
                    named = row["kind"]
                    identity = f"Takamatsu City/{row['dataset']}/{row['record']}"
            if not named and tower_neighbours == {fid} and not t.get("name"):
                named = "tower"
                identity = (
                    "Takamatsu City/tourist_facilities/unique neighbouring high-rise; identity inferred"
                )
            material = t.get("building:material", "")
            raw_color = t.get("building:colour", "").lower()
            finish = (
                "WallBrick"
                if material == "brick"
                else "WallWarm"
                if named in ("hotel", "tower")
                else ("WallCool", "WallWhite", "WallWarm")[seed % 3]
            )
            if raw_color in ("white", "ivory", "beige", "brown", "grey", "gray", "silver"):
                finish = {
                    "white": "WallWhite",
                    "ivory": "WallWhite",
                    "beige": "WallWarm",
                    "brown": "WallBrick",
                }.get(raw_color, "WallCool")
            typ = named or ("office" if h > 17 or material == "glass" else "street")
            roof = roof_shell(layers, poly, roof_faces.get(fid, []), base)
            top = h if roof is None else roof
            tiers = [(poly, low, top)]
            podium = False
            if (
                named == "hotel"
                and roof is None
                and fid not in partitioned
                and low == 0
                and top > 30
                and poly.area > 2200
            ):
                inset = min(7.0, math.sqrt(poly.area) * 0.085)
                upper = poly.buffer(-inset, join_style="mitre")
                if upper.geom_type == "Polygon" and upper.area > poly.area * 0.32:
                    split = min(12.0, top * 0.28)
                    tiers = [(poly, 0, split), (orient_polygons(upper), split, top)]
                    podium = True
            for outline, tier_low, tier_top in tiers:
                layers.extrusion("Buildings", outline, tier_top, tier_low if tier_low else -0.25, False)
                if roof is None:
                    layers.extrusion("RoofMetal", outline, tier_top + 0.045, tier_top, False)
                # The top floor and roof are separated from the textured facade by a real coping edge.
                distance = outline.distance(focus)
                if distance < 135 or named:
                    edges = list(outline.exterior.coords)
                    spans = []
                    for a, b in zip(edges, edges[1:]):
                        length = math.dist(a, b)
                        if length < 1.6:
                            continue
                        mid = Point((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)
                        ux, uy = (b[0] - a[0]) / length, (b[1] - a[1]) / length
                        facing = ((stop.x - mid.x) * uy - (stop.y - mid.y) * ux) / max(
                            0.1, mid.distance(stop)
                        )
                        spans.append(
                            (
                                length * (0.1 + max(0, facing)) / (1 + mid.distance(stop) / 70),
                                length,
                                mid,
                                (ux, uy),
                            )
                        )
                    focal = max(range(len(spans)), key=lambda i: spans[i][0]) if spans else -1
                    for i, (_, length, mid, along) in enumerate(spans):
                        if mid.distance(focus) > 155 and not named:
                            continue
                        f = Frame(layers, (mid.x, mid.y, base), along)
                        facade(
                            f,
                            length,
                            tier_low,
                            tier_top,
                            typ,
                            i == focal,
                            mid.distance(focus) < 70,
                            seed + i,
                            finish,
                        )
            evidence.append(
                {
                    "id": fid,
                    "building_height_m": h,
                    "basis": basis,
                    "outline_source": "CityGML" if fid.startswith("PLATEAU/") else "OSM",
                    "roof_source": "PLATEAU LOD2 RoofSurface" if roof is not None else "estimated flat cap",
                    "landmark": named,
                    "estimated_hotel_setback": podium,
                    "identity_source": identity,
                    "wall_colour_tag": raw_color or None,
                    "appearance": "Estimated cladding, fenestration, sign shape and entrance detail",
                }
            )
