"""東京都 練馬区（13120）：e-Stat の町丁 → アプリの地区（地域別収集曜日一覧の行）。

このファイルのきまり（tools/build_geo.py から使う）:
  town_info(towns, cal) … e-Stat の町丁ごとに、アプリの地区との対応を返す（c：地区の候補の番号の一覧）
  extra(cal)            … 自治体ぜんたいの追加データ（なければ {}）
  search_words(cal)     … 検索用の町名に足す呼び名 {呼び名: [地区の番号, …]}
地図（KML）は 元データ/13_東京都/13120_練馬区/地図/r2ka13120.kml

地区名は「大泉学園町4〜7丁目」「春日町」（全域）「北町（1~3丁目・5~8丁目）」「光が丘（1丁目2番2号棟 2丁目9番）」の形。
  ・丁目のある地区は、その丁目の町丁。
  ・かっこの中に丁目があれば、その丁目の町丁（光が丘・北町・田柄の団地や宿舎。同じ丁目の中で建物ごとに日がちがうので、候補が2つ以上になる）。
  ・丁目がない地区（全域・「旭町（都営光が丘第一アパート）」など）は、その町のすべての町丁。
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
    n = loose(n)
    m = re.fullmatch(r"(.+?)\((.+)\)", n)
    if m:
        ch = [k for s in re.findall(r"(\d+(?:[・〜]\d+)*)丁目", m[2]) for k in nums(s)]
        return m[1], sorted(set(ch)) or None
    m = re.fullmatch(r"(.+?)([\d・〜]+)丁目", n)
    if m:
        return m[1], nums(m[2])
    return n, None


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
    print(f"  練馬区：地区が決まらない町丁 {len(miss)}／{len(towns)}（{'・'.join(sorted(set(miss)))}）、地区の候補が2つ以上 {multi}")
    return out


def extra(cal):
    return {}


def search_words(cal):
    """丁目ごとの名前（「大泉学園町5丁目」で探せる）"""
    out = {}
    for i, a in enumerate(cal["areas"]):
        town, chs = area_keys(a["n"])
        for k in chs or []:
            out.setdefault(f"{town}{k}丁目", set()).add(i)
        out.setdefault(town, set()).add(i)
    return {k: sorted(v) for k, v in out.items()}
