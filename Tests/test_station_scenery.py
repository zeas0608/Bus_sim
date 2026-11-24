"""Geographic and rendering regressions for the station. Every synthetic feature stays in this test."""

import json
import struct
import sys
import tempfile
import unittest
from pathlib import Path

from shapely.geometry import LineString, Point, box

MAP = Path(__file__).resolve().parents[1] / "Maps" / "TakamatsuStage1"
sys.path.insert(0, str(MAP))
from architecture import buildings, roof_shell
from street_details import decorate
from surface import Layers, build
from survey import project
from terrain import Elevation, plateau_buildings


class StationSceneryTest(unittest.TestCase):
    def test_landmark_records_do_not_promote_conflicting_or_unlocated_buildings(self):
        civic = json.loads((MAP / "landmarks.json").read_text())["facilities"]
        sites = {r["kind"]: Point(project(r["lon"], r["lat"])) for r in civic}
        station, hotel, tower = (sites[k] for k in ("station", "hotel", "tower"))

        def block(p, radius=11):
            return box(p.x - radius, p.y - radius, p.x + radius, p.y + radius)

        footprints = [
            (block(station), 15, "station", "height"),
            (block(hotel), 44, "hotel", "height"),
            (block(tower, 4), 6, "kiosk", "height"),
            (block(Point(tower.x - 32, tower.y), 11), 140, "shaft", "height"),
        ]
        records = [
            (fid, {"building": "yes", **({"name": "別施設"} if fid == "hotel" else {})}, g, ())
            for g, _, fid, _ in footprints
        ]
        layers, evidence = Layers(Elevation({})), []
        bounds = box(-400, -400, 400, 400)
        buildings(layers, footprints, [], records, bounds, None, Point(0, 0), {}, evidence)
        results = {item["id"]: item for item in evidence}
        self.assertIn("aed_location/11", results["station"]["identity_source"])
        self.assertIsNone(results["hotel"]["landmark"])
        self.assertIsNone(results["kiosk"]["landmark"])
        self.assertIn("inferred", results["shaft"]["identity_source"])
        self.assertIn("SignPrint", layers.finish())
        # A second tall footprint is ambiguous: neither may inherit the tourism record.
        more = (block(Point(tower.x + 35, tower.y), 10), 129, "other", "height")
        records.append(("other", {"building": "yes"}, more[0], ()))
        evidence = []
        buildings(
            Layers(Elevation({})), footprints + [more], [], records, bounds, None, Point(0, 0), {}, evidence
        )
        self.assertFalse(any(e["landmark"] for e in evidence if e["id"] in ("other", "shaft")))

    def test_citygml_pitched_roof_has_relief_and_honours_courtyard_and_ground_datum(self):
        lo, la = 134.0474, 34.3517

        def ring(side, offset, roof=False):
            pts = [
                (offset, offset),
                (offset + side, offset),
                (offset + side, offset + side),
                (offset, offset + side),
                (offset, offset),
            ]
            return " ".join(
                f"{la + y * 0.00001:.8f} {lo + x * 0.00001:.8f} {5 + (8 + 0.15 * x if roof else 0)}"
                for x, y in pts
            )

        def poly(roof):
            return (
                "<g:Polygon>"
                + "".join(
                    f"<g:{k}><g:LinearRing><g:posList>{r}</g:posList></g:LinearRing></g:{k}>"
                    for k, r in [("exterior", ring(12, 0, roof)), ("interior", ring(3, 4, roof))]
                )
                + "</g:Polygon>"
            )

        gml = f'<root xmlns:b="http://www.opengis.net/citygml/building/2.0" xmlns:g="http://www.opengis.net/gml"><g:Envelope srsName="EPSG:6697"/><b:Building g:id="pitched"><b:measuredHeight uom="m">10</b:measuredHeight><b:lod0FootPrint>{poly(False)}</b:lod0FootPrint><b:boundedBy><b:RoofSurface><b:lod2MultiSurface>{poly(True)}</b:lod2MultiSurface></b:RoofSurface></b:boundedBy></b:Building></root>'
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "roof.gml"
            path.write_text(gml)
            faces = {}
            outline, _, fid, _ = plateau_buildings(path, faces)[0]
        layers = Layers(Elevation({}))
        self.assertAlmostEqual(roof_shell(layers, outline, faces[fid], 0), 8, places=3)
        mesh = layers.finish()["RoofMetal"]
        self.assertGreater(max(v[2] for v in mesh["vertices"]) - min(v[2] for v in mesh["vertices"]), 175)
        for i in range(0, len(mesh["triangles"]), 3):
            pts = [mesh["vertices"][idx] for idx in mesh["triangles"][i : i + 3]]
            self.assertTrue(outline.covers(Point(sum(p[1] for p in pts) / 300, sum(p[0] for p in pts) / 300)))
        incomplete = Layers(Elevation({}))
        part = box(*outline.bounds).buffer(-3)
        self.assertIsNone(roof_shell(incomplete, outline, [(part, (0, 0, 9))], 0))
        self.assertEqual(incomplete.finish(), {})

    def test_directed_stop_lines_zebra_and_local_uvs(self):
        east = LineString([(-50, 0), (50, 0)])
        walk = box(-50, 5, 50, 10).union(box(-50, -10, 50, -5))
        items = [
            ("lane", {"oneway": "-1"}, east, ()),
            (
                "signal",
                {"highway": "traffic_signals", "traffic_signals:direction": "backward"},
                Point(4, 0),
                (),
            ),
            ("zebra", {"highway": "crossing"}, Point(6, 0), ()),
            ("unmarked", {"highway": "crossing", "crossing:markings": "no"}, Point(29, 0), ()),
            ("cover", {"manhole": "drain"}, Point(-20, 0), ()),
            ("bay-entry", {"public_transport": "platform", "ref": "3"}, Point(-15, 6), ()),
        ]
        attrs = {"stops": [{}, {}], "platform_evidence": "Station stop only; bay 5 position unverified"}

        def draw(items, line=east.reverse(), one=True):
            evidence = []
            layers = Layers(Elevation({}))
            decorate(
                layers,
                items,
                [(line, 10, one, "lane")],
                east.buffer(5, cap_style="flat"),
                walk,
                box(150, 130, 160, 140),
                [],
                [Point(-30, 6), Point(85, 0)],
                line,
                Point(-30, 6),
                attrs,
                box(-90, -25, 90, 25),
                evidence,
            )
            return layers.finish(), evidence

        meshes, evidence = draw(items)
        bars = [f for f in evidence if f.get("detail") == "stop line"]
        self.assertEqual(len(bars), 1)
        self.assertGreater(bars[0]["en_m"][0], 6)
        self.assertAlmostEqual(bars[0]["en_m"][1], 0, places=3)
        self.assertEqual([f["id"] for f in evidence if f.get("detail") == "crosswalk"], ["zebra"])
        self.assertEqual([f["id"] for f in evidence if f.get("detail") == "manhole"], ["cover"])
        self.assertFalse(any(f.get("detail") == "suspended bay sign" for f in evidence))
        for name in ("SignPrint", "IronCover"):
            self.assertEqual(len(meshes[name]["uv"]), len(meshes[name]["triangles"]))
            self.assertTrue(all(0 <= coord <= 1 for uv in meshes[name]["uv"] for coord in uv))
        self.assertFalse(any(int(u * 4) == 0 and int(v * 4) == 1 for u, v in meshes["SignPrint"]["uv"]))
        # Wrong side of a signed one-way never receives inferred paint.
        items[1] = (
            items[1][0],
            {"highway": "traffic_signals", "traffic_signals:direction": "forward"},
            items[1][2],
            (),
        )
        self.assertFalse(any(f.get("detail") == "stop line" for f in draw(items)[1]))
        # In two-way left-hand traffic the two painted halves are diagonally opposite.
        items[1] = ("signal", {"highway": "traffic_signals"}, Point(4, 0), ())
        bars = [f["en_m"] for f in draw(items, east, False)[1] if f.get("detail") == "stop line"]
        self.assertTrue(any(x < 4 and y > 0 for x, y in bars) and any(x > 4 and y < 0 for x, y in bars))

    def test_roof_above_bay_does_not_fill_driving_clearance(self):
        line = LineString([(-50, 0), (70, 0)])
        roof = box(-13, 3.6, 17, 10)
        items = [
            (
                "way/road",
                {"highway": "busway", "width": "8", "oneway": "yes", "sidewalk": "left"},
                line,
                (1, 2),
            ),
            ("way/bay", {"public_transport": "platform", "ref": "5"}, box(-12, 4.2, 18, 11), ()),
            ("way/roof", {"building": "roof", "layer": "1", "min_height": "4.6", "height": "5"}, roof, ()),
        ]
        meta = {"stops": [{"platform_code": "5"}, {}]}
        plateau = [(roof, 5, "PLATEAU/canopy", "measuredHeight")]
        plan = build(
            items,
            LineString([(-10, 0), (60, 0)]),
            [Point(-6, 4.5), Point(60, 0)],
            meta,
            Elevation({}),
            plateau,
        )
        meshes = plan["meshes"]
        ev = plan["features"]
        self.assertEqual(min(v[2] for v in meshes["Shelters"]["vertices"]), 460)
        self.assertNotIn("Buildings", meshes)
        self.assertTrue(any(e.get("columns", 0) > 0 for e in ev))
        self.assertTrue(any(e.get("eave_source") == "OSM min_height" for e in ev))
        for detail in ("departure board", "suspended bay sign", "bench"):
            e = next(e for e in ev if e.get("detail") == detail)
            self.assertGreater(Point(e["en_m"]).distance(line), 4)
        self.assertTrue(any(e.get("detail") == "bay end marks" for e in ev))

    def test_artwork_manifest_references_valid_rgba_pairs(self):
        spec = json.loads((MAP / "Art/appearance.json").read_text())
        self.assertAlmostEqual(spec["daylight"]["sun_elevation"], 40.4)
        for mat in spec["materials"].values():
            if "tile" in mat:
                self.assertGreater(mat["metres"], 0)
                for suffix in ("_BC", "_N"):
                    raw = (MAP / "Art" / (mat["tile"] + suffix + ".png")).read_bytes()
                    self.assertEqual(raw[:8], b"\x89PNG\r\n\x1a\n")
                    self.assertEqual(struct.unpack(">II", raw[16:24]), (512, 512))
                    self.assertEqual(raw[25], 6 if suffix == "_BC" else 2)
            if "image" in mat:
                self.assertTrue((MAP / "Art" / (mat["image"] + ".png")).is_file())
