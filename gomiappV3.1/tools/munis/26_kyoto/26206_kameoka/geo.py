"""京都府 亀岡市（26206）：e-Stat の町丁 → アプリの地区（町ごとのカレンダー24）。

このファイルのきまり（tools/build_geo.py から使う）:
  town_info(towns, cal) … e-Stat の町丁（towns：名前 name・代表点 x, y・形 rings）ごとに、アプリの地区との対応を返す（c：地区の候補の番号の一覧）
  extra(cal)            … 自治体ぜんたいの追加データ（なければ {}）
  search_words(cal)     … 検索用の町名に足す呼び名 {呼び名: [地区の番号, …]}
地図（KML）は 元データ/26_京都府/26206_亀岡市/地図/r2ka26206.kml

町と地区の対応は、市の「令和8年度ごみ出しカレンダーを掲載します」のページ（決まり A1）：
  ・地区名が町名のもの（旭町・大井町・東つつじケ丘…）は、e-Stat の町名がその町名で始まれば、その地区。
  ・亀岡地区（東部・中部・西部）と篠町（Ⅰ・Ⅱ）は、ページの表の町名（calendar.py が地区の説明 d に入れたもの）でくらべる。
    「柏原（西川より西側）」「柏原（西川より東側）」は、e-Stat の町の形では分けられないので、Ⅰ・Ⅱの両方を候補にする。
  e-Stat の町名は「篠町第一見晴」「荒塚町紺屋町」のように、町名のあとに自治会などの名前が付くので、前から合わせる。
表にない篠町の町（篠町森宮・篠町森東・篠町雲宮など。表の「森」と同じとは言えない）は、地区を決めない（推測しない）。
"""
import re
import unicodedata

TOWN_SEARCH = True     # 亀岡地区・篠町は地区名が町名ではないので、町名で探せるようにする（決まり B2）
SPLIT = ("亀岡地区東部", "亀岡地区中部", "亀岡地区西部", "篠町Ⅰ", "篠町Ⅱ")


def loose(s):
    """表記ゆれをそろえる（ヶ・ケ、稗・薭、篭・籠、常盤・常磐、全角・半角）"""
    s = unicodedata.normalize("NFKC", s)
    return s.translate(str.maketrans({"ヶ": "ケ", "稗": "薭", "篭": "籠", "盤": "磐"}))


def town_index(cal):
    """[(町名の頭, 篠町の中の名前か None, [地区の番号])]"""
    idx = {}
    for i, a in enumerate(cal["areas"]):
        if a["n"] in SPLIT:
            for t in a.get("d", "").split("、"):
                t = re.sub(r"（.*?）|\d+〜\d+丁目$", "", t)
                key = ("篠町" + t) if a["n"].startswith("篠町") else t
                idx.setdefault(loose(key), set()).add(i)
        else:
            idx.setdefault(loose(a["n"]), set()).add(i)
    return {k: sorted(v) for k, v in idx.items()}


def candidates(name, idx):
    n = loose(name)
    n = re.sub(r"^篠町第[一二三四五六七八九十]+", "篠町", n)      # 篠町第一見晴 → 篠町見晴
    n = re.sub(r"[一二三四五六七八九十]+丁目$", "", n)             # 篠町夕日ケ丘一丁目 → 篠町夕日ケ丘
    # 篠町の中は、表の名前とぴったり同じ町だけ（「篠町森宮」を「森」にしない。推測しない）。ほかは町名で始まれば、その町
    keys = [k for k in idx if (n == k if k.startswith("篠町") else n.startswith(k))]
    if not keys:
        return []
    return idx[max(keys, key=len)]


def town_info(towns, cal):
    idx = town_index(cal)
    out, miss, multi = [], [], 0
    for t in towns:
        c = candidates(t["name"], idx)
        if not c:
            miss.append(t["name"])
        elif len(c) > 1:
            multi += 1
        out.append({"c": c})
    print(f"  亀岡市：地区が決まらない町丁 {len(miss)}／{len(towns)}（{'・'.join(sorted(set(miss)))}）、地区の候補が2つ以上 {multi}")
    return out


def extra(cal):
    return {}


def search_words(cal):
    """亀岡地区・篠町の表の町名（e-Stat にない町名も、市の資料にあるので探せるようにする）"""
    out = {}
    for i, a in enumerate(cal["areas"]):
        if a["n"] in SPLIT:
            for t in a.get("d", "").split("、"):
                t = re.sub(r"（.*?）", "", t)
                out.setdefault(t, set()).add(i)
    return {k: sorted(v) for k, v in out.items()}
