"""東京都 新宿区（13104）：e-Stat の町丁 → アプリの地区（区の「資源回収・ごみ収集日」の表の集積所の住所）。

このファイルのきまり（tools/build_geo.py から使う）:
  town_info(towns, cal) … e-Stat の町丁ごとに、アプリの地区との対応を返す（c：地区の候補の番号の一覧）
  extra(cal)            … 自治体ぜんたいの追加データ（なければ {}）
  search_words(cal)     … 検索用の町名に足す呼び名 {呼び名: [地区の番号, …]}
地図（KML）は 元データ/13_東京都/13104_新宿区/地図/r2ka13104.kml

地区名は「愛住町」「新宿3丁目」「上落合2・3丁目」「下落合2から4丁目」「荒木町（21から23番地）」の形（区の表のとおり）。
  ・e-Stat の「新宿三丁目」は、地区名の丁目に3が入っている「新宿」の地区。地番で分かれる町・丁目は候補が2つ以上になる（使う人がえらぶ）。
  ・e-Stat の「四谷」「戸塚町」は丁目がない（区の表は「四谷1丁目」「戸塚町1丁目」）ので、1丁目の地区にする。
"""
import re
import unicodedata

TOWN_SEARCH = True
KANJI = {"一": 1, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9}
NUM = "〇一二三四五六七八九"


def loose(s):
    return unicodedata.normalize("NFKC", s).replace("ヶ", "ケ").strip()


def nums(spec):
    out = set()
    for part in spec.split("・"):
        a, _, b = part.partition("から")
        out |= set(range(int(a), int(b or a) + 1))
    return out


def area_keys(n):
    """地区名 → (町名, 丁目の集合 / None)"""
    n = re.sub(r"\(.*$", "", loose(n))       # NFKC で「（」は「(」になる
    m = re.fullmatch(r"(\D+?)([\d・から]+)丁目", n)
    return (m[1], nums(m[2])) if m else (n, None)


def estat(t):
    m = re.fullmatch(r"(.+?)([一二三四五六七八九])丁目", loose(t))
    return (m[1], KANJI[m[2]]) if m else (loose(t), None)


def town_info(towns, cal):
    keys = [area_keys(a["n"]) for a in cal["areas"]]
    out, miss, multi = [], [], []
    for t in towns:
        town, ch = estat(t["name"])
        c = [i for i, (tw, chs) in enumerate(keys) if tw == town and chs is not None and ch in chs] if ch else []
        if not c:
            c = [i for i, (tw, chs) in enumerate(keys) if tw == town and chs is None]
        if not c and ch is None:        # 四谷・戸塚町（e-Stat は丁目なし、区の表は1丁目）
            c = [i for i, (tw, chs) in enumerate(keys) if tw == town and chs == {1}]
        if not c:
            miss.append(t["name"])
        elif len({cal["areas"][i]["s"] for i in c}) > 1:
            multi.append(t["name"])
        out.append({"c": c})
    print(f"  新宿区：地区が決まらない町丁 {len(miss)}／{len(towns)}（{'・'.join(sorted(set(miss)))}）、"
          f"収集日の候補が2つ以上 {len(multi)}（{'・'.join(sorted(set(multi)))}）")
    return out


def extra(cal):
    return {}


def search_words(cal):
    """町名（「新宿」で探せる）と、丁目ごとの名前（「新宿3丁目」「新宿三丁目」で探せる）"""
    out = {}
    for i, a in enumerate(cal["areas"]):
        town, chs = area_keys(a["n"])
        out.setdefault(town, set()).add(i)
        for k in sorted(chs or []):
            out.setdefault(f"{town}{k}丁目", set()).add(i)
            out.setdefault(f"{town}{NUM[k]}丁目", set()).add(i)
    return {k: sorted(v) for k, v in out.items()}
