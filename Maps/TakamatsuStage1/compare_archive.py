"""Independent historical cross-check. Does not write Unreal content or supply its inputs."""

import argparse
import json
import statistics
import zipfile
from pathlib import Path

from shapely.geometry import LineString, box, shape
from shapely.ops import substring, transform, unary_union
from survey import BBOX, project


def compare(n07, tak, exercise=False, figure=None):
    survey = json.loads(n07.read_text(encoding="utf-8-sig"))
    candidates = [
        f
        for f in survey["features"]
        if f["properties"]["N07_003"] == "御厩・県立プール線47" and "ことでん" in f["properties"]["N07_002"]
    ]
    if len(candidates) != 1:
        raise ValueError("Expected one historic 47 feature; check release and prefecture")
    line = LineString([project(*p[:2]) for p in candidates[0]["geometry"]["coordinates"]])
    line = substring(line, 0, 420)
    with zipfile.ZipFile(tak) as z:
        roads = json.load(z.open("roads.geojson"))
    region = box(*BBOX)
    known = []
    for f in roads["features"]:
        if f["properties"].get("structure") != "normal":
            continue
        road = shape(f["geometry"])
        if road.intersects(region):
            known.append(transform(project, road.intersection(region)))
    net = unary_union(known)
    samples = [net.distance(line.interpolate(m)) for m in range(0, 421, 5)]

    def stats(values):
        return {
            "n": len(values),
            "median_m": round(statistics.median(values), 1),
            "max_m": round(max(values), 1),
        }

    result = {
        "source_features": len(known),
        "sample_interval_m": 5,
        "first_0_to_80_m": stats(samples[:17]),
        "street_90_to_420_m": stats(samples[18:]),
        "distances_m": [round(d, 1) for d in samples],
    }

    if figure:
        draw_comparison(known, samples, figure)
    if exercise:
        from surface import build
        from terrain import Elevation

        # Start on the corroborated public street. Bay roads/widths/lanes are missing in this extract.
        # This isolated QA run deliberately cannot be selected by the Windows installer.
        tracks = []
        for i, geom in enumerate(known):
            for segment in getattr(geom, "geoms", [geom]):
                if segment.geom_type == "LineString":
                    tracks.append((f"archive/{i}", {"highway": "unclassified"}, segment, ()))
        leg = substring(line, 90, 420)
        stops = [leg.interpolate(0), leg.interpolate(leg.length)]
        meta = {"stops": [{"stop_name": "historic corridor QA"}, {}], "path_source": "historic Route 47 QA"}
        plan = build(tracks, leg, stops, meta, Elevation({}))
        result["offline_mesh_check"] = {
            "street_triangles": len(plan["meshes"]["Asphalt"]["triangles"]) // 3,
            "connected_area_m2": plan["survey"]["road_area_m2"],
            "off_road_samples_2m": len(plan["survey"]["off_road_samples_2m"]),
            "qa_length_m": plan["survey"]["shape_length_m"],
        }
    return result


def draw_comparison(roads, samples, path):
    import matplotlib

    matplotlib.use("Agg")
    from matplotlib import pyplot as plt
    from matplotlib.collections import LineCollection
    from matplotlib.patches import Circle

    fig, (ax, chart) = plt.subplots(1, 2, figsize=(10, 5.1), gridspec_kw={"width_ratios": [1.05, 1]})
    fig.subplots_adjust(left=0.065, right=0.97, bottom=0.18, top=0.82, wspace=0.3)
    fig.suptitle("Takamatsu Station  /  Route 47 archive check", x=0.065, ha="left", fontsize=18)
    segments = [
        list(line.coords)
        for road in roads
        for line in getattr(road, "geoms", [road])
        if line.geom_type == "LineString"
    ]
    ax.add_collection(LineCollection(segments, colors="#465961", linewidths=1.35))
    ax.add_patch(Circle((0, 0), 42, facecolor="#ecb766", edgecolor="none", alpha=0.38))
    ax.text(-90, -65, "Terminal vicinity", fontsize=8, color="#715022")
    ax.set(
        xlim=(-130, 220),
        ylim=(-145, 160),
        aspect="equal",
        xlabel="East of local origin (m)",
        ylabel="North (m)",
    )
    ax.set_title("Mapped street centrelines", loc="left", fontsize=11)
    chart.plot(range(0, 421, 5), samples, color="#13776f", lw=2.5)
    chart.axvspan(0, 80, color="#ecb766", alpha=0.38)
    chart.set(
        xlim=(0, 420),
        ylim=(0, 48),
        xlabel="Distance along the 2011 line (m)",
        ylabel="Nearest mapped street (m)",
    )
    chart.set_title("Separation between sources", loc="left", fontsize=11)
    chart.grid(axis="y", alpha=0.23)
    for a in (ax, chart):
        a.spines[["top", "right"]].set_visible(False)
        a.tick_params(labelsize=8)
    fig.text(
        0.065,
        0.07,
        "Roads: © OpenStreetMap contributors, from TAK release 0.4.13. Route: MLIT N07-11 (Kagawa).",
        fontsize=8,
    )
    fig.text(
        0.065,
        0.038,
        "Shading marks the terminal survey area. Stop 5 and current lane geometry require independent evidence.",
        fontsize=8,
    )
    fig.savefig(path, dpi=165)
    plt.close(fig)


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("n07_geojson", type=Path)
    p.add_argument("tak_zip", type=Path)
    p.add_argument("--exercise", action="store_true")
    p.add_argument("--figure", type=Path)
    a = p.parse_args()
    print(json.dumps(compare(a.n07_geojson, a.tak_zip, a.exercise, a.figure), indent=2))
