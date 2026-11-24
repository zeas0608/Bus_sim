"""Small oriented details in metres. +u runs along a facade, -v faces the street."""

import math
import re

from shapely.geometry import Polygon


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


def quad(layers, name, corners, uv=None):
    for indices in ((0, 1, 2), (0, 2, 3)):
        layers.face(name, [corners[i] for i in indices], [uv[i] for i in indices] if uv else None)


class Frame:
    def __init__(self, layers, origin, along):
        self.layers = layers
        self.origin = origin
        d = math.hypot(*along)
        self.ux, self.uy = along[0] / d, along[1] / d

    def p(self, u, v, z):
        x, y, h = self.origin
        return x + self.ux * u - self.uy * v, y + self.uy * u + self.ux * v, h + z

    def rect(self, x, y, w, d):
        return Polygon(
            [self.p(x + i * w / 2, y + j * d / 2, 0)[:2] for i, j in ((-1, -1), (1, -1), (1, 1), (-1, 1))]
        )

    def face(self, material, points, uv=None):
        quad(self.layers, material, [self.p(*p) for p in points], uv)

    def box(self, material, center, size):
        x, y, z = center
        a, b, c = [s / 2 for s in size]
        points = [
            self.p(x + i * a, y + j * b, z + k * c)
            for k in (-1, 1)
            for i, j in ((-1, -1), (1, -1), (1, 1), (-1, 1))
        ]
        for ids in ((3, 2, 1, 0), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)):
            quad(self.layers, material, [points[i] for i in ids])

    def tube(self, material, start, end, r1, r2=None, sides=10):
        # Any direction, with a cap at either end. Used for columns, branches and signal lenses.
        a, b = self.p(*start), self.p(*end)
        axis = [y - x for x, y in zip(a, b)]
        length = math.sqrt(sum(k * k for k in axis))
        if length < 1e-7:
            return
        x, y, z = (k / length for k in axis)
        delta = math.hypot(x, y)
        u = (-y / delta, x / delta, 0) if delta > 1e-6 else (1.0, 0.0, 0.0)
        v = (y * u[2] - z * u[1], z * u[0] - x * u[2], x * u[1] - y * u[0])
        rings = []
        for center, r in ((a, r1), (b, r1 if r2 is None else r2)):
            ring = []
            for j in range(sides):
                angle = j * math.tau / sides
                ring.append(
                    tuple(
                        k + r * (du * math.cos(angle) + dv * math.sin(angle))
                        for k, du, dv in zip(center, u, v)
                    )
                )
            rings.append(ring)
        for j in range(sides):
            k = (j + 1) % sides
            quad(self.layers, material, [rings[0][j], rings[0][k], rings[1][k], rings[1][j]])
            self.layers.face(material, [a, rings[0][k], rings[0][j]])
            self.layers.face(material, [b, rings[1][j], rings[1][k]])

    def print_panel(self, cell, x, y, z, w, h):
        # A four-pixel gutter within the atlas cell prevents colour bleed at its edges.
        u, v = (cell % 4) / 4, (cell // 4) / 4
        uv = [(u + 0.002, v + 0.246), (u + 0.248, v + 0.246), (u + 0.248, v + 0.004), (u + 0.002, v + 0.004)]
        self.face(
            "SignPrint",
            [
                (x - w / 2, y, z - h / 2),
                (x + w / 2, y, z - h / 2),
                (x + w / 2, y, z + h / 2),
                (x - w / 2, y, z + h / 2),
            ],
            uv,
        )
