"""「今いる場所から探す」用の小さな地図データ（geo/towns.json）を作る。

使い方:
  python tools/build_geo.py <KMLのフォルダ> index.html geo/towns.json [確認用の一覧.txt]

KML のフォルダには、e-Stat「統計地理情報システム」の境界データ
（国勢調査 令和2年 小地域（町丁・字等別）、世界測地系 緯度経度、KML 形式）を置く。
  r2ka35215.kml（周南市）・r2ka35207.kml（下松市）
  ※ダウンロードした .kmz は zip なので、中の .kml を取り出して上の名前にする。

できるデータ:
  ・町丁ごとの境目（形を少し簡単にして、10万分の1度の整数・差分で保存）
  ・周南市：町丁ごとに、アプリの地区（index.html の GOMI_CAL.areas）の候補
  ・下松市：西地区・東地区の境目の線（市のごみカレンダーのページにある地図「sinai.jpg」から読み取った、おおまかな線）

出典：政府統計の総合窓口（e-Stat）国勢調査（令和2年）町丁・字等別境界データ を加工して作成。
"""
import json, math, re, sys
from pathlib import Path

BASE = (131.6, 33.9)   # 座標の基準（10万分の1度の整数にするときに引く）
TOL = 0.00008          # 形を簡単にするときの許容（度。約8m）

# 下松市の西地区／東地区の境目（南西の海側 → 北東の市境の外）。経度, 緯度
KUDA_LINE = [[131.8400, 33.9950], [131.85026, 34.0076], [131.85242, 34.01112], [131.85458, 34.0158], [131.85674, 34.01903],
    [131.85891, 34.02195], [131.86107, 34.0243], [131.86323, 34.02635], [131.8654, 34.02811], [131.86756, 34.02986],
    [131.86972, 34.03133], [131.87189, 34.03308], [131.87405, 34.03396], [131.87621, 34.03514], [131.87837, 34.03601],
    [131.88054, 34.03689], [131.8827, 34.03806], [131.88486, 34.03894], [131.88703, 34.03953], [131.88919, 34.04011],
    [131.89135, 34.0407], [131.89351, 34.04129], [131.89568, 34.04158], [131.89784, 34.04217], [131.9, 34.04275],
    [131.90433, 34.04334], [131.90866, 34.04392], [131.91298, 34.04422], [131.91731, 34.04451], [131.93028, 34.0448], [131.9700, 34.0448]]
# 地図の説明で、線とは別に地区が決まっている町（凡例「東陽地区」は西地区、「笠戸島地区」は東地区）
KUDA_SIDE = {"東陽": "西地区", "笠戸島": "東地区"}

# 周南市：e-Stat の町名とアプリの地区名で呼び方がちがうもの
ALIAS = {"櫛ケ浜": ["櫛浜"], "須万": ["須金"], "金峰": ["須金"], "鹿野上": ["鹿野地域"], "鹿野中": ["鹿野地域"],
         "鹿野下": ["鹿野地域"], "大潮": ["鹿野地域"], "巣山": ["鹿野地域"], "須万鹿野": ["鹿野地域"], "金峰鹿野": ["鹿野地域"],
         "高瀬": ["和田"], "夏切": ["和田"], "垰": ["和田"], "米光": ["和田"], "馬神": ["和田"], "福川羽島": ["羽島"],
         "一番町": ["一番丁"]}
KANSUJI = "〇一二三四五六七八九"

def parse_kml(path):
    t = Path(path).read_text(encoding="utf-8")
    out = []
    for pm in re.findall(r"<Placemark>(.*?)</Placemark>", t, re.S):
        d = dict(re.findall(r'<SimpleData name="(\w+)">(.*?)</SimpleData>', pm))
        rings = []
        for poly in re.findall(r"<Polygon>(.*?)</Polygon>", pm, re.S):
            for kind, body in re.findall(r"<(outer|inner)BoundaryIs>.*?<coordinates>(.*?)</coordinates>", poly, re.S):
                rings.append([tuple(map(float, p.split(",")[:2])) for p in body.split()])
        out.append({"name": d.get("S_NAME", ""), "x": float(d["X_CODE"]), "y": float(d["Y_CODE"]), "rings": rings})
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

def encode(ring):
    # 10万分の1度の整数にして、1つ前の点との差で並べる（ファイルを小さくするため）
    out, px, py = [], 0, 0
    for x, y in ring:
        ix, iy = round((x - BASE[0]) * 1e5), round((y - BASE[1]) * 1e5)
        out += [ix - px, iy - py]; px, py = ix, iy
    return out

def bbox(rings):
    xs = [p[0] for r in rings for p in r]; ys = [p[1] for r in rings for p in r]
    return [round((min(xs) - BASE[0]) * 1e5), round((min(ys) - BASE[1]) * 1e5), round((max(xs) - BASE[0]) * 1e5), round((max(ys) - BASE[1]) * 1e5)]

def kanji_num(n):
    return {1: "一", 2: "二", 3: "三", 4: "四", 5: "五", 6: "六", 7: "七", 8: "八", 9: "九", 10: "十"}[n]

def area_keys(name):
    # アプリの地区名から、e-Stat の町名と照らし合わせるための名前を作る
    base = re.sub(r"[（(].*?[）)]", "", name).strip()
    note = "".join(re.findall(r"[（(](.*?)[）)]", name))
    base = re.sub(r"(\d)丁目", lambda m: kanji_num(int(m.group(1))) + "丁目", base)
    keys = set()
    m = re.match(r"(.+?)([一二三四五六七八九])丁目～([一二三四五六七八九])丁目$", base)
    if m:
        for i in range(KANSUJI.index(m.group(2)), KANSUJI.index(m.group(3)) + 1):
            keys.add(m.group(1) + KANSUJI[i] + "丁目")
    else:
        for part in re.split(r"・", base):
            keys.add(part)
        m2 = re.match(r"(.+?)([上中下東西])$", base.split("・")[0])
        if "・" in base and m2:   # 石光上・中・下 → 石光上, 石光中, 石光下
            for s in base.split("・")[1:]:
                keys.add(m2.group(1) + s)
            keys.add(m2.group(1))
    if "大字富田" in note:
        keys.add("富田" + base)
    for k in list(keys):
        keys.add(re.sub(r"(全域|地域).*$", "", k))
    return {k for k in keys if len(k) >= 2}, note

def estat_pieces(name):
    n = name.replace("大字", "")
    pieces = [n] + n.split("字")
    pieces += [re.sub(r"[一二三四五六七八九十]+丁目$", "", p) for p in list(pieces)]
    if n.startswith("徳山字"):
        pieces.append(n[3:])
    # 「大字徳山」の「徳山」だけでは、どの地区か決められない（徳山港町などに当たってしまう）
    return [p for p in dict.fromkeys(pieces) if len(p) >= 2 and p != "徳山"]

def shunan_candidates(towns, areas):
    akeys = [area_keys(a["n"]) for a in areas]
    res = []
    for t in towns:
        pieces = estat_pieces(t["name"])
        for p in list(pieces):
            if p in ALIAS:                 # 呼び方がちがう町（完全に同じ名前を先に）
                pieces += ALIAS[p]
            else:
                for k, v in ALIAS.items():
                    if p.startswith(k) and not any(q in ALIAS for q in pieces):
                        pieces += v
        cands = []
        for i, (keys, note) in enumerate(akeys):
            score = -1 if pieces and pieces[0] in keys and "丁目" in pieces[0] else None   # 「○○一丁目」まで同じ
            for p in pieces:
                for k in keys:
                    if p == k:
                        s = 0
                    elif p.startswith(k) and len(k) >= 2:
                        s = 1      # 例：須々万本郷 → 須々万
                    else:
                        continue
                    score = s if score is None else min(score, s)
            if score is not None:
                # 「一部：○○」に e-Stat の小さな字名が書いてあれば、それを先に
                if note and any(q in note for q in pieces[1:] if len(q) >= 2):
                    score -= 0.5
                cands.append((score, i))
        best = min((s for s, _ in cands), default=None)
        cands = sorted(c for c in cands if c[0] <= best + 0.5) if cands else []
        res.append([i for _, i in cands])
    return res

def main():
    kml_dir, html_path, out_path = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
    html = html_path.read_text(encoding="utf-8")
    cal = json.loads(re.search(r"window\.GOMI_CAL = /\*CAL-DATA-START\*/(.*?)/\*CAL-DATA-END\*/", html, re.S).group(1))
    areas = cal["areas"]
    out = {"base": BASE, "source": "e-Stat 国勢調査（令和2年）町丁・字等別境界データを加工", "cities": {}}

    # 周南市
    towns = [t for t in parse_kml(kml_dir / "r2ka35215.kml") if t["name"]]
    cands = shunan_candidates(towns, areas)
    # 地域（徳山・新南陽・熊毛・鹿野）：候補から決まらない町は、いちばん近い町に合わせる
    region = [None] * len(towns)
    for i, c in enumerate(cands):
        rs = {areas[j]["r"] for j in c}
        if len(rs) == 1:
            region[i] = rs.pop()
    known = [i for i in range(len(towns)) if region[i]]
    for i in range(len(towns)):
        if not region[i]:
            j = min(known, key=lambda k: (towns[k]["x"] - towns[i]["x"]) ** 2 + (towns[k]["y"] - towns[i]["y"]) ** 2)
            region[i] = region[j]
        cands[i] = [j for j in cands[i] if areas[j]["r"] == region[i]]
    sh = []
    for t, c, r in zip(towns, cands, region):
        rings = [simplify(rg, TOL) for rg in t["rings"]]
        sh.append({"n": t["name"], "r": r, "c": c[:8], "b": bbox(rings), "p": [encode(rg) for rg in rings]})
    out["cities"]["shunan"] = {"towns": sh}

    # 下松市
    towns = [t for t in parse_kml(kml_dir / "r2ka35207.kml") if t["name"]]
    kd = []
    for t in towns:
        rings = [simplify(rg, TOL) for rg in t["rings"]]
        side = next((v for k, v in KUDA_SIDE.items() if k in t["name"]), None)
        kd.append({"n": t["name"], "b": bbox(rings), "p": [encode(rg) for rg in rings], **({"side": side} if side else {})})
    out["cities"]["kudamatsu"] = {"towns": kd, "line": KUDA_LINE}

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")

    # 確認用の一覧（周南市の町 → アプリの地区の候補）
    if len(sys.argv) < 5:
        print("towns", len(sh), len(kd), "bytes", out_path.stat().st_size); return
    with open(sys.argv[4], "w", encoding="utf-8") as f:
        for t in sh:
            f.write(f"{t['n']}\t{t['r']}\t{' / '.join(areas[j]['n'] + '(' + areas[j]['s'] + ')' for j in t['c'])}\n")
    print("towns", len(sh), len(kd), "bytes", out_path.stat().st_size)

if __name__ == "__main__":
    main()
