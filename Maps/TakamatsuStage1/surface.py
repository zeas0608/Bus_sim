"""Ground-level street surfaces and bus clearance checks. Input data remains inspectable."""
import math
import re
from collections import Counter
from shapely import constrained_delaunay_triangles, get_parts, orient_polygons
from shapely.affinity import rotate
from shapely.geometry import LineString, Point, Polygon, box
from shapely.ops import nearest_points, unary_union

from survey import BBOX, is_five, project

ROAD_WIDTH = {"primary": 11, "secondary": 9, "tertiary": 7, "residential": 5.5,
              "unclassified": 6, "service": 5.5, "living_street": 5, "busway": 4,
              "trunk": 12, "road": 6}
WALK = {"footway", "pedestrian", "path", "platform", "steps", "cycleway"}


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
            p = (round(n*100, 2), round(e*100, 2), round(z*100, 2))
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
                x0,y0,x1,y1 = poly.bounds
                pieces = (p for x in range(math.floor(x0/15),math.floor(x1/15)+1)
                          for y in range(math.floor(y0/15),math.floor(y1/15)+1)
                          for p in solids(poly.intersection(box(x*15,y*15,(x+1)*15,(y+1)*15))))
            for piece in pieces:
                for triangle in get_parts(constrained_delaunay_triangles(piece)):
                    ring = orient_polygons(triangle).exterior.coords
                    self.face(name, [(x,y,altitude(x,y)+top) for x,y in list(ring)[:3]])
            if bottom is not None:
                for ring in [poly.exterior, *poly.interiors]:
                    coords = list(ring.coords)
                    for a,b in zip(coords,coords[1:]):
                        za, zb = altitude(*a), altitude(*b)
                        v = [(*a,za+bottom), (*b,zb+bottom), (*b,zb+top), (*a,za+top)]
                        self.face(name, v[:3])
                        self.face(name, [v[0],v[2],v[3]])

    def finish(self):
        return {name: {k:v for k,v in m.items() if k != "_index"} for name,m in self.data.items() if m["triangles"]}


def heading(line, s):
    a = line.interpolate(max(0,s-1))
    b = line.interpolate(min(line.length,s+1))
    return math.degrees(math.atan2(b.x-a.x,b.y-a.y))


def footprint(p, yaw):
    return rotate(box(p.x-1.16,p.y-4.5,p.x+1.16,p.y+4.5),-yaw,origin=(p.x,p.y))


def build(records, route, stops, meta, dem, plateau=()):
    extent = box(*project(*BBOX[:2]), *project(*BBOX[2:]))
    roads, walks, islands, tagged_roads, buildings, signs = [], [], [], [], [], []
    platforms, refs, evidence = [], Counter(), []
    lanes, explicit_walks, crossings = [], [], []
    for fid,t,g,ids in records:
        if not g.intersects(extent) or t.get("bridge","no") != "no" or t.get("tunnel","no") != "no" or t.get("layer","0") not in ("0",""):
            continue
        hw = t.get("highway","")
        platform = t.get("public_transport") == "platform" or hw in ("bus_stop","platform")
        if platform and any(is_five(t.get(k,"")) for k in ("ref","local_ref","name","platform_code")) and g.distance(stops[0]) < 80:
            platforms.append((g.distance(stops[0]),fid,g))
        if g.geom_type == "Point":
            if hw in ("traffic_signals","crossing","bus_stop") or platform:
                signs.append((fid,t,g))
                if hw == "crossing" or t.get("crossing"):
                    crossings.append(g)
            else:
                continue
        elif "building" in t and t["building"] != "no" and list(solids(g)):
            h = number(t.get("height"), None, 1, 250)
            levels = number(t.get("building:levels"), None, 1, 80)
            buildings.append((g,h or (levels*3.2 if levels else 8),fid, "height" if h else ("levels × 3.2 m" if levels else "8 m assumption")))
        elif g.geom_type in ("Polygon","MultiPolygon"):
            kind = t.get("area:highway",hw)
            if kind in WALK or platform or t.get("footway") == "traffic_island":
                islands.append(g)
            elif kind in ROAD_WIDTH:
                tagged_roads.append(g)
            else:
                continue
        elif hw in WALK or platform:
            w = number(t.get("width"), 2.5 if platform else 1.8, 0.5, 20)
            walks.append(g.buffer(w/2))
        elif hw.removesuffix("_link") in ROAD_WIDTH and t.get("area") != "yes":
            kind = hw.removesuffix("_link")
            count = number(t.get("lanes"),None,1,10)
            w = number(t.get("width"), None, 1.5, 60)
            width = w or (count*3.1 if count else ROAD_WIDTH[kind])
            one = t.get("oneway") in ("yes","1","true","-1") or t.get("junction") == "roundabout"
            if t.get("oneway") == "-1":
                g = LineString(list(g.coords)[::-1])
            roads.append((g,width,one,fid))
            if count and count >= 2:
                lanes.append((g,width,int(count),ids))
            for nid in set(ids):
                refs[nid] += 1
            if t.get("sidewalk") in ("left","right","both"):
                for sign,side in [(1,"left"),(-1,"right")]:
                    if t["sidewalk"] in (side,"both"):
                        shift = -sign if t.get("oneway") == "-1" else sign
                        explicit_walks.append(g.offset_curve(shift*(width/2+0.9)).buffer(0.9))
            evidence.append({"id":fid,"width_m":width,"basis":"width" if w else "lanes × 3.1 m" if count else "class estimate"})
        else:
            continue
        evidence.append({"id":fid, "tags":{k:t[k] for k in ("name","highway","public_transport","ref","building","height","oneway","area:highway") if k in t}})
    if not roads:
        raise ValueError("No ground-level vehicle ways in station extent")
    pavement = unary_union([g.buffer(w/2) for g,w,_,_ in roads]+tagged_roads).intersection(extent)
    mapped_islands = unary_union(islands).intersection(extent)
    pavement = pavement.difference(mapped_islands)
    walk = unary_union(walks+explicit_walks).difference(pavement).union(mapped_islands).intersection(extent)
    # Positive platform evidence outranks an undifferentiated station stop coordinate.
    platform_geom = min(platforms,key=lambda x:x[0])[2] if platforms else stops[0]
    pos = nearest_points(platform_geom, stops[0])[0]
    if platforms:
        meta["platform_evidence"] = min(platforms,key=lambda x:x[0])[1]
    elif is_five(meta["stops"][0].get("platform_code","")) or is_five(meta["stops"][0]["stop_name"]):
        meta["platform_evidence"] = "GTFS 5"
    else:
        meta["platform_evidence"] = "Station stop only; bay 5 position unverified"
    candidates = []
    for line,w,one,fid in roads:
        if line.distance(pos)>32:
            continue
        for direction in ([1] if one else [1,-1]):
            directed = line if direction == 1 else LineString(list(line.coords)[::-1])
            # Japan uses left-hand traffic; keep an estimated 0.45 m curb clearance.
            track = directed.offset_curve(max(0,w/2-1.61))
            if track.geom_type != "LineString" or track.length < 10:
                continue
            s = min(max(track.project(pos),4.6),track.length-4.6)
            p = track.interpolate(s)
            yaw = heading(track,s)
            if not pavement.buffer(.02).covers(footprint(p,yaw)) or not footprint(p,yaw).disjoint(mapped_islands):
                continue
            if route is not None:
                measure = route.project(p)
                diff = abs((yaw-heading(route,measure)+180)%360-180)
                if diff > 65 or route.distance(p)>22:
                    continue
                score = p.distance(pos)+0.25*diff+route.distance(p)
            elif not one:
                continue
            else:
                score = p.distance(pos)
            candidates.append((score,fid,p,yaw))
    if not candidates:
        raise ValueError("No clear 9.0 × 2.32 m departure footprint oriented along observed road; inspect source alignment")
    candidates.sort(key=lambda v:v[0])
    _, fid, spawn, yaw = candidates[0]
    if route is None and (not platforms or any(abs((c[3]-yaw+180)%360-180)>45 and c[0]<candidates[0][0]+3 for c in candidates[1:])):
        raise ValueError("No GTFS shape; need a mapped bay 5 and unambiguous one-way departure")
    pieces = list(solids(pavement))
    connected = next(p for p in pieces if p.buffer(.03).covers(spawn))
    if route is not None:
        # The shape may follow a centreline instead of the left lane. Record discrepancy rather than painting it as road.
        gaps = [round(float(d),1) for d in range(0,int(route.length)+1,2) if connected.distance(route.interpolate(d))>6]
        meta.update(shape_length_m=round(route.length,1), off_road_samples_2m=gaps)
        if len(gaps)*2 > max(20,0.10*route.length):
            raise ValueError("GTFS and connected road disagree at metres "+str(gaps[:12]))
    else:
        meta["route_status"] = "No published shape; one-way bay departure only. First leg unverified."
    layers = Layers(dem)
    layers.extrusion("Land",extent,-0.18)
    layers.extrusion("Asphalt",pavement,0)
    layers.extrusion("Paving",walk,0.14,0)
    layers.extrusion("Kerb",walk.intersection(pavement.buffer(0.14)),0.155)
    junctions = {k for k,v in refs.items() if v>1}
    dividers = []
    for g,w,count,ids in lanes:
        junction_keepout = unary_union([Point(p).buffer(w*.75) for p,i in zip(g.coords,ids) if i in junctions])
        for j in range(1,count):
            stripe = g.offset_curve(w*(j/count-.5))
            if stripe.geom_type != "LineString":
                continue
            from shapely.ops import substring
            for s in range(0,int(stripe.length),8):
                dash = substring(stripe,s,min(s+3,stripe.length)).buffer(.075,cap_style="flat")
                dividers.append(dash.difference(junction_keepout))
    for p in crossings:
        g,w,_,_ = min(roads,key=lambda r:r[0].distance(p))
        if g.distance(p) < w/2+1:
            a = heading(g,g.project(p))
            for i in range(-int(w/2),int(w/2)+1):
                rect = box(p.x+i-.23,p.y-1.6,p.x+i+.23,p.y+1.6)
                dividers.append(rotate(rect,-a,origin=(p.x,p.y)))
    layers.extrusion("Paint",unary_union(dividers).intersection(pavement),0.024)
    for geom,h,fid,basis in list(plateau)+buildings:
        if fid.startswith("way/") or fid.startswith("relation/"):
            if any(geom.intersection(p[0]).area > .5*min(geom.area,p[0].area) for p in plateau):
                continue
        if geom.intersects(extent):
            cropped = geom.intersection(extent)
            layers.extrusion("Buildings",cropped,h,-.25,False)
            evidence.append({"id":fid,"building_height_m":h,"basis":basis})
    for fid,t,p in signs:
        if t.get("highway") != "traffic_signals":
            continue
        # Signal nodes often denote the middle of a junction. Move schematic housing to the edge.
        edge = nearest_points(p, pavement.boundary)[1] if pavement.contains(p) else p
        layers.extrusion("Posts",edge.buffer(.09),4.3,0)
        layers.extrusion("SignalHousing",box(edge.x-.46,edge.y-.17,edge.x+.46,edge.y+.17),4.5,4.12)
        evidence.append({"id":fid,"symbol":"signal head/pole arrangement estimated; static"})
    board = nearest_points(pos,pavement.boundary)[1] if pavement.contains(pos) else pos
    layers.extrusion("Posts",board.buffer(.06),2.4,0)
    layers.extrusion("StopSign",board.buffer(.26),2.45,2.05)
    meta.update(spawn_way=candidates[0][1], spawn_yaw_deg=round(yaw,2),
                spawn_clearance_m=round(connected.boundary.distance(footprint(spawn,yaw)),2),
                road_area_m2=round(pavement.area), footprint_count=len(buildings), signal_nodes=sum(t.get("highway")=="traffic_signals" for _,t,_ in signs))
    return {"meshes":layers.finish(),"spawn":[spawn.y*100,spawn.x*100,dem(spawn.x,spawn.y)*100+125,yaw],
            "sign":[board.y*100,board.x*100,dem(board.x,board.y)*100+255], "survey":meta,"features":evidence}
