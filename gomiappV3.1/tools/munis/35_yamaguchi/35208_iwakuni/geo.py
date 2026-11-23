"""山口県 岩国市（35208）：町丁 → 収集日の地区の候補。

このファイルのきまり（tools/build_geo.py から使う）:
  town_info(towns, cal) … e-Stat の町丁（towns：名前 name・代表点 x, y・形 rings）ごとに、アプリの地区との対応を返す
                           （c：地区の候補の番号の一覧、r：地域）
  extra(cal)            … 自治体ぜんたいの追加データ（なければ {}）
地図（KML）は 元データ/35_山口県/35208_岩国市/地図/r2ka35208.kml

対応のさせ方:
  ・e-Stat の町名の頭（由宇町・周東町・玖珂町・錦町・美川町・美和町・本郷町）で地域を決める。頭がないものは岩国地域
  ・地区名（市の地域のページの書き方）から、くらべる名前（キー）を作る
      「南岩国町一丁目1～23番」→ 南岩国町一丁目、「神東（大畑）」→ 神東大畑・神東、
      「河山〔小川・四馬神・添谷〕」→ 河山・小川・四馬神・添谷
  ・e-Stat の町名（頭と「字」をとったもの）が、キーと同じ ＞ キーで始まる ＞ キーをふくむ（2文字以上）の順に近い地区を候補にする
      同じ近さなら、長いキーの地区を先に（例：由宇町南沖一丁目 は「南」より「南沖」）
  ・「玖珂町全域」のように、地域にカレンダーが1つだけのところは、その地域のどの町もその地区
  ・柱島・本郷の西黒沢は、市のカレンダーがない（地区がない）ので、候補なし
"""
import re

PREFIX = {"由宇町": "由宇", "周東町": "周東", "玖珂町": "玖珂", "錦町": "錦", "美川町": "美川", "美和町": "美和", "本郷町": "本郷"}


def norm(s):
    return s.replace("ヶ", "ケ").replace("ヵ", "ケ").replace("字", "").replace("，", "").replace(",", "")


def area_keys(name):
    """地区名 → くらべる名前（キー）の一覧"""
    keys = []
    m = re.match(r"^(.+?)〔(.+?)〕?$", name)            # 河山〔小川・四馬神・添谷〕
    if m:
        keys = [m.group(1)] + m.group(2).split("・")
        return [norm(k) for k in keys]
    m = re.match(r"^(.+?)[（(](.+?)[）)]$", name)       # 神東（大畑）・下久原（泉町【JR岩徳線より北】）・上久原(高森南)
    if m and not re.search(r"[0-9]", m.group(2)):
        sub = re.sub(r"【.*?】|[（(].*", "", m.group(2))
        return [norm(m.group(1) + sub), norm(m.group(1))]
    base = re.split(r"[（(［\[0-9]", name)[0]           # 南岩国町一丁目1～23番 → 南岩国町一丁目、麻里布町(…を除く) → 麻里布町
    return [norm(base)]


def town_info(towns, cal):
    areas = cal["areas"]
    keys = [area_keys(a["n"]) for a in areas]
    whole = {}   # 地域にカレンダーが1つだけ（玖珂町全域）
    for i, a in enumerate(areas):
        if a["n"].endswith("全域"):
            whole[a["r"]] = i
    out = []
    for t in towns:
        name, region = t["name"], "岩国"
        for p, r in PREFIX.items():
            if name.startswith(p):
                name, region = name[len(p):], r
                break
        name = norm(name)
        if region in whole:
            out.append({"r": region, "c": [whole[region]]})
            continue
        best, cands = None, []
        for i, a in enumerate(areas):
            if a["r"] != region:
                continue
            sc = None
            for k in keys[i]:
                if not k:
                    continue
                if name == k:
                    s = (0, -len(k))
                elif name.startswith(k):
                    s = (1, -len(k))
                elif len(k) >= 2 and k in name:
                    s = (2, -len(k))
                else:
                    continue
                sc = s if sc is None else min(sc, s)
            if sc is None:
                continue
            if best is None or sc < best:
                best, cands = sc, [i]
            elif sc == best:
                cands.append(i)
        out.append({"r": region, "c": cands[:20]})   # 小瀬・錦町広瀬は候補が多い（地区が字・自治会ごと）
    return out


def extra(cal):
    return {}
