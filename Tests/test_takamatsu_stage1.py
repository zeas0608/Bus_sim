"""Offline contract tests. Fixtures are artificial layouts; never used by the installer."""

import csv
import datetime as dt
import io
import json
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "Maps" / "TakamatsuStage1"))
import prepare
from shapely.geometry import LineString, box
from surface import Layers, build
from survey import (
    ORIGIN,
    active_services,
    osm_features,
    osm_route_shape,
    project,
    read_route,
)
from terrain import Elevation, plateau_buildings, tile_ids


def fixture(folder, shape=True, platform="5", road=True):
    lon, lat = ORIGIN
    rows = {
        "routes": [
            ["route_id", "route_short_name", "route_long_name", "route_type"],
            ["r", "47", "御厩線", 3],
        ],
        "trips": [
            ["route_id", "service_id", "trip_id", "shape_id"],
            ["r", "work", "depart", "shape"],
            ["r", "work", "arrive", "back"],
        ],
        "stop_times": [
            ["trip_id", "stop_id", "stop_sequence"],
            ["arrive", "b", 1],
            ["arrive", "a", 2],
            ["depart", "b", 20],
            ["depart", "a", 10],
        ],
        "stops": [
            ["stop_id", "stop_name", "stop_lon", "stop_lat", "platform_code"],
            ["a", "高松駅", lon, lat, platform],
            ["b", "試験停留所", lon + 0.001, lat, ""],
        ],
        "calendar_dates": [["service_id", "date", "exception_type"], ["work", "20261123", "1"]],
    }
    if shape:
        rows["shapes"] = [
            ["shape_id", "shape_pt_lon", "shape_pt_lat", "shape_pt_sequence"],
            ["shape", lon + 0.001, lat, 2],
            ["shape", lon, lat, 1],
        ]
    folder.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(folder / "gtfs_kb.zip", "w") as archive:
        for table, records in rows.items():
            stream = io.StringIO()
            csv.writer(stream).writerows(records)
            archive.writestr(table + ".txt", stream.getvalue().encode("utf-8-sig"))
    root = ET.Element("osm")

    def tag(node, k, v):
        ET.SubElement(node, "tag", k=k, v=v)

    def node(i, x, y, tags=()):
        el = ET.SubElement(root, "node", id=str(i), lon=str(lon + x), lat=str(lat + y))
        for k, v in tags:
            tag(el, k, v)

    def way(i, ids, tags):
        w = ET.SubElement(root, "way", id=str(i))
        for n in ids:
            ET.SubElement(w, "nd", ref=str(n))
        for k, v in tags:
            tag(w, k, v)

    node(1, -0.0002, 0)
    node(2, 0.0005, 0, [("highway", "traffic_signals")])
    node(3, 0.0013, 0)
    node(4, 0.0005, 0.0004)
    node(5, 0, 0.000055, [("public_transport", "platform"), ("ref", "5")])
    if road:
        way(
            10,
            [1, 2],
            [
                ("highway", "service"),
                ("width", "10"),
                ("oneway", "yes"),
                ("lanes", "2"),
                ("sidewalk", "both"),
            ],
        )
        way(11, [2, 3], [("highway", "service"), ("width", "10"), ("oneway", "yes")])
    way(12, [2, 4], [("highway", "residential")])
    relation = ET.SubElement(root, "relation", id="80")
    for i in (10, 11):
        ET.SubElement(relation, "member", type="way", ref=str(i), role="")
    tag(relation, "route", "bus")
    tag(relation, "ref", "47")
    (folder / "station.osm").write_bytes(ET.tostring(root, encoding="utf-8"))
    return folder


class StageTest(unittest.TestCase):
    def test_projection(self):
        self.assertAlmostEqual(project(*ORIGIN)[0], 0, places=6)
        e, n = project(ORIGIN[0] + 0.001, ORIGIN[1] + 0.001)
        self.assertTrue(91 < e < 93 and 110 < n < 112)

    def test_calendar_exceptions(self):
        cal = [dict(service_id="w", start_date="20200101", end_date="20270101", monday="1")]
        self.assertEqual(
            active_services(
                cal, [dict(service_id="w", date="20261123", exception_type="2")], dt.date(2026, 11, 23)
            ),
            set(),
        )

    def test_install_plan(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            fixture(root / "Inputs")
            plan = prepare.run(root, True, dt.date(2026, 11, 23))
            self.assertEqual(plan["survey"]["trip"], "depart")
            self.assertEqual(plan["survey"]["platform_evidence"], "node/5")
            self.assertEqual(plan["survey"]["off_road_samples_2m"], [])
            self.assertAlmostEqual(plan["spawn"][3], 90, places=1)
            self.assertGreater(plan["spawn"][0], 0)  # north side is left on eastbound road
            self.assertEqual(plan["terrain"], "flat estimate")
            self.assertTrue(
                {"Paint", "Paving", "Asphalt", "SignalHousing", "StopSign"} <= plan["meshes"].keys()
            )
            self.assertEqual(json.loads((root / "survey.json").read_text())["survey"]["signal_nodes"], 1)
            self.assertFalse((root / "Content").exists())

    def test_bus_can_recover_off_road_and_turning_apron_is_marked(self):
        # The first Windows Play test found a sharp 18 cm ground drop and
        # insufficient turning room at estimated OSM junctions.
        # Preserve source road widths; allow an expressly provisional apron.
        with tempfile.TemporaryDirectory() as d:
            root = fixture(Path(d))
            route, stops, meta = read_route(root / "gtfs_kb.zip", dt.date(2026, 11, 23))
            records = osm_features(root / "station.osm")
            plan = build(records, route, stops, meta, Elevation({}))
            layers = plan["meshes"]
            self.assertIn("Asphalt", layers)
            self.assertIn("TurningApron", layers)
            self.assertGreater(plan["survey"]["turning_apron_area_m2"], 0)
            self.assertGreater(plan["survey"]["estimated_turn_apron_junction_count"], 0)
            self.assertEqual(plan["survey"]["ground_recovery_drop_m"], 0.025)
            # All sample terrain points sit 2.5cm below the road, not 18cm.
            self.assertEqual({p[2] for p in layers["Land"]["vertices"]}, {-2.5})
            self.assertTrue(all(p[2] == 0 for p in layers["TurningApron"]["vertices"]))
            self.assertIn("not surveyed", plan["survey"]["simulation_turning_note"])

    def test_provisional_width_only_for_route_aligned_missing_tags(self):
        # Do not inflate actual recorded widths or perpendicular side streets.
        with tempfile.TemporaryDirectory() as d:
            root = fixture(Path(d))
            osm = root / "station.osm"
            tree = ET.parse(osm)
            for way in tree.getroot().findall("way"):
                if way.attrib.get("id") in ("10", "11"):
                    for tag in list(way.findall("tag")):
                        if tag.attrib.get("k") == "width":
                            way.remove(tag)
            tree.write(osm, encoding="utf-8")
            plan = prepare.run(root, True, dt.date(2026, 11, 23))
            self.assertIn("WidthEstimate", plan["meshes"])
            survey = plan["survey"]
            self.assertGreater(survey["estimated_width_extra_area_m2"], 0)
            records = {f["id"]: f for f in survey["estimated_width_segments"]}
            self.assertEqual(set(records), {"way/10", "way/11"})
            self.assertEqual(records["way/10"]["source_width_m"], 6.2)
            self.assertEqual(records["way/10"]["playable_estimate_m"], 7.6)
            self.assertEqual(records["way/11"]["source_width_m"], 5.5)
            self.assertEqual(records["way/11"]["playable_estimate_m"], 6.4)
            self.assertIn("provisional", survey["width_reproduction_note"])

    def test_missing_shape_uses_connected_relation(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            fixture(root / "Inputs", shape=False)
            plan = prepare.run(root, True, dt.date(2026, 11, 23))
            self.assertEqual(plan["survey"]["path_source"], "relation/80")
            self.assertGreater(plan["survey"]["shape_length_m"], 90)

    def test_invalid_cache_recovers_online_and_stays_strict_offline(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            cache = root / "Cache"
            cache.mkdir()
            url = "https://example.invalid/station"
            target = cache / "test.txt"
            target.write_text("expired")
            meta = {
                "provider": url,
                "retrieved": "2011-01-01T00:00:00+00:00",
                "sha256": prepare.digest(target),
            }
            (cache / "test.txt.source.json").write_text(json.dumps(meta))

            def current(path):
                if path.read_text() != "valid":
                    raise ValueError("source expired")
                return True

            with self.assertRaisesRegex(ValueError, "expired"):
                prepare.acquire(cache, "test.txt", url, current, root / "manual", True)
            with patch("urllib.request.urlopen", return_value=io.BytesIO(b"valid")):
                value, fresh = prepare.acquire(cache, "test.txt", url, current, root / "manual", False)
            self.assertTrue(value)
            self.assertEqual(fresh["sha256"], prepare.digest(target))

    def test_snapshot_checksum_and_idempotency(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            fixture(root / "Inputs")
            for _ in range(2):
                prepare.run(root, True, dt.date(2026, 11, 23))
                key = (root / "geometry.sha256").read_text()
                if _ == 0:
                    first = key
                self.assertEqual(first, key)
            svg = ET.parse(root / "overview.svg").getroot()
            self.assertTrue(svg.tag.endswith("svg"))

    def test_inactive_and_wrong_bay(self):
        with tempfile.TemporaryDirectory() as d:
            root = fixture(Path(d), platform="6")
            for day in (dt.date(2026, 11, 23), dt.date(2027, 1, 1)):
                with self.assertRaisesRegex(ValueError, "No active outbound"):
                    read_route(root / "gtfs_kb.zip", day)

    def test_disconnected_or_wrong_direction(self):
        with tempfile.TemporaryDirectory() as d:
            root = fixture(Path(d))
            route, stops, meta = read_route(root / "gtfs_kb.zip", dt.date(2026, 11, 23))
            records = osm_features(root / "station.osm")
            reverse = LineString(list(route.coords)[::-1])
            with self.assertRaisesRegex(ValueError, "departure footprint"):
                build(records, reverse, stops, meta, Elevation({}))
            broken = [
                (fid, t, (LineString([(500, 500), (520, 520)]) if fid == "way/11" else g), ids)
                for fid, t, g, ids in records
            ]
            with self.assertRaisesRegex(ValueError, "connected road disagree"):
                build(broken, route, stops, meta, Elevation({}))
            self.assertIsNone(osm_route_shape(root / "station.osm", broken, stops)[0])

    def test_triangulation_hole_and_ue_scale_winding(self):
        layers = Layers(Elevation({}))
        layers.extrusion("Asphalt", box(0, 0, 30, 10).difference(box(5, 2, 8, 8)), 0)
        mesh = layers.finish()["Asphalt"]
        area = 0
        idx = mesh["triangles"]
        for k in range(0, len(idx), 3):
            a, b, c = (mesh["vertices"][i] for i in idx[k : k + 3])
            twice = (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])
            self.assertLess(twice, 0)
            area -= twice / 20000
        self.assertAlmostEqual(area, 282)

    def test_dem_and_plateau(self):
        tile = [["7"] * 256 for _ in range(256)]
        dem = Elevation({k: tile for k in tile_ids()})
        self.assertAlmostEqual(dem(3, 10), 0)
        with tempfile.TemporaryDirectory() as d:
            gml = Path(d) / "37201.gml"
            gml.write_text("""<root xmlns:b="http://www.opengis.net/citygml/building/2.0" xmlns:g="http://www.opengis.net/gml">
            <g:Envelope srsName="http://www.opengis.net/def/crs/EPSG/0/6697"/>
            <b:Building g:id="example"><b:measuredHeight uom="m">16</b:measuredHeight><b:lod1Solid>
            <g:Polygon><g:exterior><g:LinearRing><g:posList>34.3517 134.0474 0 34.3518 134.0474 0 34.3518 134.0475 0 34.3517 134.0474 0</g:posList></g:LinearRing></g:exterior></g:Polygon></b:lod1Solid></b:Building></root>""")
            b = plateau_buildings(gml)
            self.assertEqual(b[0][1:3], (16, "PLATEAU/example"))
            self.assertTrue(45 < b[0][0].area < 57)


if __name__ == "__main__":
    unittest.main()
