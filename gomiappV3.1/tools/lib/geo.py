"""地図データ（e-Stat の町丁・字等別境界 KML）を読んで、小さくするための共通の道具"""
import math
import re
from pathlib import Path

TOL = 0.00008          # 形を簡単にするときの許容（度。約8m）


def parse_kml(path):
    t = Path(path).read_text(encoding="utf-8")
    out = []
    for pm in re.findall(r"<Placemark>(.*?)</Placemark>", t, re.S):
        d = dict(re.findall(r'<SimpleData name="(\w+)">(.*?)</SimpleData>', pm))
        rings = []
        for poly in re.findall(r"<Polygon>(.*?)</Polygon>", pm, re.S):
            for kind, body in re.findall(r"<(outer|inner)BoundaryIs>.*?<coordinates>(.*?)</coordinates>", poly, re.S):
                rings.append([tuple(map(float, p.split(",")[:2])) for p in body.split()])
        out.append({"name": d.get("S_NAME", ""), "city": d.get("CITY_NAME", ""), "x": float(d["X_CODE"]), "y": float(d["Y_CODE"]), "rings": rings})
    return out

def simplify(pts, tol):
    # ダグラス・ポーカー法（閉じた線は2つに分けて処理）
    if len(pts) < 5:
        return pts
    keep = [False] * len(pts); keep[0] = keep[-1] = True
    far = max(range(len(pts)), key=lambda i: (pts[i][0] - pts[0][0]) ** 2 + (pts[i][1] - pts[0][1]) ** 2)
    keep[far] = True
    stack = [(0, far), (far, len(pts) - 1)]
    while stack:
        a, b = stack.pop()
        if b <= a + 1:
            continue
        (x1, y1), (x2, y2) = pts[a], pts[b]
        dx, dy = x2 - x1, y2 - y1; L = math.hypot(dx, dy) or 1e-12
        best, bi = -1, -1
        for i in range(a + 1, b):
            d = abs(dy * (pts[i][0] - x1) - dx * (pts[i][1] - y1)) / L
            if d > best:
                best, bi = d, i
        if best > tol:
            keep[bi] = True; stack += [(a, bi), (bi, b)]
    out = [p for p, k in zip(pts, keep) if k]
    return out if len(out) >= 4 else pts


def encode(ring, base):
    # 10万分の1度の整数にして、1つ前の点との差で並べる（ファイルを小さくするため）
    out, px, py = [], 0, 0
    for x, y in ring:
        ix, iy = round((x - base[0]) * 1e5), round((y - base[1]) * 1e5)
        out += [ix - px, iy - py]; px, py = ix, iy
    return out


def bbox(rings, base):
    xs = [p[0] for r in rings for p in r]; ys = [p[1] for r in rings for p in r]
    return [round((min(xs) - base[0]) * 1e5), round((min(ys) - base[1]) * 1e5), round((max(xs) - base[0]) * 1e5), round((max(ys) - base[1]) * 1e5)]
