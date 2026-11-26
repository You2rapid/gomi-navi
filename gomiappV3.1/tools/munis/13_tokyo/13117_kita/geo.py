"""東京都 北区（13117）：e-Stat の町丁 → アプリの地区（区の「ごみ・資源の収集日」の表の町名・地区）。

このファイルのきまり（tools/build_geo.py から使う）:
  town_info(towns, cal) … e-Stat の町丁ごとに、アプリの地区との対応を返す（c：地区の候補の番号の一覧）
  extra(cal)            … 自治体ぜんたいの追加データ（なければ {}）
  search_words(cal)     … 検索用の町名に足す呼び名 {呼び名: [地区の番号, …]}
地図（KML）は 元データ/13_東京都/13117_北区/地図/r2ka13117.kml

地区名は「赤羽一丁目（1〜9番）」「赤羽南」「王子五丁目（王子五丁目団地）」の形（区の表の町名＋かっこに地区）。
  ・e-Stat の「赤羽一丁目」は、町名が「赤羽一丁目」の地区（番地・団地で分かれる丁目は候補が2〜4つ。使う人がえらぶ）。
  ・区の表で丁目のない町名（赤羽南・堀船・岸町・昭和町・東十条・田端新町）は「全域」なので、e-Stat のどの丁目もその地区。
  ・区の表は「桐ケ丘」「西ケ原」、e-Stat は「桐ヶ丘」「西ヶ原」なので、ヶ と ケ は同じとみる。
"""
import re
import unicodedata

TOWN_SEARCH = True
KANJI = {"一": 1, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9}


def loose(s):
    return unicodedata.normalize("NFKC", s).replace("ヶ", "ケ").strip()


def area_town(n):
    """地区名 → 区の表の町名（かっこの前）"""
    return loose(re.sub(r"（.*）$", "", n))


def base(t):
    return re.sub(r"[一二三四五六七八九]丁目$", "", t)


def town_info(towns, cal):
    keys = [area_town(a["n"]) for a in cal["areas"]]
    out, miss, multi = [], [], []
    for t in towns:
        name = loose(t["name"])
        c = [i for i, k in enumerate(keys) if k == name]
        if not c:
            c = [i for i, k in enumerate(keys) if k == base(name)]
        if not c:
            miss.append(t["name"])
        elif len({cal["areas"][i]["s"] for i in c}) > 1:
            multi.append(t["name"])
        out.append({"c": c})
    print(f"  北区：地区が決まらない町丁 {len(miss)}／{len(towns)}（{'・'.join(sorted(set(miss)))}）、"
          f"収集日の候補が2つ以上 {len(multi)}（{'・'.join(sorted(set(multi)))}）")
    return out


def extra(cal):
    return {}


def search_words(cal):
    """町名（「赤羽」で探せる）と、丁目を数字で書いた名前（「赤羽1丁目」で探せる）"""
    out = {}
    for i, a in enumerate(cal["areas"]):
        t = area_town(a["n"])
        m = re.fullmatch(r"(.+?)([一二三四五六七八九])丁目", t)
        if m:
            out.setdefault(f"{m[1]}{KANJI[m[2]]}丁目", set()).add(i)
            out.setdefault(m[1], set()).add(i)
        else:
            out.setdefault(t, set()).add(i)
    return {k: sorted(v) for k, v in out.items()}
