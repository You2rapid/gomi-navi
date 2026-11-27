"""東京都 町田市（13209）：市のページ「資源とごみの収集日」（地区番号ごとのページ）から収集日データを作る。

このファイルのきまり（どの自治体も同じ形。tools/update_year.py・download_sources.py から使う）:
  NEED                       … 元データ/<県>/<自治体>/<年度>年度/ に置くファイルの名前
  download(year, dest, web, plan) … 市のサイトから NEED のファイルを探して plan に入れる（web は tools/lib/web.py）
  make_calendar(src, year)   … src（上のフォルダ）のファイルから収集日データ（dict）を作る。読めなければ例外で止める

★ 町田市のカレンダーは「10月〜翌年9月」の区切り（年度の4〜3月とちがう）。
  2026-11-27 ユーザーの決定（手順書 AGENT.md の決まり D4）：令和8年度は、市の今のカレンダー（2026年10月〜2027年9月）にある
  **2026年10月1日〜2027年3月31日だけ**を入れる。4〜9月は空（もう過ぎた。古いカレンダーの写しは使わない）。
  令和9年度にするときは、今のカレンダー（〜2027年9月）の4〜9月と、2027年秋に出る次のカレンダーの10〜3月を合わせる
  （PERIODS に、年度ごとに「どのフォルダのどの期間を使うか」を書く）。

町田市の収集日は、収集地区（1〜13）と特別指定団体（小山田桜台・公社森野住宅・シーアイハイツ・玉川学園・東玉川学園）ごとに決まる。
  ・地区ごとのページに、区分ごとの決まり（「毎週月曜日･木曜日（12月31日を除く）」「毎月2回目の土曜日」）か、
    日付の一覧（燃やせないごみ・ペットボトル・一部の剪定枝。「下記の水曜日 2026年 9月2日･16日…」）が文字で書いてある。祝日も収集する。
  ・町と地区の対応は「収集地区番号早見表」（町名 → 地区番号）。アプリの地区は、早見表の行（町・住宅）。
  ・特別指定団体の「ビン･カン」「古紙･古着」は、団体（自治会）が回収する（市のページ：「詳しくは団体の担当者に確認」）。
    市のページに日が書いてあるので入れ、rules に「団体（自治会）の回収」と書く。
  ・見くらべ：地区ごとの「資源とごみの収集カレンダー」（全体版 PDF。1か月1ページ、マスに区分の名前の文字）を全日読む。

フォルダ（元データ/13_東京都/13209_町田市/<年度>年度/）に置くもの:
  早見表.html          … https://www.city.machida.tokyo.jp/kurashi/kankyo/gomi/gominowakekata/gomi-dashikata/syuusyuu/tikunumber.html
  地区/<ページ名>.html  … 地区番号・特別指定団体ごとのページ（18）
  カレンダー/<ページ名>.pdf … そのページの「資源とごみの収集カレンダー（2026年10月～2027年9月）」（全体版）
"""
import datetime as dt
import html
import re
import sys
import unicodedata
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "lib"))
import kana  # noqa: E402

SITE = "https://www.city.machida.tokyo.jp"
BASE = SITE + "/kurashi/kankyo/gomi/gominowakekata/gomi-dashikata/syuusyuu/"
TABLE_PAGE = BASE + "tikunumber.html"
NEED = ["早見表.html"]
WD = "月火水木金土日"
# 地区のページ → 日程の名前（地区番号か団体名）
PAGES = {"1": "1", "syusyu02": "2", "syusyu03": "3", "syusyu04": "4", "syusyu05": "5", "syusyu06": "6", "syusyu07": "7",
         "syusyu08": "8", "syusyu09": "9", "syusyu10": "10", "syusyu11": "11", "syusyu12": "12", "syusyu13": "13",
         "syusyu14": "小山田桜台", "syusyu15": "公社森野住宅", "syusyu16": "シーアイハイツ",
         "0700420110913115541109": "玉川学園", "0700420110913123540887": "東玉川学園"}
# 早見表の「特別指定団体」の行 → 団体
SPECIAL = {"小山田桜台": "小山田桜台", "玉川学園:特別指定団体区域": "玉川学園", "東玉川学園:特別指定団体区域": "東玉川学園",
           "公社森野住宅": "公社森野住宅", "シーアイハイツ": "シーアイハイツ"}
# 市のページの区分の名前 → アプリの区分（1つの行に2つの区分がある団体の回収もある）
CATNAME = {"燃やせるごみ": ["燃やせる"], "容器包装プラスチック": ["プラ"], "燃やせないごみ": ["燃やせない"], "剪定枝": ["剪定枝"],
           "ビン・カン・スプレー缶": ["ビンカン"], "ビン・カン": ["ビンカン"], "古紙・古着": ["古紙"], "ペットボトル": ["ペット"],
           "有害ごみ(電池・充電式小型家電)": ["電池"], "有害ごみ(スプレー缶・電池・充電式小型家電)": ["電池"],
           "有害ごみ(蛍光管・水銀体温計・ライター)": ["蛍光管"], "ビン・カン、古紙・古着": ["ビンカン", "古紙"]}
CATS = ["燃やせる", "プラ", "燃やせない", "古紙", "ビンカン", "ペット", "剪定枝", "電池", "蛍光管"]
# 年度ごとに入れる期間（市のカレンダーの区切りが 10月〜翌9月のため）
PERIODS = {2026: ("2026-10-01", "2027-03-31")}
# 全体版カレンダーのマスの文字 → 区分
LABEL = [("燃やせるごみ", "燃やせる"), ("燃やせないごみ", "燃やせない"), ("容器包装", "プラ"),     # 特別指定団体のカレンダーは「容器包装」「プラスチック」の2行
         ("古紙", "古紙"),
         ("ビン・カン", "ビンカン"), ("ペットボトル", "ペット"), ("剪定枝", "剪定枝"), ("乾電池", "電池"), ("蛍光管", "蛍光管")]

# 地区の読み（pykakasi では読みちがえる町名。郵便番号一覧の読みで確かめて足す）
YOMI = {
    "上小山田町": "かみおやまだまち", "下小山田町": "しもおやまだまち", "南大谷": "みなみおおや", "小山ヶ丘": "おやまがおか", "小野路町": "おのじまち",
    "広袴町": "ひろばかままち", "本町田": "ほんまちだ", "根岸町": "ねぎしまち", "相原町": "あいはらまち", "真光寺町": "しんこうじまち",
    "薬師台": "やくしだい", "西成瀬": "にしなるせ", "金井ヶ丘": "かないがおか", "高ヶ坂": "こがさか",
    "本町田住宅": "ほんまちだじゅうたく",       # 郵便番号一覧にない住宅の名前は、町名の読みに合わせた
}


def nfkc(s):
    return unicodedata.normalize("NFKC", s).replace("～", "〜").replace("~", "〜").replace("･", "・").strip()


def text(s):
    return nfkc(html.unescape(re.sub(r"<[^>]+>", "", s))).replace(" ", "").replace("　", "")


def year_of(fy, mo):
    return fy if mo >= 4 else fy + 1


def read_page(path):
    """地区のページ → [(区分の名前, 決まりの行のリスト, 団体の回収か)]"""
    t = Path(path).read_text(encoding="utf-8")
    i = t.find("資源とごみの収集日</h")
    if i < 0:
        raise ValueError(f"{path}：「資源とごみの収集日」の見出しがありません（ページの形がかわった？）")
    seg = t[i:t.find("adobereader", i)]
    out, group = [], False
    for m in re.finditer(r"<li>(.*?)</li>|<p[^>]*>(.*?)</p>", seg, re.S):
        if m[2] is not None:
            if "団体" in text(m[2]):
                group = True          # この下は、団体（自治会）が回収する資源
            continue
        lines = [text(x) for x in re.split(r"<br\s*/?>", m[1])]
        lines = [x for x in lines if x]
        out.append((lines[0], lines[1:], group))
    if len(out) < 8:
        raise ValueError(f"{path}：区分が {len(out)} しか読めません")
    return out


def parse_rule(lines, fy, where):
    """決まりの行 → その年度の日付の集合（4月〜3月）。読めなければ例外"""
    s = "".join(lines)
    days = set()
    start, end = dt.date(fy, 4, 1), dt.date(fy + 1, 3, 31)
    m = re.fullmatch(r"下記の([月火水木金土])曜日(.*)", s)
    if m:
        wd, y = WD.index(m[1]), None
        for part in lines[1:]:
            ym = re.fullmatch(r"(\d{4})年", part)
            if ym:
                y = int(ym[1])
                continue
            mm = re.fullmatch(r"(\d+)月((?:\d+日・?)+)", part)
            if not mm or y is None:
                raise ValueError(f"{where}：日付の行が読めない「{part}」")
            for dd in re.findall(r"(\d+)日", mm[2]):
                d = dt.date(y, int(mm[1]), int(dd))
                if d.weekday() != wd:
                    raise ValueError(f"{where}：{d} は{m[1]}曜日ではありません")
                if start <= d <= end:
                    days.add(d)
        return days
    ex = {(int(a), int(b)) for a, b in re.findall(r"(\d+)月(\d+)日を除く", s)}
    s2 = re.sub(r"[（(](?:\d+月\d+日を除く、?)+[）)]", "", s)
    m1 = re.fullmatch(r"毎週((?:[月火水木金土]曜日・?)+)", s2)
    m2 = re.fullmatch(r"毎月(\d)回目(?:と(\d)回目)?の([月火水木金土])曜日", s2)
    # シーアイハイツの団体回収：「2026年10,11月と2027年4,7,8,9月は、1回目と3回目の火曜日2026年12月と2027年1,2,3,5,6月は、2回目と4回目の火曜日」
    m3 = re.findall(r"(\d{4})年([\d,]+)月(?:と(\d{4})年([\d,]+)月)?は、(\d)回目と(\d)回目の([月火水木金土])曜日", s2)
    d = start
    while d <= end:
        nth = (d.day - 1) // 7 + 1
        hit = False
        if m1:
            hit = WD[d.weekday()] in re.findall(r"([月火水木金土])曜日", m1[1])
        elif m2:
            hit = WD[d.weekday()] == m2[3] and nth in {int(m2[1]), int(m2[2] or m2[1])}
        elif m3:
            for y1, ms1, y2, ms2, a, b, w in m3:
                months = {(int(y1), int(x)) for x in ms1.split(",")} | ({(int(y2), int(x)) for x in ms2.split(",")} if y2 else set())
                if (d.year, d.month) in months and WD[d.weekday()] == w and nth in {int(a), int(b)}:
                    hit = True
        else:
            raise ValueError(f"{where}：決まりが読めない「{s}」")
        if hit and (d.month, d.day) not in ex:
            days.add(d)
        d += dt.timedelta(days=1)
    for mo, dd in ex:      # 「除く」と書いた日が、ほんとうに決まりの日か
        x = dt.date(year_of(fy, mo), mo, dd)
        if m1 and WD[x.weekday()] not in m1[1] or m2 and not (WD[x.weekday()] == m2[3] and (x.day - 1) // 7 + 1 in {int(m2[1]), int(m2[2] or m2[1])}):
            raise ValueError(f"{where}：「{mo}月{dd}日を除く」が決まりの日ではありません（{s}）")
    return days


def say(name, lines, group):
    s = lines[0] if lines[0].startswith("下記の") else "".join(lines)
    if s.startswith("下記の"):
        s = s.replace("下記の", "") + "（日はカレンダーのとおり。月2回）"
    s = s.replace("回目", "番目").replace("(", "（").replace(")", "）")
    return s + ("（団体（自治会）の回収。くわしくは自治会へ）" if group else "")


def read_table(path):
    """早見表 → [(町名, 日程の名前)]"""
    t = Path(path).read_text(encoding="utf-8")
    out = []
    for tr in re.findall(r"<tr.*?</tr>", re.findall(r"<table.*?</table>", t, re.S)[0], re.S):
        cells = [text(c) for c in re.findall(r"<t[hd][^>]*>(.*?)</t[hd]>", tr, re.S)]
        if len(cells) == 3 and re.fullmatch(r".行|", cells[0]):
            cells = cells[1:]
        if len(cells) != 2 or cells[0] == "町名" or cells[0].startswith("《参考》"):
            continue
        town, no = cells
        if no == "特別指定団体":
            key = next((v for k, v in SPECIAL.items() if re.sub(r"^\(|\)$", "", town).startswith(k) or f"){k}" in town), None)
            if not key:
                raise ValueError(f"早見表の特別指定団体「{town}」がどの団体かわかりません（SPECIAL に足す）")
        else:
            mm = re.fullmatch(r"(\d+)番", no)
            if not mm:
                raise ValueError(f"早見表の地区番号が読めない：{cells}")
            key = mm[1]
        out.append((town, key))
    if len(out) < 60:
        raise ValueError(f"早見表が {len(out)} 行しか読めません")
    return out


def area_name(town):
    """「(木曽東)町田木曽住宅」→「町田木曽住宅（木曽東）」、「(玉川学園:特別指定団体区域)」→「玉川学園（特別指定団体の区域）」"""
    m = re.fullmatch(r"\((.+?)\)(.+)", town)
    if m:
        return f"{m[2]}（{m[1]}）"
    m = re.fullmatch(r"\((.+?):特別指定団体区域\)", town)
    if m:
        return f"{m[1]}（特別指定団体の区域）"
    return town.replace("(", "（").replace(")", "）")


def town_yomi_key(name):
    t = re.sub(r"（.*$", "", name)
    t = re.sub(r"[\d〜、]+丁目$", "", t)
    return re.split(r"[・、]", t)[0]


def read_pdf(pdf, period):
    """全体版カレンダー（1か月1ページ）→ {日付: [区分]}（period の期間だけ）"""
    import pymupdf
    out, months = {}, set()
    for page in pymupdf.open(pdf):
        ws = page.get_text("words")
        if page.rotation:       # 玉川学園のカレンダーはページが回転している：文字の位置を、見たときの向きに直す
            ws = [tuple(pymupdf.Rect(w[:4]) * page.rotation_matrix) + tuple(w[4:]) for w in ws]
        if not any(w[4] == "月MON" for w in ws):
            continue
        big = [w for w in ws if w[0] < 80 and w[1] < 120 and w[3] - w[1] > 25 and re.match(r"\d+(月)?$", nfkc(w[4]))]     # 左上の大きな月（「10月」「1」）
        nums = [w for w in ws if w[3] - w[1] > 15 and re.fullmatch(r"\d{1,2}", w[4]) and w[0] < 720 and w[1] > 55 and w not in big]
        if page.number < 3 or page.number > 14 or len(nums) < 28:
            continue        # 表紙・説明のページ（カレンダーは 4〜15ページ目の 10月〜9月）
        if len(big) == 1:
            mo = int(re.match(r"\d+", nfkc(big[0][4]))[0])
        else:
            mo = (page.number - 3 + 9) % 12 + 1     # 月の見出しの字が読めない PDF（玉川学園）：ページの順番で決め、下で確かめる
        y = 2026 if mo >= 10 else 2027        # このカレンダーは 2026年10月〜2027年9月
        if not (period[0] <= f"{y}-{mo:02d}-01" <= period[1]):
            continue
        # 確かめ：1日の数字の列（曜日）と、いちばん大きい日がその月と合うか
        first = min(nums, key=lambda w: int(w[4]))       # 1日が日曜日で、月の見出しの下にかくれるページもある
        last = (dt.date(y + mo // 12, mo % 12 + 1, 1) - dt.timedelta(days=1)).day
        col = round((first[0] - 42) / 108.6)        # 0＝日曜の列 … 6＝土曜の列
        if int(first[4]) > 2 or col != (dt.date(y, mo, int(first[4])).weekday() + 1) % 7 or max(int(w[4]) for w in nums) != last:
            raise ValueError(f"{Path(pdf).name} {page.number + 1}ページ：{y}年{mo}月のカレンダーと合いません（ページの順番がかわった？）")
        months.add((y, mo))
        for w in ws:
            lab = nfkc(w[4])
            cats = [c for k, c in LABEL if k in lab]
            if not cats or w[0] > 760 or w[1] < 60:        # 右の帯（x 765〜）の文字はのぞく。土曜のマスの文字は x 720 をこえることがある
                continue
            cx, cy = (w[0] + w[2]) / 2, w[1]
            # マスの左上に日の数字がある。ラベルの中心より左で、いちばん近い数字のマス（ラベルは右どなりの数字の左はしより右まで出ることがある）
            cand = [n for n in nums if n[0] <= cx + 10 and cx - n[0] < 110 and 0 < cy - n[1] < 85]
            if not cand:
                continue
            n = min(cand, key=lambda n: (cx - n[0], cy - n[1]))      # 横にいちばん近い数字（「24/31」のように1つのマスに2つの数字があるときも）
            k = dt.date(y, mo, int(n[4])).isoformat()
            out.setdefault(k, set()).update(cats)
    return {k: sorted(v, key=CATS.index) for k, v in out.items()}, months


# ---------------- 市のサイトから取ってくる ----------------
def download(year, dest, web, plan):
    plan.add(TABLE_PAGE, dest / "早見表.html")
    for p in PAGES:
        raw = web.get(BASE + p + ".html")
        plan.add(BASE + p + ".html", dest / "地区" / f"{p}.html", raw)
        pdf = [u for u, t in web.links(web.text(raw), BASE + p + ".html") if u.endswith(".pdf") and "簡略" not in t]
        if pdf:
            plan.add(pdf[0], dest / "カレンダー" / f"{p}.pdf")
        else:
            plan.problem(f"{p}.html に収集カレンダー（全体版）の PDF がありません")


# ---------------- 収集日を作る ----------------
def make_calendar(folder, year):
    folder = Path(folder)
    if year not in PERIODS:
        raise ValueError(f"{year}年度に入れる期間が PERIODS にありません（町田市のカレンダーは10月〜翌9月。calendar.py の説明を読む）")
    period = PERIODS[year]
    problems, schedules = [], {}
    for page, key in PAGES.items():
        days, rules = {}, {}
        for name, lines, group in read_page(folder / "地区" / f"{page}.html"):
            cats = CATNAME.get(name)
            if not cats:
                problems.append(f"{page}：区分「{name}」がわかりません（CATNAME に足す）")
                continue
            ds = parse_rule(lines, year, f"{page} {name}")
            for c in cats:
                if c in rules and rules[c] != say(name, lines, group):
                    problems.append(f"{page}：{c} が2回あり、決まりがちがう")
                if c in rules:
                    continue        # 市のページに同じ区分が2回（12番地区の容器包装プラスチック）。決まりは同じ
                rules[c] = say(name, lines, group)
                for d in ds:
                    k = d.isoformat()
                    if period[0] <= k <= period[1]:
                        days.setdefault(k, []).append(c)
        days = {k: sorted(v, key=CATS.index) for k, v in sorted(days.items())}
        schedules[key] = {"rules": {c: rules[c] for c in CATS if c in rules}, "days": days, "moved": {}}
        # 全体版カレンダーと見くらべる
        pdf = folder / "カレンダー" / f"{page}.pdf"
        if not pdf.exists():
            problems.append(f"{pdf.name} がありません（download_sources.py で取る）")
            continue
        got, months = read_pdf(pdf, period)
        if len(months) != 6:
            problems.append(f"{pdf.name}：10〜3月のページが {len(months)} か月しかありません")
        for k in sorted(set(got) | set(days)):
            if got.get(k, []) != days.get(k, []):
                problems.append(f"{key} {k}：カレンダー {got.get(k)}／作った日 {days.get(k)}")
    areas = []
    for town, key in read_table(folder / "早見表.html"):
        n = area_name(town)
        y = town_yomi_key(n)
        areas.append({"n": n, "s": key, "y": YOMI.get(y) or kana.yomi(y),
                      "d": f"{key}番地区" if key.isdigit() else f"特別指定団体（{key}）"})
    used = {a["s"] for a in areas}
    if used != set(schedules):
        problems.append(f"早見表と地区のページが合いません：{sorted(used ^ set(schedules))}")
    names = [a["n"] for a in areas]
    dup = {x for x in names if names.count(x) > 1}
    if dup:
        problems.append(f"同じ名前の地区：{dup}")
    hol = [k for s in schedules.values() for k in s["days"] if f"{year}-12-31" <= k <= f"{year + 1}-01-03"]
    print(f"町田市：地区 {len(areas)}・日程 {len(schedules)}・入れた期間 {period[0]}〜{period[1]}・12/31〜1/3 の収集日 {len(hol)}")
    if problems:
        for p in problems[:40]:
            print("  ！", p)
        raise ValueError(f"市のページ・カレンダーと合わないところが {len(problems)} あります")
    out = {"year": year, "schedules": schedules, "areas": areas}
    if not hol:
        out["yearEnd"] = {"off": [f"{year}-12-31", f"{year + 1}-01-03"], "tentative": False}
    return out
