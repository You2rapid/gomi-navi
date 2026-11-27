"""東京都 墨田区（13107）：e-Stat の町丁 → アプリの地区（区のカレンダーの「対象地域」12）。

このファイルのきまり（tools/build_geo.py から使う）:
  town_info(towns, cal) … e-Stat の町丁ごとに、アプリの地区との対応を返す（c：地区の候補の番号の一覧）
  extra(cal)            … 自治体ぜんたいの追加データ（なければ {}）
  search_words(cal)     … 検索用の町名に足す呼び名 {呼び名: [地区の番号, …]}
地図（KML）は 元データ/13_東京都/13107_墨田区/地図/r2ka13107.kml

地区名は「両国、亀沢、石原、横網」「本所1〜2丁目、東駒形1〜2丁目、吾妻橋、向島1〜3丁目」の形（区のカレンダーの書き方）。
  ・丁目のない町（両国など）は、その町のどの丁目もその地区。丁目のある町は、その丁目だけ。
"""
import re
import unicodedata

TOWN_SEARCH = True
KANJI = "一二三四五六七八九"


def towns_of(name):
    """地区名 → {(町名, 丁目 か None)}"""
    out = set()
    for part in re.split(r"[、 ]+", unicodedata.normalize("NFKC", name).replace("～", "〜")):
        m = re.fullmatch(r"(\D+?)([\d・〜]+)丁目", part)
        if not m:
            out.add((part, None))
            continue
        for p in m[2].split("・"):
            a, _, b = p.partition("〜")
            for n in range(int(a), int(b or a) + 1):
                out.add((m[1], n))
    return out


def town_info(towns, cal):
    keys = [towns_of(a["n"]) for a in cal["areas"]]
    out, miss = [], []
    for t in towns:
        name = unicodedata.normalize("NFKC", t["name"]).strip()
        m = re.fullmatch(r"(.+?)([一二三四五六七八九])丁目", name)
        base, ch = (m[1], KANJI.index(m[2]) + 1) if m else (name, None)
        c = [i for i, ks in enumerate(keys) if (base, None) in ks or (ch is not None and (base, ch) in ks)]
        if not c:
            miss.append(t["name"])
        out.append({"c": c})
    print(f"  墨田区：地区が決まらない町丁 {len(miss)}／{len(towns)}（{'・'.join(sorted(set(miss)))}）")
    return out


def extra(cal):
    return {}


def search_words(cal):
    """町名（「両国」「向島」で探せる）と、丁目ごとの名前（「向島3丁目」「向島三丁目」で探せる）"""
    out = {}
    for i, a in enumerate(cal["areas"]):
        for tw, ch in towns_of(a["n"]):
            out.setdefault(tw, set()).add(i)
            if ch:
                out.setdefault(f"{tw}{ch}丁目", set()).add(i)
                out.setdefault(f"{tw}{KANJI[ch - 1]}丁目", set()).add(i)
    return {k: sorted(v) for k, v in out.items()}
