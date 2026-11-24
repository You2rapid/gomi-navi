"""山口県 防府市（35206）：町丁 → 収集日の地区（自治会）の候補。

このファイルのきまり（tools/build_geo.py から使う）:
  town_info(towns, cal) … e-Stat の町丁（towns：名前 name・代表点 x, y・形 rings）ごとに、アプリの地区との対応を返す
                           （c：地区の候補の番号の一覧、r：地域）
  extra(cal)            … 自治体ぜんたいの追加データ（なければ {}）
地図（KML）は 元データ/35_山口県/35206_防府市/地図/r2ka35206.kml

アプリの地区は、市のカレンダーのページの表の「自治会名」（地域ごと）。
防府市の e-Stat の町丁は、多くが「大字江泊堀越」「大字富海富海中市」のように 大字＋自治会に近い名前になっている。

対応のさせ方:
  ・e-Stat の町名から「大字○○」をとった残り（例：堀越・富海中市）と、町名ぜんぶ（例：国衙一丁目・松崎町）をくらべる名前にする
  ・自治会名と「同じ」＞「自治会名で始まる」（国衙一丁目 → 国衙、台道小俣北 → 小俣）の順に近い自治会を候補にする（同じ近さなら長い名前）。
    「牟礼柳」「牟礼今宿一丁目」は、頭の牟礼（もとの大字）をとってもくらべる
    「大字○○」の残りの頭に大字の名前がもう一度つくもの（富海富海中市 → 中市、上右田右田新町 → 新町）は、それをとってもくらべる
  ・ちがう地域の同じ名前の自治会（新地・石原・中市・新町・開作・遠ヶ崎）が候補になったときは、大字から決めた地域（OAZA）のものだけにする
  ・「ケ」と「ヶ」、「ノ」と「の」はそろえてからくらべる
  ・ぴったり合わない町（例：南松崎町・寿町・天神一丁目）は候補なし。自治会の場所は市の資料にないので、推測で決めない
"""
import re

# 大字 → 地域（同じ名前の自治会がほかの地域にもあるときに、どちらか決めるためだけに使う）
OAZA = {
    "江泊": ["牟礼"], "牟礼": ["牟礼"], "東佐波令": ["松崎"], "新田": ["新田"], "野島": ["野島"], "向島": ["向島"],
    "浜方": ["新田", "中関"], "田島": ["中関"], "仁井令": ["華城", "華浦", "新田"], "植松": ["華城"], "伊佐江": ["華城"],
    "西浦": ["西浦"], "上右田": ["右田"], "下右田": ["右田"], "高井": ["右田"], "大崎": ["玉祖"], "佐野": ["玉祖"],
    "富海": ["富海"], "奥畑": ["小野"], "久兼": ["小野"], "中山": ["小野"], "和字": ["小野"], "奈美": ["小野"],
    "鈴屋": ["小野"], "真尾": ["小野"], "台道": ["大道"], "切畑": ["大道"],
}


def norm(s):
    return s.replace("ヶ", "ケ").replace("ヵ", "ケ").replace("ノ", "の")


def town_keys(name):
    """e-Stat の町名 → (くらべる名前の一覧, 大字)"""
    if not name.startswith("大字"):
        # 牟礼柳・牟礼今宿一丁目：もとの大字（牟礼）が町名の頭についている
        if name.startswith("牟礼") and len(name) > 2:
            return [norm(name[2:]), norm(name)], "牟礼"
        return [norm(name)], ""
    rest = name[2:]
    oaza = next((o for o in sorted(OAZA, key=len, reverse=True) if rest.startswith(o)), "")
    keys = []
    if oaza and rest != oaza:
        sub = rest[len(oaza):]
        keys.append(sub)
        # 富海富海中市 → 中市、上右田右田新町 → 新町（大字の名前のうしろの部分がもう一度つく）
        for head in {oaza, oaza[1:], oaza[-2:]}:
            if head and sub.startswith(head) and len(sub) > len(head):
                keys.append(sub[len(head):])
    keys.append(rest)
    return [norm(k) for k in keys], oaza


def town_info(towns, cal):
    areas = cal["areas"]
    names = [norm(a["n"]) for a in areas]
    out = []
    for t in towns:
        keys, oaza = town_keys(t["name"])
        best, cands = None, []
        for i, n in enumerate(names):
            sc = None
            for k in keys:
                if k == n:
                    s = (0, -len(n))
                elif k.startswith(n) and len(n) >= 2:
                    s = (1, -len(n))   # 同じ近さなら長い名前（開出西町 は「開出」より「開出西」）
                else:
                    continue
                sc = s if sc is None else min(sc, s)
            if sc is None:
                continue
            if best is None or sc < best:
                best, cands = sc, [i]
            elif sc == best:
                cands.append(i)
        regions = {areas[i]["r"] for i in cands}
        if len(regions) > 1 and oaza:
            cands = [i for i in cands if areas[i]["r"] in OAZA[oaza]]
        regions = sorted({areas[i]["r"] for i in cands})
        info = {"c": cands}
        if len(regions) == 1:
            info["r"] = regions[0]
        out.append(info)
    return out


def extra(cal):
    return {}
