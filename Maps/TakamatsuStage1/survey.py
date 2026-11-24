"""Read the published feed and OSM XML. All planar coordinates are east/north metres."""

import csv
import io
import math
import re
import unicodedata
import xml.etree.ElementTree as ET
import zipfile
from collections import defaultdict
from datetime import timedelta

from shapely.geometry import LineString, Point, Polygon
from shapely.ops import polygonize, substring, unary_union

ORIGIN = (134.0474, 34.3517)
BBOX = (134.0442, 34.3486, 134.0508, 34.3540)


def project(lon, lat):
    # EN components of the WGS84 ECEF displacement (zero ellipsoidal heights).
    lon0, lat0 = map(math.radians, ORIGIN)
    lon, lat = math.radians(float(lon)), math.radians(float(lat))
    e2 = 6.6943799901413165e-3
    n = 6378137 / math.sqrt(1 - e2 * math.sin(lat) ** 2)
    n0 = 6378137 / math.sqrt(1 - e2 * math.sin(lat0) ** 2)
    dx = n * math.cos(lat) * math.cos(lon - lon0) - n0 * math.cos(lat0)
    dz = (1 - e2) * (n * math.sin(lat) - n0 * math.sin(lat0))
    return n * math.cos(lat) * math.sin(lon - lon0), dz * math.cos(lat0) - dx * math.sin(lat0)


def normalized(value):
    return re.sub(r"[\s()（）・]", "", unicodedata.normalize("NFKC", value)).removeprefix("JR")


def is_five(value):
    return bool(
        re.fullmatch(
            r"(?:高松駅(?:前)?)?(?:バスターミナル)?(?:第)?(?:のりば)?0?5(?:番)?(?:のりば|乗り場|乗場|ホーム|番線)?",
            normalized(value),
        )
    )


def station(name):
    return (
        normalized(name) in ("高松駅", "高松駅前", "高松駅バスターミナル")
        or is_five(name)
        and "高松駅" in name
    )


def active_services(calendar, exceptions, date):
    weekday = ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday")[date.weekday()]
    day = date.strftime("%Y%m%d")
    services = {
        r["service_id"] for r in calendar if r["start_date"] <= day <= r["end_date"] and r[weekday] == "1"
    }
    for r in exceptions:
        if r["date"] == day:
            (services.add if r["exception_type"] == "1" else services.discard)(r["service_id"])
    return services


def read_route(path, today):
    with zipfile.ZipFile(path) as z:

        def rows(name):
            entries = [n for n in z.namelist() if n.split("/")[-1] == name + ".txt" and "__MACOSX" not in n]
            if not entries:
                return []
            if len(entries) != 1:
                raise ValueError("Ambiguous GTFS table: " + name)
            with z.open(entries[0]) as f:
                return list(csv.DictReader(io.TextIOWrapper(f, encoding="utf-8-sig", newline="")))

        stops = {r["stop_id"]: r for r in rows("stops")}
        routes = {r["route_id"]: r for r in rows("routes") if r["route_type"] == "3"}
        trips = {}
        for trip in rows("trips"):
            r = routes.get(trip["route_id"])
            if not r:
                continue
            names = normalized(
                " ".join(
                    [
                        r.get("route_short_name", ""),
                        r.get("route_long_name", ""),
                        trip.get("trip_headsign", ""),
                    ]
                )
            )
            # Never match 147 or another line solely by destination.
            numbers = re.findall(r"(?<!\d)\d{1,3}(?!\d)", names)
            if "47" in numbers or (not numbers and "御厩" in names):
                trips[trip["trip_id"]] = trip
        times = defaultdict(list)
        for r in rows("stop_times"):
            if r["trip_id"] in trips:
                times[r["trip_id"]].append((int(r["stop_sequence"]), r["stop_id"]))
        cal, exc = rows("calendar"), rows("calendar_dates")
        selected = []
        for offset in range(7):
            date = today + timedelta(days=offset)
            service_ids = active_services(cal, exc, date)
            for tid, seq in times.items():
                t = trips[tid]
                if t["service_id"] not in service_ids:
                    continue
                seq.sort()
                if len(seq) < 2 or not station(stops[seq[0][1]]["stop_name"]):
                    continue
                a, b = (stops[sid] for _, sid in seq[:2])
                platform = a.get("platform_code", "")
                if platform and re.search(r"\d", normalized(platform)) and not is_five(platform):
                    continue
                selected.append((tid, a, b, t))
            if selected:
                break
        if not selected:
            raise ValueError("No active outbound Route 47/Mimaya trip from Takamatsu within seven days")
        shapes = defaultdict(list)
        wanted = {t.get("shape_id") for _, _, _, t in selected}
        for r in rows("shapes"):
            if r["shape_id"] in wanted:
                shapes[r["shape_id"]].append(
                    (int(r["shape_pt_sequence"]), project(r["shape_pt_lon"], r["shape_pt_lat"]))
                )
        candidates = []
        for tid, a, b, trip in sorted(selected, key=lambda v: v[0]):
            pos = [Point(project(s["stop_lon"], s["stop_lat"])) for s in (a, b)]
            if pos[0].distance(Point(0, 0)) > 150:
                continue
            coords = shapes.get(trip.get("shape_id"), [])
            line = None
            if len(coords) >= 2:
                shape = LineString([p for _, p in sorted(coords)])
                start, end = (shape.project(p) for p in pos)
                if end - start < 15 or any(shape.distance(p) > 55 for p in pos):
                    continue
                line = substring(shape, start, min(end, start + 550))
            candidates.append((line, pos, a, b, trip, tid))
        if not candidates:
            raise ValueError("No outbound shape agrees with the station and next stop")
        # Prefer explicit platform/shape evidence. Conflicting first legs need a survey.
        candidates.sort(key=lambda c: (c[0] is None, not is_five(c[2].get("platform_code", "")), c[-1]))
        line, pos, a, b, trip, tid = candidates[0]
        for other, pts, _, stop, _, _ in candidates[1:]:
            if (
                stop["stop_name"] != b["stop_name"]
                or pts[0].distance(pos[0]) > 35
                or (line is not None and other is not None and line.hausdorff_distance(other) > 35)
            ):
                raise ValueError("Outbound first legs disagree; inspect GTFS trips before choosing a route")
        meta = dict(
            trip=tid,
            route=trip["route_id"],
            shape=trip.get("shape_id"),
            service_date=date.isoformat(),
            stops=[
                {k: s.get(k, "") for k in ("stop_id", "stop_name", "platform_code", "stop_lon", "stop_lat")}
                for s in (a, b)
            ],
        )
        return line, pos, meta


def osm_features(path):
    root = ET.parse(path).getroot()
    if root.tag != "osm" or root.find("remark") is not None:
        raise ValueError("Expected a complete OSM XML extract")
    nodes, ways, records = {}, {}, []

    def tags(elem):
        return {t.get("k"): t.get("v") for t in elem.findall("tag")}

    for node in root.findall("node"):
        point = project(node.attrib["lon"], node.attrib["lat"])
        nid = node.attrib["id"]
        nodes[nid] = point
        if len(node):
            records.append(("node/" + nid, tags(node), Point(point), ()))
    for way in root.findall("way"):
        refs = [n.attrib["ref"] for n in way.findall("nd")]
        if len(refs) >= 2 and all(r in nodes for r in refs):
            ways[way.attrib["id"]] = (tags(way), LineString([nodes[r] for r in refs]), refs)
    replaced = set()
    for rel in root.findall("relation"):
        t = tags(rel)
        if t.get("type") != "multipolygon" or not any(
            k in t
            for k in (
                "building",
                "building:part",
                "area:highway",
                "highway",
                "public_transport",
                "amenity",
                "landuse",
                "leisure",
            )
        ):
            continue
        members = [
            (m.get("role") or "outer", m.get("ref")) for m in rel.findall("member") if m.get("type") == "way"
        ]
        if any(ref not in ways for _, ref in members):
            continue

        def combine(role):
            return unary_union(list(polygonize([ways[ref][1] for r, ref in members if r == role])))

        poly = combine("outer").difference(combine("inner"))
        if not poly.is_empty:
            records.append(("relation/" + rel.attrib["id"], t, poly, ()))
            replaced.update(ref for role, ref in members if role == "outer")
    for wid, (t, line, refs) in ways.items():
        if not t or wid in replaced:
            continue
        is_area = line.is_ring and (
            t.get("area") == "yes"
            or any(k in t for k in ("area:highway", "building", "building:part", "landuse"))
            or t.get("leisure") == "garden"
            or t.get("natural") == "grassland"
            or t.get("public_transport") == "platform"
            or t.get("highway") == "platform"
        )
        geom = Polygon(line) if is_area else line
        if geom.is_valid:
            records.append(("way/" + wid, t, geom, refs))
    return records


def osm_route_shape(path, records, stops):
    """Read a single direction-consistent chain from a mapped bus relation, without bridging gaps."""
    ways = {
        fid.split("/")[1]: g
        for fid, t, g, _ in records
        if fid.startswith("way/") and g.geom_type == "LineString" and "highway" in t
    }
    alternatives = []
    for rel in ET.parse(path).getroot().findall("relation"):
        tags = {n.attrib["k"]: n.attrib["v"] for n in rel.findall("tag")}
        if tags.get("route") != "bus" or not (
            tags.get("ref") == "47" or (not tags.get("ref") and "御厩" in tags.get("name", ""))
        ):
            continue
        chain = []
        first_length = 0

        def consider():
            if len(chain) < 2:
                return
            line = LineString(chain)
            start, end = [line.project(p) for p in stops]
            if end - start > 15 and all(line.distance(p) < 30 for p in stops):
                alternatives.append(
                    (substring(line, start, min(start + 550, end)), "relation/" + rel.attrib["id"])
                )

        for m in rel.findall("member"):
            if m.get("type") != "way" or m.get("role", "") not in ("", "forward", "backward"):
                continue
            g = ways.get(m.attrib["ref"])
            if g is None:
                consider()
                chain = []
                continue
            points = list(g.coords)
            if m.get("role") == "backward":
                points.reverse()
            if chain and chain[-1] == points[-1]:
                points.reverse()
            if (
                len(chain) > 1
                and chain[0] in (points[0], points[-1])
                and chain[-1] not in (points[0], points[-1])
            ):
                # The very first member can have its native OSM way direction reversed.
                if len(chain) == first_length:
                    chain.reverse()
                    if chain[-1] == points[-1]:
                        points.reverse()
            if chain and chain[-1] != points[0]:
                consider()
                chain = []
            if not chain:
                chain = points
                first_length = len(chain)
            else:
                chain.extend(points[1:])
        consider()
    if alternatives and all(alternatives[0][0].hausdorff_distance(line) < 20 for line, _ in alternatives):
        return alternatives[0]
    return None, None
