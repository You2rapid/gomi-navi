"""東京都 町田市（13209）：e-Stat の町丁 → アプリの地区（市の「収集地区番号早見表」の行）。

このファイルのきまり（tools/build_geo.py から使う）:
  town_info(towns, cal) … e-Stat の町丁ごとに、アプリの地区との対応を返す（c：地区の候補の番号の一覧）
  extra(cal)            … 自治体ぜんたいの追加データ（なければ {}）
  search_words(cal)     … 検索用の町名に足す呼び名 {呼び名: [地区の番号, …]}
地図（KML）は 元データ/13_東京都/13209_町田市/地図/r2ka13209.kml

地区名は早見表の行：「相原町」「旭町1〜3丁目」「金井町・金井1〜8丁目」「金森2、3、7丁目」、
  住宅・団地は「町田木曽住宅（木曽東）」（かっこは早見表で前に書いてある町名）、特別指定団体は「玉川学園（特別指定団体の区域）」。
  ・e-Stat の「旭町二丁目」は、地区名に「旭町」と2丁目が入っている地区。
  ・住宅・団地・特別指定団体は、e-Stat の町丁では分けられないので、かっこの町（木曽東・森野・山崎町など）のどの町丁でも候補に足す（使う人がえらぶ）。
  ・e-Stat の「山崎」（丁目なし）は、早見表の「山崎1丁目」。
  ・早見表は「能ヶ谷」、e-Stat は「能ケ谷」なので、ヶ と ケ は同じとみる。
"""
import re
import unicodedata

TOWN_SEARCH = True
KANJI = {"一": 1, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9}
NUM = "〇一二三四五六七八九"


def loose(s):
    return unicodedata.normalize("NFKC", s).replace("ヶ", "ケ").replace("～", "〜").strip()


def nums(spec):
    out = set()
    for part in re.split(r"[、,]", spec):
        a, _, b = part.partition("〜")
        out |= set(range(int(a), int(b or a) + 1))
    return out


def area_parts(n):
    """地区名 → ([(町名, 丁目の集合 / None)], かっこの町（住宅・団体のとき）/ None)"""
    n = loose(n)
    m = re.fullmatch(r"(.+?)\((.+)\)", n)
    base, paren = (m[1], m[2]) if m else (n, None)
    if paren == "特別指定団体の区域":
        return [], base
    parts = []
    for p in base.split("・"):
        mm = re.fullmatch(r"(\D+?)([\d〜、]+)丁目", p)
        parts.append((mm[1], nums(mm[2])) if mm else (p, None))
    if paren and paren != "特別指定団体除く":          # 「町田木曽住宅（木曽東）」：住宅の名前は町名ではない
        return [], paren
    return parts, None


def estat(t):
    m = re.fullmatch(r"(.+?)([一二三四五六七八九])丁目", loose(t))
    return (m[1], KANJI[m[2]]) if m else (loose(t), None)


def town_info(towns, cal):
    keys = [area_parts(a["n"]) for a in cal["areas"]]
    out, miss, multi = [], [], []
    for t in towns:
        town, ch = estat(t["name"])
        c = [i for i, (ps, _) in enumerate(keys) if any(tw == town and (chs is None if ch is None else chs is not None and ch in chs) for tw, chs in ps)]
        if not c and ch is None:        # e-Stat の「山崎」＝ 早見表の「山崎1丁目」
            c = [i for i, (ps, _) in enumerate(keys) if any(tw == town and chs == {1} for tw, chs in ps)]
        c += [i for i, (_, par) in enumerate(keys) if par == town and i not in c]
        if not c:
            miss.append(t["name"])
        elif len({cal["areas"][i]["s"] for i in c}) > 1:
            multi.append(t["name"])
        out.append({"c": c})
    print(f"  町田市：地区が決まらない町丁 {len(miss)}／{len(towns)}（{'・'.join(sorted(set(miss)))}）、"
          f"収集日の候補が2つ以上 {len(multi)}（{'・'.join(sorted(set(multi)))}）")
    return out


def extra(cal):
    return {}


def search_words(cal):
    """町名（「金井」「木曽東」で探せる）と、丁目ごとの名前（「金井3丁目」「金井三丁目」）"""
    out = {}
    for i, a in enumerate(cal["areas"]):
        ps, par = area_parts(a["n"])
        if par:
            out.setdefault(par, set()).add(i)
        for town, chs in ps:
            out.setdefault(town, set()).add(i)
            for k in sorted(chs or []):
                out.setdefault(f"{town}{k}丁目", set()).add(i)
                out.setdefault(f"{town}{NUM[k]}丁目", set()).add(i)
    return {k: sorted(v) for k, v in out.items()}
