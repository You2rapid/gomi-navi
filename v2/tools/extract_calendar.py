"""周南市「ごみ収集カレンダー」PDF から収集日データを作り、index.html に書き込む。

使い方:
  python tools/extract_calendar.py <PDFとHTMLのフォルダ> index.html

フォルダには次を置く（市のサイトからダウンロード）:
  A.pdf ～ H.pdf, otsushima.pdf, tokuyama_sankan.pdf, wada_sankan.pdf
  page_143320.html（徳山）, page_143319.html（新南陽）, page_143318.html（熊毛）, page_143317.html（鹿野）

カレンダーのマス目は、色付きの図形（ベクター）で描かれているので、
その色から「その日に何ごみが出せるか」を読み取る。
"""
import datetime as dt
import html
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

import pymupdf

SCHEDULES = {
    "A": "A.pdf", "B": "B.pdf", "C": "C.pdf", "D": "D.pdf", "E": "E.pdf",
    "F": "F.pdf", "G": "G.pdf", "H": "H.pdf",
    "大津島": "otsushima.pdf", "徳山山間": "tokuyama_sankan.pdf", "和田山間": "wada_sankan.pdf",
}

# マスの塗り色 → 区分
COLORS = {
    (0.0, 0.65, 0.32): "可燃",
    (1.0, 0.95, 0.0): "容プラ",
    (0.99, 0.72, 0.07): "他プラ",
    (0.0, 0.68, 0.94): "不燃",
    (0.93, 0.0, 0.55): "紙衣",
    (0.46, 0.44, 0.7): "びん缶",
    (0.67, 0.88, 0.98): "ペット",
    (0.14, 0.12, 0.13): "処困",
    (1.0, 1.0, 1.0): None,
}

# 月ブロックの位置（ポイント）。左上から 2 列 × 3 段。
BLOCKS = [
    (38, 155, 414, 372), (428, 155, 803, 372),
    (38, 377, 414, 593), (428, 377, 803, 593),
    (38, 598, 414, 814), (428, 598, 803, 814),
]
FISCAL_YEAR = 2026  # 令和8年度（2026年4月～2027年3月）


def color_name(fill):
    key = tuple(round(x, 2) for x in fill)
    best, dist = None, 9
    for c, name in COLORS.items():
        d = sum(abs(a - b) for a, b in zip(c, key))
        if d < dist:
            best, dist = (c, name), d
    if dist > 0.08:
        raise ValueError(f"unknown color {key}")
    return best[1]


def cluster(values, tol=4):
    out = []
    for v in sorted(values):
        if not out or v - out[-1][-1] > tol:
            out.append([v])
        else:
            out[-1].append(v)
    return [sum(g) / len(g) for g in out]


def nearest(centers, v):
    return min(range(len(centers)), key=lambda i: abs(centers[i] - v))


def read_pdf(path):
    doc = pymupdf.open(path)
    days = {}
    months = [(FISCAL_YEAR, m) for m in range(4, 13)] + [(FISCAL_YEAR + 1, m) for m in range(1, 4)]
    for pno, page in enumerate(doc):
        drawings = page.get_drawings()
        for bi, b in enumerate(BLOCKS):
            year, month = months[pno * 6 + bi]
            blk = pymupdf.Rect(*b)
            cells = []  # (x, y, kind, color)
            for d in drawings:
                r = d["rect"]
                if d.get("fill") is None or not blk.contains(r):
                    continue
                if not (30 <= r.width <= 56 and 25 <= r.height <= 60):
                    continue
                kinds = [it[0] for it in d["items"]]
                if kinds == ["re"]:
                    shape = "rect"
                elif kinds == ["l", "l", "l"]:
                    # 斜めに 2 色で分けたマスの片側（三角形）
                    shape = "tri"
                else:
                    continue
                cells.append((r, shape, color_name(d["fill"])))
            xs = cluster([r.x0 for r, _, _ in cells])
            ys = cluster([r.y0 for r, _, _ in cells])
            if len(xs) != 7:
                raise ValueError(f"{path.name} {year}/{month}: columns={len(xs)}")
            grid = defaultdict(list)  # (row, col) -> [(shape, name)] 描画順
            for r, shape, name in cells:
                grid[(nearest(ys, r.y0), nearest(xs, r.x0))].append((shape, name))
            first = dt.date(year, month, 1)
            col0 = (first.weekday() + 1) % 7  # 日曜はじまり
            ndays = (dt.date(year + (month == 12), month % 12 + 1, 1) - first).days
            for day in range(1, ndays + 1):
                idx = col0 + day - 1
                parts = grid.get((idx // 7, idx % 7))
                if not parts:
                    raise ValueError(f"{path.name} {year}/{month}/{day}: no cell")
                tris = [n for s, n in parts if s == "tri"]
                if tris:
                    cats = [n for n in tris if n]
                else:
                    cats = [parts[-1][1]] if parts[-1][1] else []  # 最後に塗った色が見えている色
                days[f"{year}-{month:02d}-{day:02d}"] = cats
    return days


def nth_weekday(d):
    return (d.day - 1) // 7 + 1


# 山間部の日程は 1 マスに複数の区分が小さく描かれていて色だけでは読めないので、
# 「収集がある日か」だけを画素の色（燃やせるごみの緑）で読み取り、区分は凡例のルールから決める。
# ルール: (区分, 曜日(月=0), 第何週のリスト or None=毎週)
MOUNTAIN_RULES = {
    "徳山山間": [
        ("可燃", 1, None), ("容プラ", 1, [2, 3, 4, 5]), ("他プラ", 1, [1]), ("紙衣", 1, [1]),
        ("不燃", 1, [2]), ("びん缶", 1, [3]), ("ペット", 1, [3]), ("処困", 1, [4]),
    ],
    "和田山間": [
        ("可燃", 0, None), ("可燃", 3, None), ("容プラ", 0, None), ("他プラ", 3, [1]),
        ("紙衣", 3, [1, 3]), ("不燃", 3, [3]), ("びん缶", 3, [2, 4]), ("ペット", 3, [2, 4]),
        ("処困", 0, [4]),
    ],
}


MOUNTAIN_TEXT = {
    "徳山山間": {"可燃": "毎週火曜日", "容プラ": "毎月第2・3・4・5火曜日", "他プラ": "毎月第1火曜日",
                 "紙衣": "毎月第1火曜日", "不燃": "毎月第2火曜日", "びん缶": "毎月第3火曜日",
                 "ペット": "毎月第3火曜日", "処困": "毎月第4火曜日"},
    "和田山間": {"可燃": "毎週月・木曜日", "容プラ": "毎週月曜日", "他プラ": "毎月第1木曜日",
                 "紙衣": "毎月第1・3木曜日", "不燃": "毎月第3木曜日", "びん缶": "毎月第2・4木曜日",
                 "ペット": "毎月第2・4木曜日", "処困": "毎月第4月曜日"},
}


# カレンダーの注記（※）で個別に書かれている日（画像を見て確認したもの）
MOUNTAIN_OVERRIDES = {
    "和田山間": {
        "2026-11-30": ["可燃", "容プラ", "処困"],  # ※30日(月)に「処理困難物」を収集
        "2027-01-11": ["容プラ"],                  # ※11日(月)は「容器包装プラスチック」のみ収集
        "2027-03-29": ["可燃", "容プラ", "処困"],  # ※29日(月)に「処理困難物」を収集
    },
}


def mountain_cats(key, d):
    out = []
    for cat, wd, nths in MOUNTAIN_RULES[key]:
        if d.weekday() == wd and (nths is None or nth_weekday(d) in nths) and cat not in out:
            out.append(cat)
    return out


def read_mountain_pdf(key, path):
    doc = pymupdf.open(path)
    months = [(FISCAL_YEAR, m) for m in range(4, 13)] + [(FISCAL_YEAR + 1, m) for m in range(1, 4)]
    collected = set()
    all_days = []
    for pno, page in enumerate(doc):
        pix = page.get_pixmap(dpi=72)
        drawings = page.get_drawings()
        for bi, b in enumerate(BLOCKS):
            year, month = months[pno * 6 + bi]
            blk = pymupdf.Rect(*b)
            rects = [d["rect"] for d in drawings
                     if d.get("fill") is not None and blk.contains(d["rect"])
                     and 30 <= d["rect"].width <= 56 and 25 <= d["rect"].height <= 60]
            xs = cluster([r.x0 for r in rects])
            ys = cluster([r.y0 for r in rects])
            if len(xs) != 7:
                raise ValueError(f"{path.name} {year}/{month}: columns={len(xs)}")
            hs = sorted(r.height for r in rects)
            h = hs[len(hs) // 2]
            first = dt.date(year, month, 1)
            col0 = (first.weekday() + 1) % 7
            ndays = (dt.date(year + (month == 12), month % 12 + 1, 1) - first).days
            for day in range(1, ndays + 1):
                idx = col0 + day - 1
                row, col = idx // 7, idx % 7
                x0, y0 = xs[col], ys[row]
                x1 = xs[col + 1] if col < 6 else x0 + 37
                green = total = 0
                for y in range(int(y0) + 2, int(y0 + h) - 2):
                    for x in range(int(x0) + 2, int(x1) - 2):
                        r_, g_, b_ = pix.pixel(x, y)[:3]
                        total += 1
                        if g_ > 130 and r_ < 60 and 50 < b_ < 120:
                            green += 1
                d = dt.date(year, month, day)
                all_days.append(d)
                if green / total > 0.08:
                    collected.add(d)
    days = {}
    for d in all_days:
        cats = []
        if d in collected:
            cats = mountain_cats(key, d)
            if not cats:
                # 祝日などの振替：同じ週で収集のなかった本来の日のルールを使う
                sunday = d - dt.timedelta(days=(d.weekday() + 1) % 7)
                for i in range(7):
                    o = sunday + dt.timedelta(days=i)
                    if o not in collected and mountain_cats(key, o):
                        cats = mountain_cats(key, o)
                        break
                if not cats:
                    print("  !! 区分不明の収集日", key, d)
                    cats = ["可燃"]
        days[d.isoformat()] = cats
    for k, cats in MOUNTAIN_OVERRIDES.get(key, {}).items():
        if not days.get(k):
            print("  !! 注記の日が収集日として読めていない", key, k)
        days[k] = cats
    return days


WD = "月火水木金土日"


def derive_rules(days):
    """収集日の並びから「毎週月・木」「毎月第2火」のような基本ルールを推定する。"""
    by_cat = defaultdict(list)
    for k, cats in days.items():
        for c in cats:
            by_cat[c].append(dt.date.fromisoformat(k))
    rules = {}
    for cat, ds in by_cat.items():
        wd = Counter(d.weekday() for d in ds)
        if cat == "処困":
            rules[cat] = {"text": "月1回（カレンダーで確認）"}
            continue
        weekly = [w for w, n in wd.items() if n >= 30]
        if weekly:
            weekly.sort()
            rules[cat] = {"weekly": weekly, "text": "毎週" + "・".join(WD[w] for w in weekly) + "曜日"}
            continue
        nth = Counter((nth_weekday(d), d.weekday()) for d in ds)
        common = sorted([k for k, n in nth.items() if n >= 7])
        if not common:
            rules[cat] = {"text": ""}
            continue
        w = common[0][1]
        ns = [n for n, ww in common if ww == w]
        rules[cat] = {"nth": ns, "wd": w,
                      "text": "毎月第" + "・".join(map(str, ns)) + WD[w] + "曜日"}
    return rules


def is_regular(d, cat, rules):
    r = rules.get(cat, {})
    if "weekly" in r:
        return d.weekday() in r["weekly"]
    if "nth" in r:
        return d.weekday() == r["wd"] and nth_weekday(d) in r["nth"]
    return cat == "処困"


def read_areas(folder):
    """市のページの「行政区別日程一覧」表から 町名 → 日程 を作る。"""
    pages = [("徳山", "page_143320.html"), ("新南陽", "page_143319.html"), ("熊毛", "page_143318.html")]
    areas = []
    for region, fn in pages:
        raw = (folder / fn).read_bytes()
        try:
            text = raw.decode("cp932")
        except UnicodeDecodeError:
            text = raw.decode("utf-8")
        for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", text, re.S):
            cells = [html.unescape(re.sub(r"<[^>]+>|\s+", "", c))
                     for c in re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", tr, re.S)]
            cells = [c for c in cells if c]
            if len(cells) < 2:
                continue
            name, sched = cells[-2], cells[-1]
            sched = sched.translate(str.maketrans("ＡＢＣＤＥＦＧＨ", "ABCDEFGH"))
            if sched not in SCHEDULES or name in ("行政区", "町名"):
                continue
            areas.append({"r": region, "n": name, "s": sched})
    areas.append({"r": "鹿野", "n": "鹿野地域（全域）", "s": "H"})
    add_readings(areas)
    return areas


# 自動の読みが外れやすい地名（ひらがな検索用）
YOMI_FIX = {
    "櫛浜": "くしはま", "岐山通": "きざんどおり", "遠石": "といし", "上遠石": "かみといし", "上遠石町": "かみといしちょう",
    "夜市": "やじ", "戸田": "へた", "粭島": "すくもじま", "鼓海": "つづみがうら", "鼓南": "こなん",
    "大津島": "おおづしま", "新堀": "にいぼり", "四熊": "しくま", "須々万": "すすま", "須金": "すがね",
    "莇地": "あざみじ", "馬屋": "うまや", "花陽": "かよう", "糀町": "こうじまち", "土越": "ひじこし",
    "乗兼": "のりかね", "川曲": "かわまがり", "向道": "むかいみち", "長穂": "ながほ", "中須": "なかず",
    "小畑": "おばたけ", "大河内": "おおこうち", "久米": "くめ", "湯野": "ゆの", "秋月": "あきづき",
    "政所": "まんどころ", "富田": "とんだ", "福川": "ふくがわ", "温田": "ぬくた", "桶川町": "おけがわちょう",
    "御姫町": "おひめまち", "かせ河原町": "かせがわらまち", "社地町": "しゃじまち", "羽島": "はじま",
    "勝間": "かつま", "呼坂": "よびさか", "八代": "やしろ", "三丘": "みつお", "高水原": "たかみずばら",
    "垰": "たお", "定光": "じょうこう", "院内": "いんない", "此原": "このはら", "樋口": "ひぐち",
}


def add_readings(areas):
    try:
        import pykakasi
    except ImportError:
        return
    kks = pykakasi.kakasi()
    for a in areas:
        name = re.sub(r"[（(].*?[）)]", "", a["n"])
        for k in sorted(YOMI_FIX, key=len, reverse=True):
            name = name.replace(k, YOMI_FIX[k])
        a["y"] = "".join(x["hira"] for x in kks.convert(name))


def main():
    folder = Path(sys.argv[1])
    out_html = Path(sys.argv[2])
    sched_data = {}
    for key, fn in SCHEDULES.items():
        if key in MOUNTAIN_RULES:
            days = read_mountain_pdf(key, folder / fn)
        else:
            days = read_pdf(folder / fn)
        if key in MOUNTAIN_RULES:
            rules = {c: {"text": t} for c, t in MOUNTAIN_TEXT[key].items()}
            extra = {k: [c for c in cats if c not in mountain_cats(key, dt.date.fromisoformat(k))]
                     for k, cats in days.items()}
        else:
            rules = derive_rules(days)
            # 振替など、いつもの曜日と違う収集日に印をつける
            extra = {k: [c for c in cats if not is_regular(dt.date.fromisoformat(k), c, rules)]
                     for k, cats in days.items()}
        sched_data[key] = {
            "rules": {c: r["text"] for c, r in rules.items()},
            "days": {k: v for k, v in days.items() if v},
            "moved": {k: v for k, v in extra.items() if v},
        }
        print(key, {c: r["text"] for c, r in rules.items()})
        print("   特別:", {k: v for k, v in extra.items() if v})
    areas = read_areas(folder)
    print("areas", len(areas), Counter(a["s"] for a in areas))
    payload = json.dumps({"year": FISCAL_YEAR, "schedules": sched_data, "areas": areas},
                         ensure_ascii=False, separators=(",", ":"))
    src = out_html.read_text(encoding="utf-8")
    start, end = "/*CAL-DATA-START*/", "/*CAL-DATA-END*/"
    i, j = src.index(start) + len(start), src.index(end)
    out_html.write_text(src[:i] + payload + src[j:], encoding="utf-8")
    print("wrote", out_html, len(payload), "bytes")


if __name__ == "__main__":
    main()
