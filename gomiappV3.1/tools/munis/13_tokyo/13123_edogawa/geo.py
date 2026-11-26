"""東京都 江戸川区（13123）：e-Stat の町丁 → アプリの地区（ごみ収集・資源回収地域別曜日表の行）。

このファイルのきまり（tools/build_geo.py から使う）:
  town_info(towns, cal) … e-Stat の町丁ごとに、アプリの地区との対応を返す（c：地区の候補の番号の一覧）
  extra(cal)            … 自治体ぜんたいの追加データ（なければ {}）
  search_words(cal)     … 検索用の町名に足す呼び名 {呼び名: [地区の番号, …]}
地図（KML）は 元データ/13_東京都/13123_江戸川区/地図/r2ka13123.kml

地区名は「一之江1〜5丁目」「一之江町」（全域）「江戸川2丁目（1〜10）（16〜31）〜4丁目（1〜14）」「清新町1丁目　（1）清新中央ハイツ…」の形。
  ・かっこの中（番地・建物）は見ないで、地区名の中の「○丁目」の町丁を候補にする（番地で分かれているところは、同じ丁目に候補が2つ以上になる）。
  ・丁目がない地区（全域）は、その町のすべての町丁。
"""
import re
import unicodedata

TOWN_SEARCH = True
KANJI = {"一": 1, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9}


def loose(s):
    return unicodedata.normalize("NFKC", s).replace("～", "〜").replace("~", "〜")


def nums(spec):
    """「1・3〜5」→ [1, 3, 4, 5]"""
    out = []
    for part in spec.split("・"):
        a, _, b = part.partition("〜")
        out += list(range(int(a), int(b or a) + 1))
    return out


def area_keys(n):
    """地区名 → (町名, 丁目の一覧 / None（町ぜんぶ）)"""
    n = re.sub(r"\([^)]*\)", "", loose(n))
    m = re.match(r"(\D+?)(\d.*)?$", n)
    town, rest = m[1].strip(), (m[2] or "").replace("丁目〜", "〜")
    ch = sorted({k for s in re.findall(r"(\d+(?:[・〜]\d+)*)丁目", rest) for k in nums(s)})
    return town, ch or None


def estat(t):
    """e-Stat の町名 → (町名, 丁目 / None)"""
    m = re.fullmatch(r"(.+?)([一二三四五六七八九])丁目", loose(t))
    return (m[1], KANJI[m[2]]) if m else (loose(t), None)


def town_info(towns, cal):
    keys = [area_keys(a["n"]) for a in cal["areas"]]
    out, miss, multi = [], [], 0
    for t in towns:
        town, ch = estat(t["name"])
        c = [i for i, (tw, chs) in enumerate(keys) if tw == town and (chs is None or ch in chs)]
        if not c:
            miss.append(t["name"])
        elif len(c) > 1:
            multi += 1
        out.append({"c": c})
    print(f"  江戸川区：地区が決まらない町丁 {len(miss)}／{len(towns)}（{'・'.join(sorted(set(miss)))}）、地区の候補が2つ以上 {multi}")
    return out


def extra(cal):
    return {}


def search_words(cal):
    """丁目ごとの名前（「西瑞江4丁目」で探せる）"""
    out = {}
    for i, a in enumerate(cal["areas"]):
        town, chs = area_keys(a["n"])
        for k in chs or []:
            out.setdefault(f"{town}{k}丁目", set()).add(i)
        out.setdefault(town, set()).add(i)
    return {k: sorted(v) for k, v in out.items()}
