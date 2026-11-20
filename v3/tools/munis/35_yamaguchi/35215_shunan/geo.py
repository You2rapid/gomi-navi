"""山口県 周南市（35215）：町丁 → 収集日の地区（町名・日程）の候補。

このファイルのきまり（tools/build_geo.py から使う）:
  town_info(towns, cal) … e-Stat の町丁（towns：名前 name・代表点 x, y・形 rings）ごとに、アプリの地区との対応を返す
                           （c：地区の候補の番号の一覧、r：地域、side：線と関係なく決まっている地区 など）
  extra(cal)            … 自治体ぜんたいの追加データ（境目の線など。なければ {}）
地図（KML）は 元データ/<県>/<自治体>/地図/r2ka<自治体コード>.kml
"""
import re

# 周南市：e-Stat の町名とアプリの地区名で呼び方がちがうもの
ALIAS = {"櫛ケ浜": ["櫛浜"], "須万": ["須金"], "金峰": ["須金"], "鹿野上": ["鹿野地域"], "鹿野中": ["鹿野地域"],
         "鹿野下": ["鹿野地域"], "大潮": ["鹿野地域"], "巣山": ["鹿野地域"], "須万鹿野": ["鹿野地域"], "金峰鹿野": ["鹿野地域"],
         "高瀬": ["和田"], "夏切": ["和田"], "垰": ["和田"], "米光": ["和田"], "馬神": ["和田"], "福川羽島": ["羽島"],
         "一番町": ["一番丁"]}
KANSUJI = "〇一二三四五六七八九"

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

def town_info(towns, cal):
    areas = cal["areas"]
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
    return [{"r": r, "c": c[:8]} for c, r in zip(cands, region)]


def extra(cal):
    return {}
