"""東京都 品川区（13109）：e-Stat の町丁 → アプリの地区（区の収集曜日一覧の町名・丁目）。

このファイルのきまり（tools/build_geo.py から使う）:
  town_info(towns, cal) … e-Stat の町丁ごとに、アプリの地区との対応を返す（c：地区の候補の番号の一覧）
  extra(cal)            … 自治体ぜんたいの追加データ（なければ {}）
  search_words(cal)     … 検索用の町名に足す呼び名 {呼び名: [地区の番号, …]}
地図（KML）は 元データ/13_東京都/13109_品川区/地図/r2ka13109.kml

地区名は「荏原2〜4丁目」「西大井1丁目（4番28号、…）」の形（区の収集曜日一覧）。葛飾区・江東区の geo.py と同じ形。
  ・番地・号棟で分かれる丁目（西大井1・6丁目、西品川1丁目、東大井5・6丁目、平塚2丁目、南大井6丁目、八潮5丁目）は、
    e-Stat の町丁では分けられないので、候補が2つになる（使う人がえらぶ）。
  ・e-Stat の「○○二丁目」は、地区名に2丁目が入っている地区を候補にする。なければ、丁目のない同じ町の地区。
"""
import re
import unicodedata

TOWN_SEARCH = True
KANJI = {"一": 1, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9}


def loose(s):
    return unicodedata.normalize("NFKC", s).replace("～", "〜").replace("~", "〜").replace("ヶ", "ケ").strip()


def nums(spec):
    out = set()
    for part in re.split(r"[・、]", spec):
        a, _, b = part.partition("〜")
        out |= set(range(int(a), int(b or a) + 1))
    return out


def area_keys(n):
    """地区名 → (町名, 丁目の集合 / None)"""
    n = re.sub(r"\(.*\)$", "", loose(n)).strip()
    n = re.sub(r"[0-9].*番地$", "", n)        # 「北野町1653〜1654番地」「長沼町1508番地、1515〜1520番地」
    m = re.match(r"(\D+?)([\d・、〜]+)丁目$", n)
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
        if not c:
            miss.append(t["name"])
        elif len({cal["areas"][i]["s"] for i in c}) > 1:
            multi.append(t["name"])
        out.append({"c": c})
    print(f"  品川区：地区が決まらない町丁 {len(miss)}／{len(towns)}（{'・'.join(sorted(set(miss)))}）、"
          f"収集地区の候補が2つ以上 {len(multi)}（{'・'.join(sorted(set(multi)))}）")
    return out


def extra(cal):
    return {}


def search_words(cal):
    """丁目ごとの名前（「暁町2丁目」で探せる）と町名"""
    out = {}
    for i, a in enumerate(cal["areas"]):
        town, chs = area_keys(a["n"])
        town = re.sub(r"\(.*\)$", "", unicodedata.normalize("NFKC", a["n"])).strip()
        town = re.sub(r"[\d・、〜～]+丁目$", "", town)
        town = re.sub(r"[0-9].*番地$", "", town)
        for k in sorted(chs or []):
            out.setdefault(f"{town}{k}丁目", set()).add(i)
        out.setdefault(town, set()).add(i)
    return {k: sorted(v) for k, v in out.items()}
