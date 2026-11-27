"""東京都 目黒区（13110）：e-Stat の町丁 → アプリの地区（区の収集曜日一覧表・地域別カレンダーの「町名・丁目」の地域）。

このファイルのきまり（tools/build_geo.py から使う）:
  town_info(towns, cal) … e-Stat の町丁ごとに、アプリの地区との対応を返す（c：地区の候補の番号の一覧）
  extra(cal)            … 自治体ぜんたいの追加データ（なければ {}）
  search_words(cal)     … 検索用の町名に足す呼び名 {呼び名: [地区の番号, …]}
地図（KML）は 元データ/13_東京都/13110_目黒区/地図/r2ka13110.kml

地区名は「青葉台1〜3丁目」「大岡山1・2丁目」「目黒1丁目」の形（区のカレンダーの書き方）。
  ・e-Stat の「青葉台二丁目」は、町名が「青葉台」で、丁目の範囲に 2 がある地区。
"""
import re
import unicodedata

TOWN_SEARCH = True
KANJI = "一二三四五六七八九"


def split(n):
    """地区名 → (町名, {丁目の番号})"""
    m = re.fullmatch(r"(.+?)(\d+)(?:([〜・])(\d+))?丁目", n)
    if not m:
        raise ValueError(f"地区名の形がちがう：{n}")
    a, b = int(m[2]), int(m[4] or m[2])
    return m[1], (set(range(a, b + 1)) if m[3] == "〜" else {a, b})


def town_info(towns, cal):
    keys = [split(a["n"]) for a in cal["areas"]]
    out, miss = [], []
    for t in towns:
        name = unicodedata.normalize("NFKC", t["name"]).strip()
        m = re.fullmatch(r"(.+?)([一二三四五六七八九])丁目", name)
        base, ch = (m[1], KANJI.index(m[2]) + 1) if m else (name, None)
        c = [i for i, (tw, chs) in enumerate(keys) if tw == base and ch in chs]
        if not c:
            miss.append(t["name"])
        out.append({"c": c})
    print(f"  目黒区：地区が決まらない町丁 {len(miss)}／{len(towns)}（{'・'.join(sorted(set(miss)))}）")
    return out


def extra(cal):
    return {}


def search_words(cal):
    """町名（「青葉台」で探せる）と、丁目ごとの名前（「青葉台2丁目」「青葉台二丁目」で探せる）"""
    out = {}
    for i, a in enumerate(cal["areas"]):
        tw, chs = split(a["n"])
        out.setdefault(tw, set()).add(i)
        for ch in sorted(chs):
            out.setdefault(f"{tw}{ch}丁目", set()).add(i)
            out.setdefault(f"{tw}{KANJI[ch - 1]}丁目", set()).add(i)
    return {k: sorted(v) for k, v in out.items()}
