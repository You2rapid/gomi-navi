"""京都府 長岡京市（26209）：e-Stat の町丁 → アプリの地区（分別収集日程表の地域の町名）。

このファイルのきまり（tools/build_geo.py から使う）:
  town_info(towns, cal) … e-Stat の町丁ごとに、アプリの地区との対応を返す（c：地区の候補の番号の一覧）
  extra(cal)            … 自治体ぜんたいの追加データ（なければ {}）
  search_words(cal)     … 検索用の町名に足す呼び名 {呼び名: [地区の番号, …]}
地図（KML）は 元データ/26_京都府/26209_長岡京市/地図/r2ka26209.kml

地区名は、しおりの分別収集日程表の地域の町名（「長岡1〜3丁目」「今里（南平尾）」など）。
e-Stat の町名は「長岡一丁目」「神足古市」「粟生畑ケ田」「奥海印寺東山」「今里今里」のように書き方がちがうので、
地区名を丁目ごとに分けた名前と、下の ALIAS（大字の中の地名）でくらべる。
  ・e-Stat の「今里今里」（丁目のない今里）は、今里（更ノ町・評町・北ノ町・川原）と今里（南平尾）の両方を候補にする（e-Stat の形では分けられない）。
  ・e-Stat の「勝竜寺住居表示以外」は勝竜寺。
表にない町（あかね台・小畑町・彦林・舞塚・南浦など、e-Stat に同じ名前の町がないもの）は、地図からは選べない（地区の一覧・検索から選ぶ）。
"""
import re
import unicodedata

TOWN_SEARCH = True
KANJI = {"一": 1, "二": 2, "三": 3, "四": 4, "五": 5}

# e-Stat の町名 → 地区名（大字の中の地名を、しおりの書き方にする）
ALIAS = {
    "馬場馬場": ["馬場"], "神足神足": ["神足"], "神足古市": ["古市（在）"], "勝竜寺勝竜寺": ["勝竜寺"], "勝竜寺住居表示以外": ["勝竜寺"],
    "今里今里": ["今里（更ノ町・評町・北ノ町・川原）", "今里（南平尾）"], "今里薬師堂": ["薬師堂"],
    "粟生粟生": ["粟生"], "粟生畑ケ田": ["畑ケ田"], "粟生田内": ["田内"],
    "奥海印寺奥海印寺": ["奥海印寺"], "奥海印寺東山": ["東山"], "奥海印寺太鼓山": ["太鼓山"], "奥海印寺谷田": ["谷田"], "奥海印寺森ノ下": ["森ノ下"],
    "友岡友岡": ["友岡"],
}


def loose(s):
    return unicodedata.normalize("NFKC", s).replace("ヶ", "ケ").replace("～", "〜").replace("~", "〜")


def area_names(n):
    """地区名 → くらべる名前（「長岡1〜3丁目」→ 長岡1丁目・長岡2丁目・長岡3丁目、「八条が丘」→ 八条が丘）"""
    n = loose(n)
    m = re.fullmatch(r"(.+?)([\d・〜]+)丁目", n)
    if not m:
        return [n]
    nums = []
    for part in m[2].split("・"):
        if "〜" in part:
            a, b = map(int, part.split("〜"))
            nums += list(range(a, b + 1))
        else:
            nums.append(int(part))
    return [f"{m[1]}{k}丁目" for k in nums]


def estat_name(t):
    """e-Stat の町名の丁目を数字にする（長岡一丁目 → 長岡1丁目）"""
    return re.sub(r"([一二三四五])丁目$", lambda m: f"{KANJI[m[1]]}丁目", loose(t))


def town_index(cal):
    idx = {}
    for i, a in enumerate(cal["areas"]):
        for k in area_names(a["n"]):
            idx.setdefault(k, set()).add(i)
    return idx


def candidates(name, cal, idx):
    n = estat_name(name)
    names = {a["n"]: i for i, a in enumerate(cal["areas"])}
    if n in ALIAS:
        return sorted(names[x] for x in ALIAS[n])
    if n in idx:
        return sorted(idx[n])
    base = re.sub(r"\d+丁目$", "", n)       # 八条が丘1丁目 → 八条が丘、花山1丁目 → 花山（地区名に丁目がないもの）
    if base in idx and not any(re.search(r"\d+丁目$", k) for k in idx if k.startswith(base) and k != base):
        return sorted(idx[base])
    return []


def town_info(towns, cal):
    idx = town_index(cal)
    out, miss, multi = [], [], 0
    for t in towns:
        c = candidates(t["name"], cal, idx)
        if not c:
            miss.append(t["name"])
        elif len(c) > 1:
            multi += 1
        out.append({"c": c})
    print(f"  長岡京市：地区が決まらない町丁 {len(miss)}／{len(towns)}（{'・'.join(sorted(set(miss)))}）、地区の候補が2つ以上 {multi}")
    return out


def extra(cal):
    return {}


def search_words(cal):
    """地区名を丁目ごとに分けた名前（「長岡2丁目」で探せる）と、今里の中の地名"""
    out = {}
    for i, a in enumerate(cal["areas"]):
        for k in area_names(a["n"]):
            out.setdefault(k, set()).add(i)
        for w in re.findall(r"[（(](.+?)[）)]", a["n"]):
            for x in w.split("・"):
                out.setdefault(x, set()).add(i)
    return {k: sorted(v) for k, v in out.items()}
