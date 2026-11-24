"""Build a local Stage 1 plan from original data. Never writes project Content."""

import argparse
import datetime as dt
import hashlib
import json
import urllib.request
import uuid
import zipfile
from pathlib import Path

from overview import write_overview
from plateau import download_tiles
from surface import build
from survey import BBOX, ORIGIN, osm_features, osm_route_shape, read_route
from terrain import Elevation, plateau_buildings, tile_ids

GTFS = "https://www.kotoden.co.jp/publichtm/gtfs/gtfsdata/latest/gtfs_kb.zip"
OSM = "https://api.openstreetmap.org/api/0.6/map?bbox=" + ",".join(map(str, BBOX))
GSI = "https://cyberjapandata.gsi.go.jp/xyz/dem/14/{}/{}.txt"
PLATEAU = "https://www.geospatial.jp/ckan/dataset/plateau-37201-takamatsu-shi-2022"


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def acquire(folder, name, url, validate, manual, offline):
    path = folder / name
    receipt = folder / (name + ".source.json")
    now = dt.datetime.now(dt.timezone.utc)
    if manual.is_file():
        return validate(manual), dict(file=name, source="local input", provider=url, sha256=digest(manual))

    def cached():
        info = json.loads(receipt.read_text(encoding="utf-8"))
        if info["sha256"] != digest(path) or info["provider"] != url:
            raise ValueError("Cached source checksum/URL mismatch: " + name)
        return validate(path), info

    if path.is_file() and receipt.is_file():
        try:
            value, info = cached()
        except (OSError, ValueError, KeyError, zipfile.BadZipFile):
            if offline:
                raise
            info = None
        if info and (
            offline
            or now - dt.datetime.fromisoformat(info["retrieved"]) < dt.timedelta(days=1)
            or name.startswith("dem-")
        ):
            return value, info
    if offline:
        raise ValueError("Missing local input: " + str(manual))
    temporary = folder / (name + "." + uuid.uuid4().hex + ".part")
    try:
        req = urllib.request.Request(
            url, headers={"User-Agent": "KotodenBusSimulator Stage1/1.0 (github.com/zeas0608/Bus_sim)"}
        )
        with urllib.request.urlopen(req, timeout=25) as response, temporary.open("wb") as out:
            total = 0
            while True:
                chunk = response.read(1024 * 1024)
                if not chunk:
                    break
                total += len(chunk)
                if total > 128 * 1024 * 1024:
                    raise ValueError("Source exceeds stage download limit")
                out.write(chunk)
        value = validate(temporary)
        info = dict(file=name, provider=url, retrieved=now.isoformat(), sha256=digest(temporary))
        temporary.replace(path)
        receipt_temp = temporary.with_suffix(".json.part")
        receipt_temp.write_text(json.dumps(info, indent=2), encoding="utf-8")
        receipt_temp.replace(receipt)
        return value, info
    except (OSError, ValueError, zipfile.BadZipFile) as e:
        if isinstance(e, OSError) and path.is_file() and receipt.is_file():
            value, info = cached()
            return value, dict(info, reused_after=str(e))
        raise RuntimeError(f"{name}: {url}: {e}. Offline file: {manual}") from e
    finally:
        temporary.unlink(missing_ok=True)


def read_tile(path):
    rows = [row.split(",") for row in path.read_text(encoding="ascii").splitlines()]
    if len(rows) != 256 or any(len(row) != 256 for row in rows):
        raise ValueError("Invalid GSI 256x256 elevation tile")
    return rows


def run(saved, offline=False, today=None):
    today = today or dt.datetime.now(dt.timezone(dt.timedelta(hours=9))).date()
    local, cache = saved / "Inputs", saved / "Cache"
    local.mkdir(exist_ok=True, parents=True)
    cache.mkdir(exist_ok=True)

    def fetch(name, url, reader):
        obj, info = acquire(cache, name, url, reader, local / name, offline)
        sources.append(info)
        return obj

    sources = []
    route, stops, survey = fetch("gtfs_kb.zip", GTFS, lambda p: read_route(p, today))

    def read_osm(path):
        features = osm_features(path)
        if route is None:
            return features, osm_route_shape(path, features, stops)
        return features, (route, "GTFS shapes.txt")

    features, (route, basis) = fetch("station.osm", OSM, read_osm)
    survey["path_source"] = basis
    tiles = {}
    warnings = []
    try:
        for x, y in tile_ids():
            tiles[x, y] = fetch(f"dem-{x}-{y}.txt", GSI.format(x, y), read_tile)
        dem = Elevation(tiles)
    except (OSError, ValueError, RuntimeError) as e:
        warnings.append("Flat local datum, GSI unavailable: " + str(e))
        dem = Elevation({})
    plateau = []
    roof_faces = {}
    paths = sorted(local.glob("*.gml"))
    plateau_receipt = cache / "plateau.json"
    if not paths:
        try:
            if plateau_receipt.is_file():
                receipt = json.loads(plateau_receipt.read_text(encoding="utf-8"))
                paths = [cache / Path(name).name for name in receipt["members"]]
                if any(not p.is_file() or digest(p) != receipt["sha256"].get(p.name) for p in paths):
                    raise ValueError("PLATEAU tile checksum failed")
            elif not offline:
                paths, receipt = download_tiles(cache)
                receipt.update(
                    sha256={p.name: digest(p) for p in paths},
                    retrieved=dt.datetime.now(dt.timezone.utc).isoformat(),
                )
                plateau_receipt.write_text(json.dumps(receipt), encoding="utf-8")
            if paths:
                sources.append(receipt)
        except (OSError, ValueError, RuntimeError, KeyError, zipfile.BadZipFile) as e:
            paths = []
            warnings.append("PLATEAU unavailable; OSM footprints used: " + str(e))
    for path in paths:
        result = plateau_buildings(path, roof_faces)
        plateau.extend(result)
        sources.append(dict(file=path.name, provider=PLATEAU, sha256=digest(path), buildings=len(result)))
    try:
        plan = build(features, route, stops, survey, dem, plateau, roof_faces)
    except ValueError as e:
        if "GSI DEM has no sample" not in str(e):
            raise
        warnings.append(str(e) + "; entire stage uses flat local datum")
        dem = Elevation({})
        plan = build(features, route, stops, survey, dem, plateau, roof_faces)
    if dem.filled:
        warnings.append(
            f"GSI voids filled using a neighbouring sample within two pixels per axis: {len(dem.filled)}"
        )
    city_landmarks = [
        f for f in plan["features"] if str(f.get("identity_source", "")).startswith("Takamatsu City/")
    ]
    if city_landmarks:
        civic = json.loads(Path(__file__).with_name("landmarks.json").read_text(encoding="utf-8"))
        sources.append(
            {
                "provider": "https://github.com/takamatsu-city/opendata/tree/" + civic["revision"],
                "license": civic["license"],
                "publisher": civic["publisher"],
                "matches": [f["identity_source"] for f in city_landmarks],
            }
        )
    plan.update(
        schema=1,
        origin_lon_lat=ORIGIN,
        bbox=BBOX,
        prepared_utc=dt.datetime.now(dt.timezone.utc).isoformat(),
        sources=sources,
        warnings=warnings,
        terrain="GSI DEM 10 m" if dem.variable else "flat estimate",
        attribution="© OpenStreetMap contributors (ODbL) | ことでんバス GTFS"
        + (" | 国土地理院 標高タイル" if dem.variable else "")
        + (" | PLATEAU 高松市 2022" if plateau else "")
        + (" | 高松市オープンデータ CC BY 4.0" if city_landmarks else ""),
    )
    art = Path(__file__).resolve().parent / "Art"
    appearance = json.loads((art / "appearance.json").read_text(encoding="utf-8"))
    plan["daylight"] = appearance["daylight"]
    styles = appearance["materials"]
    plan["materials"] = {name: styles[name] for name in plan["meshes"]}
    images = set()
    for spec in plan["materials"].values():
        if "tile" in spec:
            images.update([spec["tile"] + "_BC", spec["tile"] + "_N"])
        if "image" in spec:
            images.add(spec["image"])
    plan["artwork"] = {name: digest(art / (name + ".png")) for name in sorted(images)}
    target = saved / "plan.json"
    temp = saved / ("plan-" + uuid.uuid4().hex + ".tmp")
    temp.write_text(
        json.dumps(plan, ensure_ascii=False, separators=(",", ":"), allow_nan=False), encoding="utf-8"
    )
    temp.replace(target)
    visible = {
        k: plan[k]
        for k in ("meshes", "spawn", "sign", "board_yaw", "attribution", "materials", "artwork", "daylight")
    }
    visible["bay"] = survey["platform_evidence"]
    checksum = hashlib.sha256(json.dumps(visible, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    (saved / "geometry.sha256").write_text(checksum, encoding="ascii")
    write_overview(plan, saved / "overview.svg")
    review = {k: v for k, v in plan.items() if k != "meshes"}
    review["mesh_triangles"] = {k: len(v["triangles"]) // 3 for k, v in plan["meshes"].items()}
    (saved / "survey.json").write_text(json.dumps(review, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Plan: {target}. See survey.json for source evidence, terrain and departure checks.")
    return plan


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--saved", type=Path, required=True)
    parser.add_argument("--offline", action="store_true")
    args = parser.parse_args()
    run(args.saved, args.offline)
