"""Street-level furniture and markings. Decoration never participates in wheel collision."""

import hashlib
import math
import random

from shapely import constrained_delaunay_triangles, get_parts, orient_polygons
from shapely.geometry import LineString, Point
from shapely.ops import nearest_points, unary_union

from street_mesh import Frame, number, solids
from survey import is_five, normalized


def tangent(line, s):
    a = line.interpolate(max(0, s - 0.5))
    b = line.interpolate(min(line.length, s + 0.5))
    d = math.hypot(b.x - a.x, b.y - a.y)
    return ((b.x - a.x) / d, (b.y - a.y) / d) if d else (1.0, 0.0)


def stamp_cover(layers, p, z):
    # The lid and cast iron knurling use local (not world-space) UVs.
    radius = 0.32
    center = (p.x, p.y, z)
    for j in range(32):
        angles = [j * math.tau / 32, (j + 1) * math.tau / 32]
        xy = [(math.cos(a), math.sin(a)) for a in angles]
        layers.face(
            "IronCover",
            [center] + [(p.x + radius * x, p.y + radius * y, z) for x, y in xy],
            [(0.5, 0.5)] + [(0.5 + 0.5 * x, 0.5 - 0.5 * y) for x, y in xy],
        )


def shelter_detail(layers, roof, walk, road, obstacles, fid, evidence, eave, base):
    rect = roof.minimum_rotated_rectangle
    if rect.geom_type != "Polygon" or roof.area < 3:
        return
    edges = list(rect.exterior.coords)
    a, b = max(zip(edges, edges[1:]), key=lambda pair: math.dist(*pair))
    along = (b[0] - a[0], b[1] - a[1])
    g = roof.centroid
    frame = Frame(layers, (g.x, g.y, base), along)
    length = math.dist(a, b)
    width = rect.area / length
    # Coated sheet-metal soffit visible from the driving seat.
    for poly in solids(roof):
        for tri in get_parts(constrained_delaunay_triangles(poly)):
            layers.face(
                "CanopyLining",
                [(x, y, base + eave) for x, y in list(orient_polygons(tri).exterior.coords)[:3]][::-1],
            )
    # Folded fascia and narrow drip edge follow the surveyed outline, including concave wings.
    for poly in solids(roof):
        for ring in (poly.exterior, *poly.interiors):
            coords = list(ring.coords)
            for a, b in zip(coords, coords[1:]):
                span = math.dist(a, b)
                if span < 0.4:
                    continue
                edge = Frame(layers, (*a, base), (b[0] - a[0], b[1] - a[1]))
                edge.box("Frame", (span / 2, 0, eave + 0.055), (span, 0.085, 0.11))
                edge.box("RoofMetal", (span / 2, 0, eave - 0.027), (span, 0.062, 0.04))
    usable = roof.difference(road.buffer(0.32)).difference(obstacles)
    count = 0
    bays = max(1, min(24, int(length / 4.4)))
    for i in range(bays):
        x = length * ((i + 0.5) / bays - 0.5)
        cross = LineString([frame.p(x, v, 0)[:2] for v in (-width * 2, width * 2)])
        origin = Point(frame.p(x, 0, 0)[:2])
        spans = get_parts(roof.intersection(cross))
        offsets = []
        for segment in spans:
            if segment.geom_type != "LineString" or segment.length < 0.7:
                continue
            for fraction in [0.5] if segment.length < 4 else [0.23, 0.77]:
                anchor = segment.interpolate(fraction, normalized=True)
                offsets.append((anchor.y - origin.y) * frame.ux - (anchor.x - origin.x) * frame.uy)
        for y in offsets:
            point = Point(frame.p(x, y, 0)[:2])
            if not usable.covers(point.buffer(0.16)):
                continue
            foot = layers.elevation(point.x, point.y) - base + (0.14 if walk.covers(point) else 0)
            frame.tube("Posts", (x, y, foot), (x, y, eave), 0.095, 0.074)
            frame.box("Frame", (x, y, foot + 0.045), (0.30, 0.30, 0.09))
            span = min(width * 0.40, 1.6)
            for side in (-1, 1):
                tip = y + side * span
                if roof.covers(Point(frame.p(x, tip, 0)[:2])):
                    frame.tube("Frame", (x, y, eave - 0.58), (x, tip, eave - 0.09), 0.047, 0.038, 8)
            if roof.covers(frame.rect(x, y, 1.3, 0.16)):
                frame.box("LightPanel", (x, y, eave - 0.045), (1.3, 0.16, 0.07))
            count += 1
    evidence.append(
        {
            "id": fid,
            "detail": "terminal canopy",
            "columns": count,
            "basis": "Roof outline as recorded or identified estimate; soffit, column spacing, luminaires and braces estimated",
        }
    )


def bench(f):
    for y in (-0.17, 0, 0.17):
        f.box("BenchSlat", (0, y, 0.465), (1.62, 0.142, 0.065))
    for z in (0.69, 0.85):
        f.box("BenchSlat", (0, 0.24, z), (1.62, 0.055, 0.11))
    for x in (-0.61, 0.61):
        f.box("Posts", (x, 0, 0.26), (0.075, 0.32, 0.38))
        f.box("Frame", (x, 0.22, 0.60), (0.05, 0.055, 0.5))
        f.box("Frame", (x, 0, 0.055), (0.18, 0.49, 0.08))


def lamp(f):
    f.tube("Posts", (0, 0, 0), (0, 0, 5.48), 0.102, 0.048, 12)
    f.tube("Posts", (0, 0, 5.27), (0, -0.76, 5.67), 0.052, 0.036, 10)
    f.box("SignalHousing", (0, -0.88, 5.68), (0.27, 0.57, 0.11))
    f.box("LightPanel", (0, -0.88, 5.616), (0.21, 0.46, 0.024))


def tree(f, seed, height, planter=False):
    rng = random.Random(int.from_bytes(hashlib.sha256(seed.encode()).digest()[:8], "big"))
    if planter:
        f.box("WallWarm", (0, 0, 0.21), (1.36, 1.16, 0.42))
        f.box("Soil", (0, 0, 0.427), (1.22, 1.02, 0.026))
    else:
        f.box("Soil", (0, 0, 0.012), (1.12, 1.12, 0.024))
    f.tube("TreeTrunk", (0, 0, 0.04), (0.05, 0.04, height * 0.74), 0.105, 0.043, 10)
    for k in range(18):
        a = (k * 0.61803398875 % 1) * math.tau
        level = k / 18
        r = height * (0.24 - 0.14 * level) * rng.uniform(0.8, 1.16)
        x, y = r * math.cos(a), r * math.sin(a)
        z = height * (0.54 + 0.36 * level)
        f.tube("TreeTrunk", (0, 0, z - height * 0.19), (x, y, z), 0.041, 0.015, 6)
        for j in range(3):
            az = a + j * 1.07
            w = height * (0.115 - 0.033 * level)
            dx, dy = math.cos(az) * w, math.sin(az) * w
            # Branch sprays lean out of the vertical, with varying normals and heights.
            spread = 0.30 * height
            cx = x + (j - 1) * 0.14
            f.face(
                "Leaves",
                [
                    (cx - dx, y - dy, z - 0.23),
                    (cx + dx, y + dy, z - 0.23),
                    (cx + dx + 0.22 * math.cos(a), y + dy + 0.22 * math.sin(a), z + spread),
                    (cx - dx + 0.22 * math.cos(a), y - dy + 0.22 * math.sin(a), z + spread),
                ],
                [(0, 1), (1, 1), (1, 0), (0, 0)],
            )


def stop_board(f, bay, is_route):
    f.tube("Posts", (0, 0, 0), (0, 0, 2.48), 0.054, 0.044)
    f.box("StopSign", (0, 0, 2.20), (0.92, 0.105, 0.50))
    f.print_panel(bay - 1 if bay and 1 <= bay <= 10 else 10, 0, -0.056, 2.2, 0.88, 0.45)
    f.box("Frame", (0, 0, 1.29), (0.52, 0.10, 0.68))
    f.print_panel(11 if is_route else 10, 0, -0.055, 1.41, 0.46, 0.235)
    f.box("CanopyLining", (0, -0.057, 1.14), (0.455, 0.016, 0.25))
    # Brushed timetable case and glazing clips; no invented departure times.
    for x in (-0.17, 0.17):
        f.box("Frame", (x, -0.072, 1.22), (0.026, 0.016, 0.038))


def signal(f, arm):
    f.tube("Posts", (0, 0, 0), (0, 0, 5.53), 0.115, 0.061)
    f.tube("Posts", (0, 0, 5.43), (arm, 0, 5.43), 0.065, 0.048)
    # Aim the head along the approach. In Japan green is left, red is right.
    f.box("SignalHousing", (arm, 0, 5.19), (1.11, 0.24, 0.39))
    for x, mat in [(-0.35, "SignalLens"), (0, "AmberLens"), (0.35, "RedLens")]:
        f.tube(mat, (arm + x, -0.12, 5.19), (arm + x, -0.143, 5.19), 0.123, sides=16)
        # Open lower half of the visor leaves the lens visible from a bus below.
        for i in range(6):
            a, b = math.pi * i / 6, math.pi * (i + 1) / 6
            u1, z1 = x + 0.14 * math.cos(a), 5.19 + 0.14 * math.sin(a)
            u2, z2 = x + 0.14 * math.cos(b), 5.19 + 0.14 * math.sin(b)
            f.face(
                "SignalHousing",
                [(arm + u1, -0.12, z1), (arm + u1, -0.28, z1), (arm + u2, -0.28, z2), (arm + u2, -0.12, z2)],
            )


def signed_bay(t):
    for key in ("local_ref", "ref", "platform_code", "name"):
        s = normalized(t.get(key, ""))
        if is_five(s):
            return 5
        if s.isdecimal() and 0 < int(s) <= 10:
            return int(s)
    return None


def decorate(
    layers, records, roads, road, walk, obstacles, shelters, stops, route, board, meta, extent, evidence
):
    """Return the small attribution plaque anchor and yaw alongside the originating stop."""
    focus = (route if route is not None else stops[0]).buffer(115).intersection(extent)
    items = [
        (fid, t, g)
        for fid, t, g, _ in records
        if focus.intersects(g)
        and t.get("layer", "0") in ("0", "")
        and t.get("tunnel", "no") == "no"
        and t.get("bridge", "no") == "no"
    ]

    def nearest(p):
        return min(roads, key=lambda r: r[0].distance(p))

    def surface_z(p):
        return layers.elevation(p.x, p.y) + (0.14 if walk.covers(p) else 0)

    def facing_road(p):
        g = nearest(p)[0]
        s = g.project(p)
        a, b = tangent(g, s)
        q = g.interpolate(s)
        # The front of the panel (-v) faces the carriageway.
        if (q.x - p.x) * b - (q.y - p.y) * a < 0:
            a, b = -a, -b
        return Frame(layers, (p.x, p.y, surface_z(p)), (a, b))

    def record(fid, kind, p, basis):
        evidence.append({"id": fid, "detail": kind, "en_m": [round(p.x, 2), round(p.y, 2)], "basis": basis})

    mapped_lamps = []
    mapped_trees = []
    mapped_covers = []
    bay_points = []
    signals = []
    crossings = []
    for fid, t, g in items:
        if g.geom_type == "Point":
            if t.get("highway") == "street_lamp":
                mapped_lamps.append((fid, g))
            if t.get("natural") == "tree":
                mapped_trees.append((fid, g))
            if t.get("man_made") == "manhole" or "manhole" in t:
                mapped_covers.append((fid, g))
            if t.get("highway") == "traffic_signals":
                signals.append((fid, g))
            if t.get("highway") == "crossing" or t.get("crossing"):
                if t.get("crossing:markings") not in ("no", "unmarked") and t.get("crossing") not in (
                    "no",
                    "unmarked",
                    "informal",
                ):
                    crossings.append((fid, g))
        if t.get("natural") == "tree_row" and g.geom_type == "LineString":
            for s in range(3, int(g.length), 8):
                mapped_trees.append((fid, g.interpolate(s)))
        if (
            t.get("landuse") in ("grass", "flowerbed")
            or t.get("leisure") == "garden"
            or t.get("natural") == "grassland"
        ):
            if g.geom_type in ("MultiPolygon", "Polygon"):
                patch = g.intersection(extent).difference(road.union(walk).union(obstacles))
                layers.extrusion("Planting", patch, 0.006)
        platform = t.get("public_transport") == "platform" or t.get("highway") in ("bus_stop", "platform")
        if platform and g.distance(stops[0]) < 95 and signed_bay(t):
            p = g if g.geom_type == "Point" else nearest_points(g, nearest(g.centroid)[0])[0]
            bay_points.append((fid, signed_bay(t), p))

    for fid, t, g in items:
        if (
            g.geom_type != "LineString"
            or t.get("footway") != "crossing"
            or t.get("crossing:markings") in ("no", "unmarked")
        ):
            continue
        for line, _, _, _ in roads:
            hit = line.intersection(g)
            if (
                hit.geom_type == "Point"
                and not hit.is_empty
                and all(p.distance(hit) > 2 for _, p in crossings)
            ):
                crossings.append((fid, hit))

    # Do not place bodies in the road, turning apron, or against existing buildings.
    free = extent.difference(road.buffer(0.15)).difference(obstacles)
    free_walk = free.intersection(walk)
    occupied = []

    def place_zone(p, r, walk_only=False, max_shift=6):
        available = free_walk if walk_only else free
        if not available.is_empty:
            local = available.intersection(p.buffer(max_shift + r + 0.15)).buffer(-r)
            if not local.is_empty:
                loc = nearest_points(p, local)[1]
                if loc.distance(p) <= max_shift and all(
                    loc.distance(other) > r + prior for other, prior in occupied
                ):
                    occupied.append((loc, r))
                    return loc
        return None

    # Keep surveyed anchors for the headline stop, with a small physical setback from the kerb.
    bay_known = "unverified" not in meta["platform_evidence"]
    start = place_zone(board, 0.53, max_shift=5)
    # Some feeds put the stop at the lane centre, including wide divided roads.
    # Use the nearest edge when it has room, otherwise retain only the source anchor.
    if start is None and not road.is_empty:
        edge = nearest_points(board, road.boundary)[1]
        if board.distance(edge) <= 15:
            start = place_zone(edge, 0.53, max_shift=3)
    board_fits = start is not None
    if not board_fits:
        start = board
    primary = facing_road(start)
    if board_fits:
        stop_board(primary, 5 if bay_known else None, True)
    record(
        meta["platform_evidence"],
        "departure board" if board_fits else "stop anchor only",
        start,
        "Stop anchor from stage survey; cabinet, lettering and setback estimated",
    )
    seen = {5} if bay_known else set()
    for fid, bay, p in sorted(bay_points, key=lambda t: (t[1], t[0])):
        if bay in seen or start.distance(p) < 2.4:
            continue
        loc = place_zone(p, 0.52)
        if loc is not None:
            stop_board(facing_road(loc), bay, False)
            record(fid, "bay " + str(bay), loc, "Mapped bay number; board geometry and setback estimated")
            seen.add(bay)
    if extent.contains(stops[1]) and route is not None and route.distance(stops[1]) < 30:
        loc = place_zone(stops[1], 0.53, max_shift=12)
        if loc is not None:
            # Downstream stop names can differ; the lower panel identifies the line.
            f = facing_road(loc)
            f.tube("Posts", (0, 0, 0), (0, 0, 2.32), 0.052, 0.04)
            f.box("StopSign", (0, 0, 2.05), (0.8, 0.10, 0.42))
            f.print_panel(11, 0, -0.055, 2.05, 0.76, 0.38)
            record(
                meta["stops"][1].get("stop_id", "GTFS"),
                "next stop",
                loc,
                "GTFS stop; pole position and dimensions estimated",
            )

    # Known footprints take precedence; place a shelter estimate at the selected bay only when there
    # is room beside the road. On narrow platforms only the surveyed roof/board will be rendered.
    roof_tags = {fid: tags for fid, tags, _, _ in records if tags.get("building") == "roof"}
    roofs = list(shelters)
    if bay_known and not any(roof.distance(start) < 13 for roof, _, _ in roofs):
        for off in (3.0, -3.0, 0.0):
            shape = primary.rect(off, 1.65, 9.2, 2.65)
            if free.covers(shape) and shape.distance(walk) < 2.5:
                roofs.append(
                    (
                        shape,
                        "estimated/departure-roof",
                        "Bay location corroborated; local roof footprint estimated",
                    )
                )
                break
    hung_board = False
    for roof, fid, basis in roofs:
        clipped = roof.intersection(extent)
        if clipped.is_empty:
            continue
        base = layers.elevation(*clipped.representative_point().coords[0])
        tags = roof_tags.get(fid, {})
        top = number(tags.get("height"), None, 1.5, 50)
        eave = number(tags.get("min_height"), None, 1.0, 48)
        tagged_eave = eave is not None
        if eave is None:
            eave = top - 0.25 if top else 4.2
        if top is None or top <= eave:
            top = eave + 0.25
        layers.extrusion("Shelters", clipped, top, eave, False)
        if clipped.intersects(focus):
            shelter_detail(layers, clipped, walk, road, obstacles, fid, evidence, eave, base)
        # A double-sided suspended bay sign is readable on the approach as well as from the platform.
        # Only install it beneath a nearby evidenced/estimated canopy on pedestrian ground.
        if board_fits and bay_known and not hung_board and eave >= 3.15 and clipped.distance(start) < 6:
            point = Point(primary.p(1.7, 0.25, 0)[:2])
            sign_zone = clipped.intersection(free_walk).buffer(-0.78)
            if not sign_zone.is_empty:
                support = nearest_points(point, sign_zone)[1]
                if point.distance(support) < 4.0:
                    f = Frame(layers, (support.x, support.y, base), (-primary.uy, primary.ux))
                    sign_z = eave - 0.64
                    for x in (-0.41, 0.41):
                        f.tube("Frame", (x, 0, sign_z + 0.23), (x, 0, eave), 0.014, sides=6)
                    f.box("StopSign", (0, 0, sign_z), (1.27, 0.095, 0.50))
                    f.print_panel(4, 0, -0.050, sign_z, 1.23, 0.465)
                    rev = Frame(layers, f.origin, (-f.ux, -f.uy))
                    rev.print_panel(4, 0, -0.050, sign_z, 1.23, 0.465)
                    hung_board = True
                    record(
                        fid,
                        "suspended bay sign",
                        support,
                        "Bay 5 confirmed; hanging sign and placement estimated",
                    )
        evidence.append(
            {
                "id": fid,
                "basis": basis,
                "eave_m": eave,
                "eave_source": "OSM min_height" if tagged_eave else "estimated clearance",
            }
        )
    for offset in (3.0, -3.0, 5.0, -5.0):
        proposed = Point(primary.p(offset, 1.45, 0)[:2])
        loc = place_zone(proposed, 0.99, True, max_shift=1.8)
        if loc is not None:
            bench(facing_road(loc))
            record(
                "estimated/departure-seat", "bench", loc, "Provisional seat on existing pedestrian surface"
            )
            break

    # Markings only on an actual carriageway. Place an inferred stop bar in the inbound
    # half for left-hand traffic, including oneway=-1 ways (normalised by the road builder).
    paint = []
    tactile = []
    if bay_known and board_fits:
        # Short bay end marks belong to the departure side, leaving the through lane clear.
        line, width, _, way = nearest(start)
        at = line.project(start)
        if line.distance(start) <= width / 2 + 3.5:
            # A way may end at the bay. Retain the end mark that fits its documented length.
            for offset in (-6, 6):
                if not 1.4 < at + offset < line.length - 1.4:
                    continue
                q = line.interpolate(at + offset)
                if any(p.distance(q) < 4.5 for _, p in crossings + signals):
                    continue
                f = Frame(layers, (q.x, q.y, 0), tangent(line, at + offset))
                side = 1 if (start.y - q.y) * f.ux - (start.x - q.x) * f.uy > 0 else -1
                v = side * (width / 2 - 0.36)
                paint.extend(
                    [
                        f.rect(0, v - side * 0.33, 0.14, 0.75),
                        f.rect(-math.copysign(0.60, offset), v, 1.34, 0.14),
                    ]
                )
            if paint:
                record(
                    way, "bay end marks", start, "Provisional boarding-bay paint beside corroborated platform"
                )
            # Follow the kerb on the actual footway side even if the GTFS point lies at its end.
            zone = primary.rect(0, 0.4, 13.0, 4.0)
            warning = road.buffer(0.60).difference(road.buffer(0.30)).intersection(zone).intersection(walk)
            if not warning.is_empty:
                tactile.append(warning)
                record(
                    way, "boarding tactile strip", start, "Provisional warning tiles 0.30 m from mapped kerb"
                )

    for fid, p in crossings:
        line, w, _, _ = nearest(p)
        if line.distance(p) > w / 2 + 1:
            continue
        s = line.project(p)
        q = line.interpolate(s)
        f = Frame(layers, (q.x, q.y, 0), tangent(line, s))
        for i in range(-int(w / 2), int(w / 2) + 1):
            paint.append(f.rect(0, i, 3.5, 0.45))
        for side in (-1, 1):
            tactile.append(f.rect(0, side * (w / 2 + 0.46), 2.9, 0.60))
        record(fid, "crosswalk", q, "Mapped crossing; zebra spacing, width and tactile warnings estimated")
        # Use the sign only on uncontrolled crossings, and only where the post fits.
        if not any(g.distance(q) < 10 for _, g in signals):
            loc = place_zone(Point(f.p(-2, w / 2 + 0.65, 0)[:2]), 0.34, True, max_shift=2.5)
            if loc is not None:
                dx, dy = tangent(line, s)
                sf = Frame(layers, (loc.x, loc.y, surface_z(loc)), (dy, -dx))
                sf.tube("Posts", (0, 0, 0), (0, 0, 2.7), 0.038)
                sf.box("Frame", (0, 0, 2.52), (0.50, 0.045, 0.49))
                sf.print_panel(15, 0, -0.025, 2.52, 0.485, 0.475)
                record(fid, "crossing sign", loc, "Estimated roadside sign at mapped crossing")
    for fid, t, g in items:
        if t.get("road_marking") == "stop_line" and g.geom_type == "LineString":
            paint.append(g.buffer(0.20, cap_style="flat"))
            record(fid, "stop line", g.centroid, "Mapped line; paint width estimated")
    reversed_ways = {fid for fid, t, _ in items if t.get("oneway") == "-1"}
    known_bars = [g for _, t, g in items if t.get("road_marking") == "stop_line"]
    for fid, t, p in items:
        if p.geom_type != "Point" or t.get("highway") not in ("traffic_signals", "stop"):
            continue
        nearby = [r for r in roads if r[0].distance(p) < 1.2]
        for line, w, one, way in nearby:
            s = line.project(p)
            for direction in [1] if one else [1, -1]:
                # Signed 'direction' refers to the way orientation before oneway normalisation.
                source_direction = t.get("direction") or t.get("traffic_signals:direction")
                rev = way in reversed_ways
                if source_direction in ("backward", "forward") and (
                    (direction == 1) != ((source_direction == "forward") != rev)
                ):
                    continue
                cross_ahead = [
                    line.project(g)
                    for _, g in crossings
                    if line.distance(g) < 1.4 and 0 <= (s - line.project(g)) * direction <= 12
                ]
                near_s = (
                    min(cross_ahead)
                    if cross_ahead and direction == 1
                    else max(cross_ahead)
                    if cross_ahead
                    else s
                )
                bar_s = near_s - direction * (3.65 if cross_ahead else 4.5)
                if not 0 < bar_s < line.length:
                    continue
                q = line.interpolate(bar_s)
                if any(b.distance(q) < 5 for b in known_bars):
                    continue
                dx, dy = tangent(line, bar_s)
                frame = Frame(layers, (q.x, q.y, 0), (dx * direction, dy * direction))
                width = w if one else w / 2
                stripe = frame.rect(0, 0 if one else w / 4, 0.36, max(0.3, width - 0.35)).intersection(
                    line.buffer(w / 2)
                )
                paint.append(stripe)
                record(
                    fid,
                    "stop line",
                    stripe.centroid,
                    "Estimated approach marking at mapped " + t["highway"] + " on " + way,
                )
    layers.extrusion("Paint", unary_union(paint).intersection(road), 0.024)
    tactile.append(primary.rect(0, 0.30, 2.4, 0.30))
    layers.extrusion("Tactile", unary_union(tactile).intersection(walk), 0.149)

    # Saw-cut expansion joints sized across the existing kerbstone band. The
    # narrow marks at the top of the kerb have no separate collision volumes.
    joints = []
    band = walk.intersection(road.buffer(0.14)).intersection(focus)

    def seam_segments(geometry):
        if geometry.geom_type == "LineString":
            yield geometry
        elif hasattr(geometry, "geoms"):
            for part in geometry.geoms:
                yield from seam_segments(part)

    for edge in seam_segments(walk.boundary.intersection(road.buffer(0.045)).intersection(focus)):
        for i in range(1, int(edge.length / 1.15) + 1):
            s = i * 1.15
            p = edge.interpolate(s)
            d = tangent(edge, s)
            f = Frame(layers, (p.x, p.y, 0), d)
            joints.append(f.rect(0, 0, 0.014, 0.38))
    if joints:
        layers.extrusion("KerbJoint", unary_union(joints).intersection(band), 0.159)
    for fid, p in signals:
        line, w, _, _ = nearest(p)
        q = nearest_points(p, road.boundary)[1] if road.covers(p) else p
        loc = place_zone(q, 0.18, max_shift=3.5)
        if loc is None:
            continue
        s = line.project(p)
        dx, dy = tangent(line, s)
        if route is not None and route.distance(p) < 18:
            rx, ry = tangent(route, route.project(p))
            if dx * rx + dy * ry < 0:
                dx, dy = -dx, -dy
        f = Frame(layers, (loc.x, loc.y, surface_z(loc)), (dy, -dx))
        delta = (p.x - loc.x) * dy - (p.y - loc.y) * dx
        signal(f, 1.45 if delta >= 0 else -1.45)
        record(fid, "signal head", loc, "Mapped signal; post, orientation and static unlit lenses estimated")

    for fid, p in mapped_covers:
        if road.covers(p.buffer(0.34)) or walk.covers(p.buffer(0.34)):
            stamp_cover(layers, p, surface_z(p) + 0.017)
            record(fid, "manhole", p, "Mapped utility node; cast pattern and diameter estimated")
    if not mapped_covers and route is not None:
        for d in range(24, int(min(220, route.length)), 47):
            s = route.interpolate(d)
            line, w, _, _ = nearest(s)
            m = line.project(s)
            dx, dy = tangent(line, m)
            center = line.interpolate(m)
            p = Point(center.x - dy * min(w * 0.23, 1.7), center.y + dx * min(w * 0.23, 1.7))
            if road.covers(p.buffer(0.4)) and all(g.distance(p) > 5 for _, g in crossings + signals):
                stamp_cover(layers, p, layers.elevation(p.x, p.y) + 0.017)
                record("estimated/cover", "manhole", p, "Provisional location and cast pattern")
    for fid, p in mapped_lamps:
        loc = place_zone(p, 0.20, max_shift=3)
        if loc is not None:
            lamp(facing_road(loc))
            record(fid, "street lamp", loc, "Mapped node; pole profile and arm estimated")
    for fid, p in mapped_trees:
        loc = place_zone(p, 1.75, max_shift=2.2)
        if loc is not None:
            tree(facing_road(loc), fid + str(round(p.x)), 4.65)
            record(fid, "tree", loc, "OSM vegetation; species, spacing for rows and crown estimated")
    for offset in (-15.0, 13.0, 36.0):
        p = Point(primary.p(offset, 2, 0)[:2])
        if not any(g.distance(p) < 17 for _, g in mapped_lamps):
            loc = place_zone(p, 0.23, True, max_shift=2.5)
            if loc is not None:
                lamp(facing_road(loc))
                record(
                    "estimated/plaza-light",
                    "street lamp",
                    loc,
                    "Provisional light on existing pedestrian surface",
                )
        p = Point(primary.p(offset + 3, 3.25, 0)[:2])
        if not any(g.distance(p) < 12 for _, g in mapped_trees):
            loc = place_zone(p, 1.48, True, max_shift=2)
            if loc is not None:
                tree(facing_road(loc), str(offset), 3.75, True)
                record(
                    "estimated/plaza-planter",
                    "planted tree",
                    loc,
                    "Provisional planter; footprint fits pedestrian surface",
                )
    return primary
