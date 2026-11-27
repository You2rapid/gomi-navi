"""東京都 豊島区（13116）：e-Stat の町丁 → アプリの地区（区の「回収・収集曜日一覧」の町丁名の行）。

このファイルのきまり（tools/build_geo.py から使う）:
  town_info(towns, cal) … e-Stat の町丁ごとに、アプリの地区との対応を返す（c：地区の候補の番号の一覧）
  extra(cal)            … 自治体ぜんたいの追加データ（なければ {}）
  search_words(cal)     … 検索用の町名に足す呼び名 {呼び名: [地区の番号, …]}
地図（KML）は 元データ/13_東京都/13116_豊島区/地図/r2ka13116.kml

地区名は「池袋1・4丁目」「池袋本町1〜4丁目」「要町1丁目1番〜8番」「池袋2丁目14番5号・8号、15番2号〜3号…」の形。
  ・地区名の頭の「町名＋丁目の並び（1・4／1〜4）」で、e-Stat の「池袋一丁目」などと対応させる。
  ・番地で分かれる丁目（要町1丁目など）は、e-Stat では番地まで分けられないので、候補が2つ以上になる（使う人がえらぶ）。
"""
import re
import unicodedata

TOWN_SEARCH = True
KANJI = "一二三四五六七八九"


def split(n):
    """地区名 → (町名, {丁目の番号})"""
    n = unicodedata.normalize("NFKC", n)
    m = re.match(r"(.+?)(\d+(?:[・〜]\d+)*)丁目", n)
    if not m:
        raise ValueError(f"地区名の形がわからない：{n}")
    chs = set()
    for part in m[2].split("・"):
        a, _, b = part.partition("〜")
        chs |= set(range(int(a), int(b or a) + 1))
    return m[1], chs


def town_info(towns, cal):
    keys = [split(a["n"]) for a in cal["areas"]]
    out, miss, multi = [], [], []
    for t in towns:
        name = unicodedata.normalize("NFKC", t["name"]).strip()
        m = re.fullmatch(r"(.+?)([一二三四五六七八九])丁目", name)
        base, ch = (m[1], KANJI.index(m[2]) + 1) if m else (name, None)
        c = [i for i, (tw, chs) in enumerate(keys) if tw == base and ch in chs]
        if not c:
            miss.append(t["name"])
        elif len({cal["areas"][i]["s"] for i in c}) > 1:
            multi.append(t["name"])
        out.append({"c": c})
    print(f"  豊島区：地区が決まらない町丁 {len(miss)}／{len(towns)}（{'・'.join(sorted(set(miss)))}）、"
          f"収集日の候補が2つ以上 {len(multi)}（{'・'.join(sorted(set(multi)))}）")
    return out


def extra(cal):
    return {}


def search_words(cal):
    """町名（「池袋」で探せる）と、丁目ごとの名前（「池袋2丁目」「池袋二丁目」で探せる）"""
    out = {}
    for i, a in enumerate(cal["areas"]):
        tw, chs = split(a["n"])
        out.setdefault(tw, set()).add(i)
        for ch in sorted(chs):
            out.setdefault(f"{tw}{ch}丁目", set()).add(i)
            out.setdefault(f"{tw}{KANJI[ch - 1]}丁目", set()).add(i)
    return {k: sorted(v) for k, v in out.items()}
