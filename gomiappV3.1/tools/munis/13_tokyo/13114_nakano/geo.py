"""東京都 中野区（13114）：e-Stat の町丁 → アプリの地区（区の「ごみ収集・資源回収一覧」の町名・丁目の行）。

このファイルのきまり（tools/build_geo.py から使う）:
  town_info(towns, cal) … e-Stat の町丁ごとに、アプリの地区との対応を返す（c：地区の候補の番号の一覧）
  extra(cal)            … 自治体ぜんたいの追加データ（なければ {}）
  search_words(cal)     … 検索用の町名に足す呼び名 {呼び名: [地区の番号, …]}
地図（KML）は 元データ/13_東京都/13114_中野区/地図/r2ka13114.kml

地区名は「新井1・2・4・5丁目」「江原町」（区の表で「全域」の町は町名だけ）の形。
  ・e-Stat の「新井一丁目」は、町名が「新井」で、丁目の並びに 1 がある地区。
  ・町名だけの地区（江原町・上鷺宮・沼袋・南台）は、e-Stat のその町のどの丁目もその地区。
"""
import re
import unicodedata

TOWN_SEARCH = True
KANJI = "一二三四五六七八九"


def split(n):
    """地区名 → (町名, {丁目の番号} か None（全域）)"""
    m = re.fullmatch(r"(.+?)(\d+(?:・\d+)*)丁目", n)
    if m:
        return m[1], {int(x) for x in m[2].split("・")}
    return n, None


def town_info(towns, cal):
    keys = [split(a["n"]) for a in cal["areas"]]
    out, miss = [], []
    for t in towns:
        name = unicodedata.normalize("NFKC", t["name"]).strip()
        m = re.fullmatch(r"(.+?)([一二三四五六七八九])丁目", name)
        base, ch = (m[1], KANJI.index(m[2]) + 1) if m else (name, None)
        c = [i for i, (tw, chs) in enumerate(keys) if tw == base and (chs is None or ch in chs)]
        if not c:
            miss.append(t["name"])
        out.append({"c": c})
    print(f"  中野区：地区が決まらない町丁 {len(miss)}／{len(towns)}（{'・'.join(sorted(set(miss)))}）")
    return out


def extra(cal):
    return {}


def search_words(cal):
    """町名（「新井」で探せる）と、丁目ごとの名前（「新井3丁目」「新井三丁目」で探せる）"""
    out = {}
    for i, a in enumerate(cal["areas"]):
        tw, chs = split(a["n"])
        out.setdefault(tw, set()).add(i)
        for ch in sorted(chs or []):
            out.setdefault(f"{tw}{ch}丁目", set()).add(i)
            out.setdefault(f"{tw}{KANJI[ch - 1]}丁目", set()).add(i)
    return {k: sorted(v) for k, v in out.items()}
