"""東京都 豊島区（13116）：区の「資源回収・ごみ収集曜日一覧（50音順）」（画像の PDF）を書き写した表（TABLE）から収集日データを作り、
「年末最終日・年始開始日一覧」（文字の PDF）と全行くらべる。

このファイルのきまり（どの自治体も同じ形。tools/update_year.py・download_sources.py から使う）:
  NEED                       … 元データ/<県>/<自治体>/<年度>年度/ に置くファイルの名前
  download(year, dest, web, plan) … 区のサイトから NEED のファイルを探して plan に入れる（web は tools/lib/web.py）
  make_calendar(src, year)   … src（上のフォルダ）のファイルから収集日データ（dict）を作る。読めなければ例外で止める

豊島区の収集日は、町名・丁目（一部は番地）ごとに曜日で決まる（58行）。
  びん・かん・ペットボトル 週1回・段ボール・紙・布類とプラスチック 週1回（同じ日）・燃やすごみ 週2回・
  金属・陶器・ガラスごみ 月2回（「第1・3」＝その月の1番目・3番目に来るその曜日。5番目はない）。
  雨の日も祝日も収集する。日曜日と年末年始は休み。
  ・曜日：区の冊子「資源回収・ごみ収集のお知らせ」の「回収・収集曜日一覧」（PDF。文字が画像なので読めない）を拡大して書き写した（TABLE）。
    左の表（43行。朝8時まで）と、右の「池袋駅周辺繁華街地域」の表（15行。朝7時30分まで）。
  ・年末年始：区のお知らせ「年末年始の資源回収・ごみ収集について」の「12月31日（木曜日）から1月3日（日曜日）までお休み」を読む。
    「年末最終日・年始開始日一覧」（文字の PDF。町丁目ごとに、区分ごとの12月の最後の日と1月の最初の日）を読み、
    書き写した曜日から作った日と、全行くらべる（合わなければ止まる。書き写しのまちがいもここで見つかる）。
  ・さんあ～る（区のアプリ）のカレンダーは、民間のアプリなので使わない。

フォルダ（元データ/13_東京都/13116_豊島区/<年度>年度/）に置くもの:
  回収・収集曜日一覧.pdf       … 区の「資源・ごみ パンフレット」のページ https://www.city.toshima.lg.jp/150/kurashi/gomi/shigen/013329.html の「回収・収集曜日一覧」
  年末年始.html                … 「年末年始の資源回収・ごみ収集について」（毎年10月ごろ。トピックスのページから探す）
  年末年始_最終日開始日一覧.pdf … 上のページの「資源回収・ごみ収集最終日及び開始日一覧」
"""
import datetime as dt
import html
import re
import sys
import unicodedata
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "lib"))
import kana  # noqa: E402

SITE = "https://www.city.toshima.lg.jp"
PAMPHLET = SITE + "/150/kurashi/gomi/shigen/013329.html"
TOPICS = SITE + "/151/2311271026.html"
NEED = ["回収・収集曜日一覧.pdf", "年末年始.html", "年末年始_最終日開始日一覧.pdf"]
WD = "月火水木金土日"
CATS = ["燃やす", "紙布プラ", "びん缶ペット", "金属陶器ガラス"]
TENTATIVE = ("12-31", "01-03")
DOWNTOWN = "池袋駅周辺繁華街地域"

# 回収・収集曜日一覧（令和8年4月の版。2026-04-03 に区のページに出たもの）を書き写したもの。
# 町丁名 | びん・かん・ペットボトル | 段ボール・紙布類／プラスチック | 燃やすごみ | 金属・陶器・ガラスごみ
TABLE = """
池袋1・4丁目|火|水|月・木|第1・3金
池袋2丁目14番5号・8号,15番2号〜3号,16番,17番,19番(要町通り沿い以外),20番〜38番,39番〜40番(トキワ通り沿い以外),42番,44番〜45番(トキワ通り沿い以外),46番,47番〜78番|火|水|月・木|第1・3金
池袋3丁目|火|水|月・木|第2・4金
池袋本町1〜4丁目|火|水|月・木|第1・3金
要町1丁目1番〜8番|木|金|水・土|第1・3月
要町1丁目9番〜49番|木|金|水・土|第2・4月
要町2丁目1番〜14番|木|金|水・土|第1・3月
要町2丁目15番〜36番|木|金|水・土|第2・4月
要町3丁目1番〜30番|木|金|水・土|第1・3月
要町3丁目31番〜59番|木|金|水・土|第2・4月
上池袋1〜4丁目|土|月|火・金|第2・4水
北大塚1丁目1番〜10番,15番(16号〜21号),34番(14号〜20号)|水|木|火・金|第1・3土
北大塚1丁目11番〜14番,15番(1号〜15号),16番〜33番,34番(1号〜13号)|土|月|火・金|第1・3水
北大塚2丁目|土|月|火・金|第1・3水
北大塚3丁目|土|月|火・金|第2・4水
駒込1〜7丁目|水|木|火・金|第2・4土
巣鴨1・2・5丁目|水|木|火・金|第2・4土
巣鴨3・4丁目|水|木|火・金|第1・3土
千川1・2丁目|木|金|水・土|第2・4月
雑司が谷1〜3丁目|金|土|月・木|第2・4火
高田1・2丁目|金|土|月・木|第2・4火
高田3丁目|月|火|水・土|第2・4木
高松1〜3丁目|木|金|水・土|第2・4月
千早1〜4丁目|木|金|水・土|第1・3月
長崎1〜5丁目|月|火|水・土|第1・3木
長崎6丁目|木|金|水・土|第1・3月
西池袋2・4丁目|火|水|月・木|第2・4金
西池袋3丁目1番〜19番,21番13号,33番〜36番|火|水|月・木|第2・4金
西池袋5丁目2番,3番,4番(要町通り沿い以外),5番,8番(要町通り沿い以外),9番〜28番|火|水|月・木|第2・4金
西巣鴨1〜4丁目|土|月|火・金|第1・3水
東池袋2丁目1番〜48番,49番6号付近,53番9号|金|土|月・木|第1・3火
東池袋3丁目1番,16番〜23番|金|土|月・木|第1・3火
東池袋4・5丁目|金|土|月・木|第1・3火
南池袋1丁目1番〜16番|火|水|月・木|第2・4金
南池袋2丁目1番〜21番,24番1号(シアターグリーン通り沿い),28番〜49番|金|土|月・木|第1・3火
南池袋3・4丁目|金|土|月・木|第2・4火
南大塚1・2丁目|水|木|火・金|第1・3土
南大塚3丁目1番〜24番|水|木|火・金|第1・3土
南大塚3丁目25番〜37番|金|土|月・木|第1・3火
南大塚3丁目38番〜55番|水|木|火・金|第1・3土
南長崎1〜3丁目|月|火|水・土|第2・4木
南長崎4〜6丁目|月|火|水・土|第1・3木
目白1〜5丁目|月|火|水・土|第2・4木
★池袋2丁目1番〜13番,14番(5号,8号以外),15番1号・6号,18番,19番(要町通り沿い)|水|火|月・木|第1・3金
★池袋2丁目39番〜41番,43番〜45番(すべてトキワ通り沿い)|火|水|月・木|第1・3金
★西池袋1丁目1番〜17番|火|金|水・土|第2・4木
★西池袋1丁目18番〜20番,26番〜30番,43番,44番|火|金|水・土|第1・3月
★西池袋1丁目21番〜25番,31番〜42番|火|金|水・土|第2・4月
★西池袋3丁目20番〜32番(21番13号以外)|水|火|月・木|第2・4金
★西池袋5丁目1番,4番(要町通り沿い),8番(要町通り沿い)|水|火|月・木|第2・4金
★東池袋1丁目1番〜7番|木|月|火・金|第1・3水
★東池袋1丁目8番〜11番,14番〜21番,29番〜33番|木|月|火・金|第1・3土
★東池袋1丁目12番,13番,22番〜28番|木|月|火・金|第2・4土
★東池袋1丁目34番〜50番|木|月|火・金|第2・4水
★東池袋2丁目49番〜63番(49番6号付近,53番9号は除く)|金|土|月・木|第1・3火
★東池袋3丁目2番〜15番|金|土|月・木|第2・4火
★南池袋1丁目17番〜29番|金|火|水・土|第1・3木
★南池袋2丁目22番〜27番,24番1号(シアターグリーン通り沿いは除く)|金|火|水・土|第1・3木
"""
COLS = ["びん缶ペット", "紙布プラ", "燃やす", "金属陶器ガラス"]

# 年末年始の一覧の町丁名が、曜日一覧とちがう書き方の行 → 曜日一覧の町丁名（1つの行にまとめてあるものもある）
ALIAS = {
    "北大塚1丁目1番〜10番、15番(16号〜21号)、34番(14〜20号)": ["北大塚1丁目1番〜10番,15番(16号〜21号),34番(14号〜20号)"],
    "東池袋2丁目1番〜48番,49番6号付近、53番9号、東池袋3丁目1番、16番〜23番、東池袋4・5丁目":
        ["東池袋2丁目1番〜48番,49番6号付近,53番9号", "東池袋3丁目1番,16番〜23番", "東池袋4・5丁目"],
}

# 地区の読み（pykakasi では読みちがえる町名。郵便番号一覧の読みで確かめた）
YOMI = {"上池袋": "かみいけぶくろ", "雑司が谷": "ぞうしがや"}


def nfkc(s):
    return unicodedata.normalize("NFKC", s).replace("～", "〜").replace("~", "〜").replace("　", " ").strip()


def read_table():
    out = []
    for line in TABLE.strip().splitlines():
        name, *days = line.split("|")
        down = name.startswith("★")
        out.append({"name": name.lstrip("★"), "downtown": down, **dict(zip(COLS, days))})
    return out


def parse_rule(cat, s):
    """「火」→ {(1, None)}、「月・木」→ {(0, None), (3, None)}、「第1・3金」→ {(4, 1), (4, 3)}"""
    m = re.fullmatch(r"第(\d)・(\d)([月火水木金土])", s)
    if m:
        if cat != "金属陶器ガラス":
            raise ValueError(f"{cat}の曜日の形がいつもとちがう：{s}")
        return frozenset({(WD.index(m[3]), int(m[1])), (WD.index(m[3]), int(m[2]))})
    if cat == "金属陶器ガラス" or not re.fullmatch(r"[月火水木金土](・[月火水木金土])*", s):
        raise ValueError(f"{cat}の曜日が読めない：{s}")
    return frozenset((WD.index(w), None) for w in s.split("・"))


def say(rule):
    ks = sorted(k for _, k in rule if k)
    ws = sorted({w for w, _ in rule})
    return (f"第{'・'.join(map(str, ks))}" if ks else "") + "・".join(WD[w] for w in ws)


def say_long(cat, rule):
    if cat == "金属陶器ガラス":
        return f"{say(rule)}曜日（月2回。その月の{'・'.join(str(k) for k in sorted(k for _, k in rule))}番目の{WD[min(w for w, _ in rule)]}曜日）"
    return f"毎週{say(rule)}曜日"


def hits(rule, d):
    return any(d.weekday() == w and (k is None or (d.day - 1) // 7 + 1 == k) for w, k in rule)


def read_year_end(path, year):
    """年末年始のお知らせ → (休みの最初の日, 最後の日)。その年度のお知らせでなければ None"""
    p = Path(path)
    if not p.exists():
        return None
    t = re.sub(r"\s+", "", nfkc(html.unescape(re.sub(r"<[^>]+>", "", p.read_text(encoding="utf-8")))))
    m = re.search(r"資源回収・ごみ収集は令和(\d+)年(\d+)月(\d+)日\((.)曜日\)から令和(\d+)年(\d+)月(\d+)日\((.)曜日\)までお休みします", t)
    if not m:
        raise ValueError(f"{p}：年末年始の休みが読めません（ページの書き方がかわった？ calendar.py を直す）")
    a = dt.date(int(m[1]) + 2018, int(m[2]), int(m[3]))
    b = dt.date(int(m[5]) + 2018, int(m[6]), int(m[7]))
    if a.year != year or b.year != year + 1 or WD[a.weekday()] != m[4] or WD[b.weekday()] != m[8]:
        return None
    return a.isoformat(), b.isoformat()


def key(s):
    """町丁名をくらべるための形（数字・記号・空白・★のちがいをなくす）"""
    s = nfkc(s).replace("★", "")
    return re.sub(r"[\s,、・()（）〜]", "", s)


def read_last_first(pdf):
    """年末最終日・年始開始日一覧 → [(町丁名, [12月の日×4（びん・紙布プラ・燃やす・金属）], [1月の日×4])]"""
    import pymupdf
    page = pymupdf.open(pdf)[0]
    ws = [(w[0], w[1], w[2], w[3], nfkc(w[4])) for w in page.get_text("words")]
    # 日の列：見出し「びん・かん・」の x（年末4列・年始4列）
    dates = [w for w in ws if re.fullmatch(r"\d+日\(.\)", w[4])]
    rows = {}
    for w in dates:
        rows.setdefault(round((w[1] + w[3]) / 2 / 3), []).append(w)
    out = []
    names = [w for w in ws if w[0] < 520 and w[1] > 110 and not re.fullmatch(r"[いかきこすせそたちなにひみめ]", w[4])]
    for yk, ds in sorted(rows.items()):
        if len(ds) != 8:
            raise ValueError(f"{Path(pdf).name}：日が8つない行があります（{[d[4] for d in ds]}）")
        ds.sort(key=lambda w: w[0])
        y = yk * 3
        nm = [w for w in names if abs((w[1] + w[3]) / 2 - y) < 14]
        nm.sort(key=lambda w: (round(w[1] / 6), w[0]))
        name = "".join(w[4] for w in nm)
        vals = []
        for w in ds:
            m = re.fullmatch(r"(\d+)日\((.)\)", w[4])
            vals.append((int(m[1]), m[2]))
        out.append((name, vals[:4], vals[4:]))
    return out


def area_name(r):
    return nfkc(r["name"]).replace("(", "（").replace(")", "）").replace(",", "、")


# ---------------- 区のサイトから取ってくる ----------------
def download(year, dest, web, plan):
    page = web.text(web.get(PAMPHLET))
    found = [u for u, t in web.links(page, PAMPHLET) if "回収・収集曜日一覧" in t]
    if found:
        plan.add(found[0], dest / "回収・収集曜日一覧.pdf")
    else:
        plan.problem(f"{PAMPHLET} に「回収・収集曜日一覧」の PDF がありません")
    page = web.text(web.get(TOPICS))
    found = [u for u, t in web.links(page, TOPICS) if "年末年始" in t and "収集" in t]
    if not found:
        plan.problem(f"{TOPICS} に年末年始の収集のお知らせがありません（10月ごろに出る。出るまでは 12/31〜1/3 が「未定」）")
        return
    raw = web.get(found[0])
    plan.add(found[0], dest / "年末年始.html", raw)
    pdf = [u for u, t in web.links(web.text(raw), found[0]) if "最終日" in t and "開始日" in t]
    if pdf:
        plan.add(pdf[0], dest / "年末年始_最終日開始日一覧.pdf")


# ---------------- 収集日を作る ----------------
def make_calendar(folder, year):
    folder = Path(folder)
    off = read_year_end(folder / "年末年始.html", year)
    tentative = off is None
    if tentative:
        off = (f"{year}-{TENTATIVE[0]}", f"{year + 1}-{TENTATIVE[1]}")
        print(f"  ！ {year}年度の年末年始のお知らせ（年末年始.html）がありません。{off[0]}〜{off[1]} を「未定」にして作ります")
    problems, schedules, areas, made = [], {}, [], {}
    for r in read_table():
        rules = {c: parse_rule(c, r[c]) for c in CATS}
        sname = "／".join(f"{c}:{say(rules[c])}" for c in CATS)
        if sname not in schedules:
            days = {}
            d, end = dt.date(year, 4, 1), dt.date(year + 1, 3, 31)
            while d <= end:
                k = d.isoformat()
                cs = [c for c in CATS if d.weekday() != 6 and hits(rules[c], d)]
                if off[0] <= k <= off[1]:
                    cs = []
                if cs:
                    days[k] = cs
                d += dt.timedelta(days=1)
            schedules[sname] = {"rules": {c: say_long(c, rules[c]) for c in CATS}, "days": days, "moved": {}}
        days = schedules[sname]["days"]
        # 年末の最後の日・年始の最初の日（年末年始の一覧とくらべる）
        last = [max(k for k, cs in days.items() if c in cs and k < f"{year + 1}-01-01") for c in COLS]
        first = [min(k for k, cs in days.items() if c in cs and k > f"{year}-12-31") for c in COLS]
        made[key(r["name"])] = (last, first)
        a = {"n": area_name(r), "s": sname, "y": YOMI.get(town_of(r["name"])) or kana.yomi(town_of(r["name"]))}
        if r["downtown"]:
            a["d"] = f"{DOWNTOWN}（朝7時30分までに出す）"
        areas.append(a)
    # 年末年始の一覧とくらべる
    pdf = folder / "年末年始_最終日開始日一覧.pdf"
    if not tentative and pdf.exists():
        seen = set()
        for name, last, first in read_last_first(pdf):
            kn = key(name)
            ks = [k for k in made if k == kn] or [key(x) for x in ALIAS.get(nfkc(name).lstrip("★"), [])]
            if not ks:      # 1行に2つの町丁名がまとまっている行がある（「池袋1・4丁目、2丁目14番5号…」。2つ目は町名がない）
                ks = [k1 for k1 in made for k2 in made if k1 != k2 and kn == k1 + k2[len(town_of(k2)):]]
                ks += [k2 for k1 in made for k2 in made if k1 != k2 and kn == k1 + k2[len(town_of(k2)):]]
            if not ks:
                problems.append(f"年末年始の一覧の「{name}」が、書き写した表にありません")
                continue
            for k in ks:
                seen.add(k)
                ml, mf = made[k]
                got_l = [f"{year}-12-{d:02d}" for d, _ in last]
                got_f = [f"{year + 1}-01-{d:02d}" for d, _ in first]
                if (ml, mf) != (got_l, got_f):
                    problems.append(f"{k}：年末年始の一覧 {got_l}／{got_f}、作った日 {ml}／{mf}")
                for (d, w), x in zip(last + first, got_l + got_f):
                    if WD[dt.date.fromisoformat(x).weekday()] != w:
                        problems.append(f"年末年始の一覧の曜日がおかしい：{name} {x}（{w}）")
        for k in made:
            if k not in seen:
                problems.append(f"書き写した「{k}」が、年末年始の一覧にありません")
    elif not tentative:
        problems.append(f"{pdf.name} がありません（年末年始のお知らせのページにある）")
    names = [a["n"] for a in areas]
    dup = {x for x in names if names.count(x) > 1}
    if dup:
        problems.append(f"同じ名前の地区：{dup}")
    print(f"豊島区：地区 {len(areas)}・収集日の組み合わせ {len(schedules)}・年末年始 {'未定' if tentative else '発表ずみ'}（{off[0]}〜{off[1]}）")
    if problems:
        for p in problems[:40]:
            print("  ！", p)
        raise ValueError(f"書き写した表と年末年始の一覧が合わないところが {len(problems)} あります")
    return {"year": year, "schedules": schedules, "areas": areas, "yearEnd": {"off": list(off), "tentative": tentative}}


def town_of(name):
    return re.match(r"[^\d]+?(?=\d)", nfkc(name))[0]
