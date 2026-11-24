"""Ground-level street surfaces and bus clearance checks. Input data remains inspectable."""

import math
import re
from collections import Counter, defaultdict

from shapely import constrained_delaunay_triangles, get_parts, orient_polygons
from shapely.affinity import rotate
from shapely.geometry import LineString, Point, box
from shapely.ops import nearest_points, substring, unary_union
from survey import BBOX, is_five, project

ROAD_WIDTH = {
    "primary": 11,
    "secondary": 9,
    "tertiary": 7,
    "residential": 5.5,
    "unclassified": 6,
    "service": 5.5,
    "living_street": 5,
    "busway": 4,
    "trunk": 12,
    "road": 6,
}
WALK = {"footway", "pedestrian", "path", "platform", "steps", "cycleway"}

# Stage1 experimental driveability guards, NOT official road geometry.
# A shallow neighbouring ground surface prevents an 18 cm cliff at OSM centreline
# polygons. A separately labelled turning apron supports large bus offtracking
# around nearby mapped junctions, leaving surveyed tagged road widths unchanged.
GROUND_RECOVERY_DROP_M = 0.025
JUNCTION_TURN_APRON_EXTRA_M = 1.75
JUNCTION_FOCUS_RADIUS_M = 12.0


def number(s, default, lo, hi):
    m = re.fullmatch(r"(\d+(?:\.\d+)?)\s*(?:m)?", str(s).strip())
    return float(m[1]) if m and lo <= float(m[1]) <= hi else default


def solids(geometry):
    if geometry.geom_type == "Polygon":
        if not geometry.is_empty and geometry.area > 0.002:
            yield geometry
    elif hasattr(geometry, "geoms"):
        for part in geometry.geoms:
            yield from solids(part)


class Layers:
    def __init__(self, elevation):
        self.data = {}
        self.elevation = elevation

    def face(self, name, points):
        # In EN, counterclockwise top triangles become UE clockwise looking down (+X north).
        mesh = self.data.setdefault(name, {"vertices": [], "triangles": [], "_index": {}})
        ids = []
        for e, n, z in points:
            p = (round(n * 100, 2), round(e * 100, 2), round(z * 100, 2))
            if p not in mesh["_index"]:
                mesh["_index"][p] = len(mesh["vertices"])
                mesh["vertices"].append(p)
            ids.append(mesh["_index"][p])
        if len(set(ids)) == 3:
            mesh["triangles"].extend(ids)

    def extrusion(self, name, geom, top, bottom=None, drape=True):
        for raw in solids(geom):
            poly = orient_polygons(raw)
            altitude = self.elevation if drape else lambda x, y: base
            base = self.elevation(*poly.representative_point().coords[0])
            # Intersect terrain-dependent surfaces with the same grid before triangulating.
            pieces = [poly]
            if drape and self.elevation.variable:
                x0, y0, x1, y1 = poly.bounds
                pieces = (
                    p
                    for x in range(math.floor(x0 / 15), math.floor(x1 / 15) + 1)
                    for y in range(math.floor(y0 / 15), math.floor(y1 / 15) + 1)
                    for p in solids(poly.intersection(box(x * 15, y * 15, (x + 1) * 15, (y + 1) * 15)))
                )
            for piece in pieces:
                for triangle in get_parts(constrained_delaunay_triangles(piece)):
                    ring = orient_polygons(triangle).exterior.coords
                    self.face(name, [(x, y, altitude(x, y) + top) for x, y in list(ring)[:3]])
            if bottom is not None:
                for ring in [poly.exterior, *poly.interiors]:
                    coords = list(ring.coords)
                    for a, b in zip(coords, coords[1:]):
                        za, zb = altitude(*a), altitude(*b)
                        v = [(*a, za + bottom), (*b, zb + bottom), (*b, zb + top), (*a, za + top)]
                        self.face(name, v[:3])
                        self.face(name, [v[0], v[2], v[3]])

    def finish(self):
        return {
            name: {k: v for k, v in m.items() if k != "_index"}
            for name, m in self.data.items()
            if m["triangles"]
        }


def heading(line, s):
    a = line.interpolate(max(0, s - 1))
    b = line.interpolate(min(line.length, s + 1))
    return math.degrees(math.atan2(b.x - a.x, b.y - a.y))


def footprint(p, yaw):
    return rotate(box(p.x - 1.16, p.y - 4.5, p.x + 1.16, p.y + 4.5), -yaw, origin=(p.x, p.y))


def swept_check(route, connected):
    # Treat the source line as an approximate FRONT axle path. Let the rear axle
    # follow with the 1086 rig's 4.40 m wheelbase. This tests geometry, not Chaos.
    a = math.radians(heading(route, 0))
    front = route.interpolate(0)
    rear = Point(front.x - 4.4 * math.sin(a), front.y - 4.4 * math.cos(a))
    crossings = []
    min_clear = float("inf")
    for d in range(0, int(route.length) + 1, 1):
        front = route.interpolate(d)
        dx, dy = front.x - rear.x, front.y - rear.y
        distance = math.hypot(dx, dy)
        if distance < 0.001:
            continue
        rear = Point(front.x - 4.4 * dx / distance, front.y - 4.4 * dy / distance)
        mid = Point((front.x + rear.x) / 2, (front.y + rear.y) / 2)
        body = footprint(mid, math.degrees(math.atan2(dx, dy)))
        if not connected.covers(body):
            crossings.append(d)
        min_clear = min(min_clear, connected.boundary.distance(body))
    return dict(
        sample_m=1,
        wheelbase_m=4.4,
        min_clearance_m=round(min_clear, 2),
        outside_pavement_at_m=crossings,
        assumption="Source line as front axle; provisional 9.0 × 2.32 m body",
    )


def build(records, route, stops, meta, dem, plateau=()):
    extent = box(*project(*BBOX[:2]), *project(*BBOX[2:]))
    roads, walks, islands, tagged_roads, buildings, signs = [], [], [], [], [], []
    platforms, refs, evidence = [], Counter(), []
    node_positions, node_widths = {}, defaultdict(list)
    shelters = []
    lanes, explicit_walks, crossings = [], [], []
    for fid, t, g, ids in records:
        if (
            not g.intersects(extent)
            or t.get("bridge", "no") != "no"
            or t.get("tunnel", "no") != "no"
            or t.get("layer", "0") not in ("0", "")
        ):
            continue
        hw = t.get("highway", "")
        platform = t.get("public_transport") == "platform" or hw in ("bus_stop", "platform")
        if (
            platform
            and any(is_five(t.get(k, "")) for k in ("ref", "local_ref", "name", "platform_code"))
            and g.distance(stops[0]) < 80
        ):
            platforms.append((g.distance(stops[0]), fid, g))
        if g.geom_type == "Point":
            if t.get("amenity") == "shelter" and t.get("shelter_type") == "public_transport":
                shelters.append((g.buffer(1.5), fid, "shelter node, footprint estimate"))
            if hw in ("traffic_signals", "crossing", "bus_stop") or platform:
                signs.append((fid, t, g))
                if hw == "crossing" or t.get("crossing"):
                    crossings.append(g)
            else:
                continue
        elif t.get("building") == "roof" and list(solids(g)):
            shelters.append((g, fid, "mapped roof footprint, 4.2 m clearance estimate"))
        elif "building" in t and t["building"] != "no" and list(solids(g)):
            h = number(t.get("height"), None, 1, 250)
            levels = number(t.get("building:levels"), None, 1, 80)
            buildings.append(
                (
                    g,
                    h or (levels * 3.2 if levels else 8),
                    fid,
                    "height" if h else ("levels × 3.2 m" if levels else "8 m assumption"),
                )
            )
        elif g.geom_type in ("Polygon", "MultiPolygon"):
            kind = t.get("area:highway", hw)
            if kind in WALK or platform or t.get("footway") == "traffic_island":
                islands.append(g)
            elif kind in ROAD_WIDTH:
                tagged_roads.append(g)
            else:
                continue
        elif hw in WALK or platform:
            w = number(t.get("width"), 2.5 if platform else 1.8, 0.5, 20)
            walks.append(g.buffer(w / 2))
        elif hw.removesuffix("_link") in ROAD_WIDTH and t.get("area") != "yes":
            kind = hw.removesuffix("_link")
            count = number(t.get("lanes"), None, 1, 10)
            w = number(t.get("width"), None, 1.5, 60)
            width = w or (count * 3.1 if count else ROAD_WIDTH[kind])
            one = t.get("oneway") in ("yes", "1", "true", "-1") or t.get("junction") == "roundabout"
            # Capture node locations before reversing the one-way line; ids
            # always refer to the source line order, not the travel direction.
            for nid, xy in zip(ids, g.coords):
                node_positions[nid] = Point(xy)
                node_widths[nid].append(width)
            if t.get("oneway") == "-1":
                g = LineString(list(g.coords)[::-1])
            roads.append((g, width, one, fid))
            if count and count >= 2:
                lanes.append((g, width, int(count), ids))
            for nid in set(ids):
                refs[nid] += 1
            if t.get("sidewalk") in ("left", "right", "both"):
                for sign, side in [(1, "left"), (-1, "right")]:
                    if t["sidewalk"] in (side, "both"):
                        shift = -sign if t.get("oneway") == "-1" else sign
                        explicit_walks.append(g.offset_curve(shift * (width / 2 + 0.9)).buffer(0.9))
            evidence.append(
                {
                    "id": fid,
                    "width_m": width,
                    "basis": "width" if w else "lanes × 3.1 m" if count else "class estimate",
                }
            )
        else:
            continue
        evidence.append(
            {
                "id": fid,
                "tags": {
                    k: t[k]
                    for k in (
                        "name",
                        "highway",
                        "public_transport",
                        "ref",
                        "building",
                        "height",
                        "oneway",
                        "area:highway",
                    )
                    if k in t
                },
            }
        )
    if not roads:
        raise ValueError("No ground-level vehicle ways in station extent")
    # OSM-derived asphalt stays distinct from the *estimated* bus turning area.
    # Driving safety must not be represented as a surveyed widening of the road.
    base_pavement = unary_union([g.buffer(w / 2) for g, w, _, _ in roads] + tagged_roads).intersection(extent)
    mapped_islands = unary_union(islands).intersection(extent)
    base_pavement = base_pavement.difference(mapped_islands)
    focus = route.buffer(JUNCTION_FOCUS_RADIUS_M) if route is not None else stops[0].buffer(35)
    junctions = [nid for nid, count in refs.items() if count > 1 and nid in node_positions
                 and focus.intersects(node_positions[nid])]
    # Schematic corner aprons: only at shared OSM nodes near the route.
    # They are a separate material in-game, not claimed as real asphalt.
    apron = unary_union([
        node_positions[nid].buffer(max(node_widths[nid]) / 2 + JUNCTION_TURN_APRON_EXTRA_M)
        for nid in junctions
    ]).intersection(extent).difference(base_pavement).difference(mapped_islands)
    pavement = unary_union([base_pavement, apron])
    walk = unary_union(walks + explicit_walks).difference(pavement).union(mapped_islands).intersection(extent)
    # Positive platform evidence outranks an undifferentiated station stop coordinate.
    platform_geom = min(platforms, key=lambda x: x[0])[2] if platforms else stops[0]
    pos = nearest_points(platform_geom, stops[0])[0]
    if platforms:
        meta["platform_evidence"] = min(platforms, key=lambda x: x[0])[1]
    elif is_five(meta["stops"][0].get("platform_code", "")) or is_five(meta["stops"][0]["stop_name"]):
        meta["platform_evidence"] = "GTFS 5"
    else:
        meta["platform_evidence"] = "Station stop only; bay 5 position unverified"
    if route is not None and not extent.covers(route):
        # Keep only the connected prefix before the first departure from our survey window.
        boundary_crossings = route.intersection(extent.boundary)
        distances = [
            route.project(point) for point in get_parts(boundary_crossings) if point.geom_type == "Point"
        ]
        if not distances or not extent.contains(Point(route.coords[0])) or min(distances) < 15:
            raise ValueError("Route departs the mapped extent before a usable first leg")
        route = substring(route, 0, min(distances))
        meta["end_limit"] = "OSM survey window"
    canopy = unary_union([g for g, _, _ in shelters])
    # LOD1 models can enclose the air underneath a free-standing terminal canopy.
    # Prefer a tagged roof outline there and keep the mapped vehicle clearance below it.
    elevated = [item for item in plateau if canopy.intersection(item[0]).area > 0.6 * item[0].area]
    for item in elevated:
        evidence.append({"id": item[2], "basis": "Overlaps mapped canopy; roof layer supplies clearance"})
    plateau = [item for item in plateau if item not in elevated]
    obstacles = unary_union([item[0] for item in list(plateau) + buildings])
    candidates = []
    for line, w, one, fid in roads:
        if line.distance(pos) > 32:
            continue
        for direction in [1] if one else [1, -1]:
            directed = line if direction == 1 else LineString(list(line.coords)[::-1])
            # Japan uses left-hand traffic; keep an estimated 0.45 m curb clearance.
            track = directed.offset_curve(max(0, w / 2 - 1.61))
            if track.geom_type != "LineString" or track.length < 10:
                continue
            s = min(max(track.project(pos), 4.6), track.length - 4.6)
            p = track.interpolate(s)
            yaw = heading(track, s)
            if not pavement.buffer(0.02).covers(footprint(p, yaw)) or not footprint(p, yaw).disjoint(
                mapped_islands
            ):
                continue
            if not obstacles.is_empty and footprint(p, yaw).intersects(obstacles):
                continue
            if route is not None:
                measure = route.project(p)
                diff = abs((yaw - heading(route, measure) + 180) % 360 - 180)
                if measure > 65 or diff > 65 or route.distance(p) > 22:
                    continue
                score = p.distance(pos) + 0.25 * diff + route.distance(p)
            elif not one:
                continue
            else:
                score = p.distance(pos)
            candidates.append((score, fid, p, yaw))
    if not candidates:
        raise ValueError(
            "No clear 9.0 × 2.32 m departure footprint oriented along observed road; inspect source alignment"
        )
    candidates.sort(key=lambda v: v[0])
    _, fid, spawn, yaw = candidates[0]
    if route is None and (
        not platforms
        or any(
            abs((c[3] - yaw + 180) % 360 - 180) > 45 and c[0] < candidates[0][0] + 3 for c in candidates[1:]
        )
    ):
        raise ValueError("No GTFS shape; need a mapped bay 5 and unambiguous one-way departure")
    pieces = list(solids(pavement))
    connected = next(p for p in pieces if p.buffer(0.03).covers(spawn))
    if route is not None:
        # The shape may follow a centreline instead of the left lane. Record discrepancy rather than painting it as road.
        gaps = [
            round(float(d), 1)
            for d in range(0, int(route.length) + 1, 2)
            if connected.distance(route.interpolate(d)) > 6
        ]
        meta.update(
            shape_length_m=round(route.length, 1),
            off_road_samples_2m=gaps,
            swept_path=swept_check(route, connected),
        )
        if len(gaps) * 2 > max(20, 0.10 * route.length):
            raise ValueError("GTFS and connected road disagree at metres " + str(gaps[:12]))
    else:
        meta["route_status"] = "No published shape; one-way bay departure only. First leg unverified."
    layers = Layers(dem)
    # Land supports wheels just 2.5 cm beneath the road instead of dropping
    # 18 cm outside mapped polygons. OSM sidewalks remain raised and visible.
    layers.extrusion("Land", extent, -GROUND_RECOVERY_DROP_M)
    layers.extrusion("Asphalt", base_pavement, 0)
    layers.extrusion("TurningApron", apron, 0)
    layers.extrusion("Paving", walk, 0.14, 0)
    layers.extrusion("Kerb", walk.intersection(pavement.buffer(0.14)), 0.155)
    junctions = {k for k, v in refs.items() if v > 1}
    dividers = []
    for g, w, count, ids in lanes:
        junction_keepout = unary_union(
            [Point(p).buffer(w * 0.75) for p, i in zip(g.coords, ids) if i in junctions]
        )
        for j in range(1, count):
            stripe = g.offset_curve(w * (j / count - 0.5))
            if stripe.geom_type != "LineString":
                continue
            for s in range(0, int(stripe.length), 8):
                dash = substring(stripe, s, min(s + 3, stripe.length)).buffer(0.075, cap_style="flat")
                dividers.append(dash.difference(junction_keepout))
    for p in crossings:
        g, w, _, _ = min(roads, key=lambda r: r[0].distance(p))
        if g.distance(p) < w / 2 + 1:
            a = heading(g, g.project(p))
            for i in range(-int(w / 2), int(w / 2) + 1):
                rect = box(p.x + i - 0.23, p.y - 1.6, p.x + i + 0.23, p.y + 1.6)
                dividers.append(rotate(rect, -a, origin=(p.x, p.y)))
    layers.extrusion("Paint", unary_union(dividers).intersection(pavement), 0.024)
    for geom, h, fid, basis in list(plateau) + buildings:
        if fid.startswith("way/") or fid.startswith("relation/"):
            if any(geom.intersection(p[0]).area > 0.5 * min(geom.area, p[0].area) for p in plateau):
                continue
        if geom.intersects(extent):
            cropped = geom.intersection(extent)
            layers.extrusion("Buildings", cropped, h, -0.25, False)
            evidence.append({"id": fid, "building_height_m": h, "basis": basis})
    for roof, roof_id, basis in shelters:
        clipped = roof.intersection(extent)
        layers.extrusion("Shelters", clipped, 4.45, 4.2, False)
        evidence.append({"id": roof_id, "basis": basis})
    for fid, t, p in signs:
        if t.get("highway") != "traffic_signals":
            continue
        # Signal nodes often denote the middle of a junction. Move schematic housing to the edge.
        edge = nearest_points(p, pavement.boundary)[1] if pavement.contains(p) else p
        layers.extrusion("Posts", edge.buffer(0.09), 4.3, 0)
        layers.extrusion(
            "SignalHousing", box(edge.x - 0.46, edge.y - 0.17, edge.x + 0.46, edge.y + 0.17), 4.5, 4.12
        )
        # Three unlit lenses; signal phases and surveyed head direction are unavailable.
        for shift in (-0.28, 0, 0.28):
            lens = box(edge.x + shift - 0.09, edge.y + 0.17, edge.x + shift + 0.09, edge.y + 0.20)
            layers.extrusion("SignalLens", lens, 4.40, 4.21)
        evidence.append({"id": fid, "symbol": "signal head/pole arrangement estimated; static"})
    board = nearest_points(pos, pavement.boundary)[1] if pavement.contains(pos) else pos
    layers.extrusion("Posts", board.buffer(0.06), 2.4, 0)
    layers.extrusion("StopSign", board.buffer(0.26), 2.45, 2.05)
    if extent.contains(stops[1]) and route is not None and route.distance(stops[1]) < 30:
        next_board = (
            nearest_points(stops[1], pavement.boundary)[1] if pavement.contains(stops[1]) else stops[1]
        )
        layers.extrusion("Posts", next_board.buffer(0.06), 2.4, 0)
        layers.extrusion("StopSign", next_board.buffer(0.26), 2.45, 2.05)
    meta["route_en_m"] = [[round(e, 2), round(n, 2)] for e, n in route.coords] if route is not None else []
    meta.update(
        spawn_way=candidates[0][1],
        spawn_yaw_deg=round(yaw, 2),
        spawn_clearance_m=round(connected.boundary.distance(footprint(spawn, yaw)), 2),
        road_area_m2=round(base_pavement.area),
        turning_apron_area_m2=round(apron.area, 1),
        estimated_turn_apron_junction_count=len(junctions),
        ground_recovery_drop_m=GROUND_RECOVERY_DROP_M,
        estimated_turn_apron_extra_m=JUNCTION_TURN_APRON_EXTRA_M,
        simulation_turning_note="Temporary bus-friendly junction aprons are not surveyed real-world road widths.",
        footprint_count=len(buildings),
        signal_nodes=sum(t.get("highway") == "traffic_signals" for _, t, _ in signs),
    )
    return {
        "meshes": layers.finish(),
        "spawn": [spawn.y * 100, spawn.x * 100, dem(spawn.x, spawn.y) * 100 + 125, yaw],
        "sign": [board.y * 100, board.x * 100, dem(board.x, board.y) * 100 + 255],
        "survey": meta,
        "features": evidence,
    }
