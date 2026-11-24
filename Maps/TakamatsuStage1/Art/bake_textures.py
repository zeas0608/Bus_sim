"""Bake original seamless PBR tiles and a fictional wayfinding layout. Build-time tool only."""

import argparse
import math
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).resolve().parent
SIZE = 512
Y, X = np.mgrid[:SIZE, :SIZE] / SIZE


def noise(rng, cells):
    # Periodic, smooth value noise. UV boundaries share the same neighbouring samples.
    grid = rng.normal(0, 1, (cells, cells))
    x, y = X * cells, Y * cells
    i, j = x.astype(int), y.astype(int)
    u, v = x - i, y - j
    u, v = u * u * (3 - 2 * u), v * v * (3 - 2 * v)
    return ((1 - u) * grid[j, i] + u * grid[j, (i + 1) % cells]) * (1 - v) + (
        (1 - u) * grid[(j + 1) % cells, i] + u * grid[(j + 1) % cells, (i + 1) % cells]
    ) * v


def save_pbr(out, name, rgb, roughness, height, metres):
    # Base texture RGB = sRGB, alpha = linear roughness. Heights in metres.
    rgba = np.dstack((np.clip(rgb, 0, 255), np.clip(roughness, 0, 1) * 255)).round().astype("uint8")
    Image.fromarray(rgba).save(out / (name + "_BC.png"), optimize=True)
    scale = SIZE / (2 * metres)
    du = (np.roll(height, -1, axis=1) - np.roll(height, 1, axis=1)) * scale
    dv = (np.roll(height, -1, axis=0) - np.roll(height, 1, axis=0)) * scale
    # DirectX tangent-space normals (image V increases down).
    n = np.stack((-du, dv, np.ones_like(du)), axis=-1)
    n /= np.linalg.norm(n, axis=-1, keepdims=True)
    Image.fromarray(((n * 0.5 + 0.5) * 255).round().astype("uint8")).save(
        out / (name + "_N.png"), optimize=True
    )


def paving(out):
    rng = np.random.default_rng(108647)
    grain = rng.normal(size=(SIZE, SIZE))
    aggregate = noise(rng, 160)
    patch = noise(rng, 4)
    stones = np.maximum(aggregate - 0.5, 0)
    # Small aggregate, binder and slowly changing tone avoid painted-looking uniform black.
    intensity = 57 + 3.5 * patch + 9 * grain + 16 * stones + 4 * noise(rng, 28)
    rgb = intensity[:, :, None] * np.array([1.015, 1.008, 1.0])
    save_pbr(
        out,
        "Asphalt",
        rgb,
        0.85 - 0.085 * stones + 0.025 * patch,
        0.00053 * grain + 0.0019 * stones + 0.0008 * aggregate,
        1.28,
    )

    # Thirty-two staggered 30 × 15 cm concrete blocks in each 1.2 m square repeat (4 x 8).
    row = (Y * 8).astype(int)
    col = ((X * 4 + 0.5 * (row % 2)) % 4).astype(int)
    u = (X * 4 + 0.5 * (row % 2)) % 1
    v = (Y * 8) % 1
    gap = np.minimum(np.minimum(u, 1 - u) * 0.30, np.minimum(v, 1 - v) * 0.15)
    bevel = np.clip((gap - 0.002) / 0.005, 0, 1)
    lot = rng.normal(0, 6, (8, 4))[row, col]
    paver = np.array([168, 157, 143]) + lot[:, :, None] + (grain * 3.8 + patch * 4)[:, :, None]
    rgb = np.array([94, 89, 80]) * (1 - bevel[:, :, None]) + paver * bevel[:, :, None]
    save_pbr(out, "Pavers", rgb, 0.90 - 0.09 * bevel, bevel * 0.0038 + 0.0005 * grain, 1.2)

    sand = noise(rng, 55) + grain * 0.65
    pores = np.clip(-1.2 - aggregate, 0, 1)
    rgb = np.array([177, 174, 164]) + (patch * 4.5 + sand * 4 - pores * 25)[:, :, None]
    save_pbr(out, "Concrete", rgb, 0.8 + 0.08 * pores, 0.0006 * sand - 0.002 * pores, 0.8)

    worn = np.clip((aggregate + grain * 0.45 - 1.25) * 0.85, 0, 0.9)
    paint = np.array([223, 221, 203]) - (worn * 105)[:, :, None] + (grain * 3 + patch * 3)[:, :, None]
    save_pbr(out, "RoadPaint", paint, 0.69 + 0.13 * worn, 0.00025 * grain - 0.0007 * worn, 0.8)

    # Cast-iron lid, concentric rims and interlocking raised diamonds; no municipal crest.
    r = np.hypot(X - 0.5, Y - 0.5)
    hatch = (np.cos((X + Y) * math.tau * 20) + np.cos((X - Y) * math.tau * 20)) * 0.5
    emboss = np.clip((hatch - 0.06) * 3, 0, 1) * (r < 0.421)
    rim = ((r > 0.443) & (r < 0.463)) | ((r > 0.477) & (r < 0.488))
    slot = (((X - 0.50) / 0.065) ** 2 + ((np.abs(Y - 0.50) - 0.345) / 0.018) ** 2) < 1
    h = 0.0022 * emboss + 0.002 * rim - 0.003 * slot
    metal = 65 + emboss * 19 + rim * 25 - slot * 31 + grain * 6 + patch * 5
    save_pbr(
        out,
        "IronCover",
        metal[:, :, None] * np.array([1.045, 1.02, 0.98]),
        0.77 - 0.21 * emboss - 0.14 * rim,
        h + 0.00035 * grain,
        0.64,
    )

    # Tactile warning dots at 6 cm pitch on 30 cm modules.
    dx = (X * 5 + 0.5) % 1 - 0.5
    dy = (Y * 5 + 0.5) % 1 - 0.5
    dots = np.clip((0.25 - np.hypot(dx, dy)) / 0.12, 0, 1)
    seam = np.clip(np.minimum.reduce([X, Y, 1 - X, 1 - Y]) / 0.009, 0, 1)
    rgb = np.array([214, 168, 55]) * (0.85 + 0.15 * seam[:, :, None]) + (grain * 3 + dots * 9)[:, :, None]
    save_pbr(out, "Tactile", rgb, 0.8 - 0.12 * dots, 0.005 * dots + 0.001 * seam, 0.30)


def foliage(out):
    # An original twig spray with individually drawn blades and midribs, used on two-sided masked cards.
    rng = np.random.default_rng(205)
    img = Image.new("RGBA", (512, 512), (71, 100, 46, 0))
    d = ImageDraw.Draw(img)
    stem = np.array([251.0, 497.0])
    for side in (-1, 1):
        for i in range(6):
            base = stem + np.array([i * 2.0, -i * 57.0])
            end = base + np.array([side * (192 - i * 18), -125.0])
            d.line([tuple(base), tuple(end)], fill=(95, 91, 48, 255), width=3)
            for j in range(1, 10):
                mid = base + (end - base) * (j / 10)
                for sign in (-1, 1):
                    angle = -1.32 + side * 0.55 + sign * 1.03 + rng.uniform(-0.32, 0.32)
                    axis = np.array([math.cos(angle), math.sin(angle)])
                    tip = mid + axis * rng.uniform(26, 51)
                    center = mid + (tip - mid) * 0.49
                    perp = np.array([-axis[1], axis[0]]) * rng.uniform(6.5, 11.0)
                    base_color = np.array([80, 113, 57]) + rng.normal(0, 15) * np.array([1, 0.84, 0.6])
                    color = tuple(np.clip(base_color, 0, 255).astype(int)) + (255,)
                    d.polygon(
                        [tuple(mid), tuple(center + perp), tuple(tip), tuple(center - perp)], fill=color
                    )
                    d.line([tuple(mid), tuple(tip)], fill=(106, 132, 67, 255), width=1)
    d.line([(251, 499), (262, 182), (264, 78)], fill=(102, 99, 52, 255), width=3)
    img.save(out / "Leaves.png", optimize=True)


# Atlas grid, 4 columns x 4 rows. All imagery/lettering is drawn for this project.
# Tile order is also the index used by the map meshes.
SIGN_CELLS = ["bay" + str(n) for n in range(1, 11)] + [
    "bus",
    "route47",
    "station",
    "tower",
    "hotel",
    "crossing",
]


def signs(out, font):
    width, height = 512, 256
    atlas = Image.new("RGB", (4 * width, 4 * height), (40, 58, 64))
    for index, kind in enumerate(SIGN_CELLS):
        tile = Image.new("RGB", (width, height), (234, 236, 226))
        draw = ImageDraw.Draw(tile)

        def label(x, y, word, size, color, anchor="mm"):
            draw.text(
                (x, y), word, font=ImageFont.truetype(str(font), size, index=0), fill=color, anchor=anchor
            )

        ink = (27, 48, 58)
        if kind.startswith("bay"):
            draw.rectangle((0, 0, 180, 256), fill=(16, 87, 107))
            label(89, 121, kind[3:], 143, "white")
            label(345, 75, "高松駅", 57, ink)
            label(345, 143, "のりば", 44, ink)
            label(345, 213, "TAKAMATSU STA.", 23, ink)
        elif kind in ("station", "tower", "hotel"):
            tile.paste((39, 53, 62), (0, 0, width, height))
            text, latin = {
                "station": ("高 松 駅", "TAKAMATSU STATION"),
                "tower": ("高松シンボルタワー", "TAKAMATSU SYMBOL TOWER"),
                "hotel": ("ホテルクレメント高松", "HOTEL CLEMENT TAKAMATSU"),
            }[kind]
            label(256, 100, text, 70 if kind == "station" else 44, (247, 244, 230))
            label(256, 179, latin, 24, (197, 211, 211))
        elif kind == "crossing":
            tile.paste((31, 78, 136), (0, 0, width, height))
            draw.polygon([(256, 18), (392, 225), (120, 225)], fill=(244, 245, 236))
            draw.ellipse((245, 78, 265, 97), fill=ink)
            draw.line([(250, 105), (237, 142), (267, 151), (281, 191)], fill=ink, width=11)
            draw.line([(237, 143), (213, 186)], fill=ink, width=10)
            draw.line([(250, 108), (270, 131), (291, 133)], fill=ink, width=8)
        else:
            draw.rectangle((0, 0, 512, 72), fill=(23, 91, 107))
            label(256, 34, "バスのりば", 35, "white")
            label(256, 127, "47　御厩線" if kind == "route47" else "高松駅", 51, ink)
            label(256, 202, "MIMAYA LINE" if kind == "route47" else "TAKAMATSU STA.", 25, ink)
        atlas.paste(tile, (index % 4 * width, index // 4 * height))
    atlas.save(out / "Wayfinding.png", optimize=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--font", type=Path, required=True, help="Noto Sans CJK Regular TTC (or equivalent for local artwork)"
    )
    args = parser.parse_args()
    paving(HERE)
    foliage(HERE)
    signs(HERE, args.font)
