"""A local, north-up review drawing from the actual triangles imported into the editor."""

from html import escape

from survey import BBOX, project


def write_overview(plan, path):
    west, south = project(*BBOX[:2])
    east, north = project(*BBOX[2:])
    w, h = east - west, north - south

    def xy(e, n):
        return f"{e - west:.2f},{north - n:.2f}"

    out = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w:.2f} {h + 82:.2f}">',
        '<rect width="100%" height="100%" fill="#faf7ee"/>',
        "<title>高松駅と御厩線47番・生成メッシュの平面検図</title>",
    ]
    colors = {
        "Asphalt": "#67727a",
        "WidthEstimate": "#929d9e",
        "TurningApron": "#a1a9a3",
        "Buildings": "#c7b99e",
        "Paving": "#d5cfc4",
        "Kerb": "#eeebe2",
        "Shelters": "#64a8ae",
        "Paint": "#faf4da",
        "StopSign": "#185385",
        "SignalHousing": "#222b30",
    }
    for name, color in colors.items():
        layer = plan["meshes"].get(name)
        if not layer:
            continue
        # Group neighbouring faces in one path, so internal seams aren't stroked.
        coords = [xy(e / 100, n / 100) for n, e, z in layer["vertices"]]
        idx = layer["triangles"]
        triangles = "".join(
            "M" + " ".join(coords[i] for i in idx[k : k + 3]) + "Z" for k in range(0, len(idx), 3)
        )
        out.append(f'<path fill="{color}" d="{triangles}"/>')
    survey = plan["survey"]
    line = " ".join(xy(*p) for p in survey["route_en_m"])
    if line:
        out.append(
            f'<polyline points="{line}" fill="none" stroke="#ed942d" stroke-width="2" stroke-dasharray="6 3"/>'
        )
    n, e, _, yaw = plan["spawn"]
    out.append(
        f'<g transform="translate({xy(e / 100, n / 100)}) rotate({yaw:.2f})"><path d="M0 -7L4 4L0 2L-4 4Z" fill="#e34f3f" stroke="white"/></g>'
    )
    out.extend(
        [
            '<g font-family="sans-serif" fill="#263b46"><text x="10" y="20" font-size="12">N ↑</text>',
            '<path d="M10 35h50" stroke="#263b46"/><text x="10" y="49" font-size="10">50 m</text>',
            f'<text x="8" y="{h + 18:.1f}" font-size="13">高松駅　御厩線47番 ｜ 赤い矢印は1086の発進位置</text>',
            f'<text x="8" y="{h + 36:.1f}" font-size="10">経路資料 {escape(str(survey["path_source"] or "なし"))}　乗場資料 {escape(survey["platform_evidence"])}</text>',
            f'<text x="8" y="{h + 53:.1f}" font-size="10">橙破線は資料の経路線。濃い灰が元の車道、明るい灰が仮の幅・旋回補助。停止位置・信号にも推定を含む。</text>',
            f'<text x="8" y="{h + 69:.1f}" font-size="9">{escape(plan["attribution"])}</text></g></svg>',
        ]
    )
    path.write_text("\n".join(out), encoding="utf-8")
