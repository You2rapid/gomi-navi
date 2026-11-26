"""東京都 世田谷区（13112）：e-Stat の町丁 → アプリの地区（区のカレンダーの対象地区の一覧の「町名丁目」）。

このファイルのきまり（tools/build_geo.py から使う）:
  town_info(towns, cal) … e-Stat の町丁ごとに、アプリの地区との対応を返す（c：地区の候補の番号の一覧）
  extra(cal)            … 自治体ぜんたいの追加データ（なければ {}）
  search_words(cal)     … 検索用の町名に足す呼び名 {呼び名: [地区の番号, …]}
地図（KML）は 元データ/13_東京都/13112_世田谷区/地図/r2ka13112.kml

地区名は「赤堤1・3〜5丁目」「砧公園」のように、町名と丁目の一覧。e-Stat の町名は「赤堤一丁目」なので、丁目ごとにくらべる。
集合住宅の地区（「都営池尻二丁目アパート（池尻2丁目3番）」など）は、かっこの中の丁目の町丁で、ふつうの地区といっしょに候補にする
（同じ丁目の中で、建物だけ収集日がちがう。地図では建物まで分けられないので、候補から選ぶ）。
"""
import re
import unicodedata

TOWN_SEARCH = True
KANJI = {"一": 1, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9}


def loose(s):
    return unicodedata.normalize("NFKC", s).replace("～", "〜").replace("~", "〜")


def area_keys(n):
    """地区名 → くらべる名前の一覧。
    「赤堤1・3〜5丁目」→ 赤堤1丁目・赤堤3丁目・赤堤4丁目・赤堤5丁目、「砧公園」→ 砧公園、
    「希望ヶ丘団地（船橋6丁目26番、7丁目1番、7丁目8番）」→ 船橋6丁目・船橋7丁目"""
    n = loose(n)
    m = re.fullmatch(r"(.+?)\((.+)\)", n)      # NFKC でかっこは半角になる
    if m:
        town = re.match(r"\D+", m[2])[0]
        return sorted({f"{town}{k}丁目" for k in re.findall(r"(\d+)丁目", m[2])})
    m = re.fullmatch(r"(.+?)([\d・〜]+)丁目", n)
    if not m:
        return [n]
    nums = []
    for part in m[2].split("・"):
        a, _, b = part.partition("〜")
        nums += list(range(int(a), int(b or a) + 1))
    return [f"{m[1]}{k}丁目" for k in nums]


def estat_name(t):
    """e-Stat の町名の丁目を数字にする（赤堤一丁目 → 赤堤1丁目）"""
    return re.sub(r"([一二三四五六七八九])丁目$", lambda m: f"{KANJI[m[1]]}丁目", loose(t))


def town_index(cal):
    idx = {}
    for i, a in enumerate(cal["areas"]):
        for k in area_keys(a["n"]):
            idx.setdefault(k, set()).add(i)
    return idx


def town_info(towns, cal):
    idx = town_index(cal)
    out, miss, multi = [], [], 0
    for t in towns:
        c = sorted(idx.get(estat_name(t["name"]), []))
        if not c:
            miss.append(t["name"])
        elif len(c) > 1:
            multi += 1
        out.append({"c": c})
    print(f"  世田谷区：地区が決まらない町丁 {len(miss)}／{len(towns)}（{'・'.join(sorted(set(miss)))}）、地区の候補が2つ以上（集合住宅のある丁目） {multi}")
    return out


def extra(cal):
    return {}


def search_words(cal):
    """地区名を丁目ごとに分けた名前（「赤堤4丁目」で探せる）"""
    out = {}
    for i, a in enumerate(cal["areas"]):
        for k in area_keys(a["n"]):
            out.setdefault(k, set()).add(i)
    return {k: sorted(v) for k, v in out.items()}
