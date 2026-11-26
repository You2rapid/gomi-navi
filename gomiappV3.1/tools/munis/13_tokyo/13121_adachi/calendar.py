"""東京都 足立区（13121）：区のページの「地区別の収集曜日一覧」と、日程ごとの「資源とごみの収集カレンダー」（PDF）から収集日データを作る。

このファイルのきまり（どの自治体も同じ形。tools/update_year.py・download_sources.py から使う）:
  NEED                       … 元データ/<県>/<自治体>/<年度>年度/ に置くファイルの名前
  download(year, dest, web, plan) … 区のサイトから NEED のファイルを探して plan に入れる（web は tools/lib/web.py）
  make_calendar(src, year)   … src（上のフォルダ）のファイルから収集日データ（dict）を作る。読めなければ例外で止める

足立区の収集日は、町丁目ごとに曜日で決まっている（令和8年4月から、区内全域でプラスチックの分別回収が始まり、曜日が変わった）。
  燃やすごみ 週2回・プラスチック 週1回・燃やさないごみ 月2回（第1・3か第2・4の○曜日）・資源 週1回。祝日も収集する。
  ・曜日と地区：「足立区で生活する外国人の方へ【ごみ収集スケジュール】」の「地区別の収集曜日一覧」（HTML の表。98地区）。
  ・見くらべ：「令和8年度 資源とごみの収集カレンダー」のページの、日程ごとのカレンダー PDF（12枚。上に地区の一覧、日付のマスの色が区分）。
    PDF の地区の一覧と、日付のマスの色を読んで、曜日から作った日と1日ずつくらべる（合わなければ止まる）。
  ・年末年始：カレンダーでは 12/24〜1/10 が空いていて「12月のあだち広報やホームページ等をご覧ください」。
    発表されるまでは、その期間を「未定」（yearEnd.tentative）にして、日を入れない（決まり A1。推測しない）。
    発表されたら YEAR_END に、休みと、その期間の収集日（区のお知らせのとおり）を書く。

フォルダ（元データ/13_東京都/13121_足立区/<年度>年度/）に置くもの:
  曜日一覧.html         … https://www.city.adachi.tokyo.jp/seso/kurashi/sche.html
  カレンダー.html       … https://www.city.adachi.tokyo.jp/seso/<年>calender.html（日程ごとの PDF へのリンク）
  <番号>.pdf            … カレンダーのページからリンクしている日程ごとの PDF（001.pdf〜012.pdf、002_1.pdf。002.pdf は町丁別収集曜日一覧表で画像だけ）
"""
import datetime as dt
import html as H
import re
import sys
import unicodedata
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "lib"))
import kana  # noqa: E402

SITE = "https://www.city.adachi.tokyo.jp"
LIST_PAGE = SITE + "/seso/kurashi/sche.html"
CAL_PAGE = SITE + "/seso/{year}calender.html"
NEED = ["曜日一覧.html", "カレンダー.html"]
PERENNIAL = True
CATS = ["燃やす", "プラ", "燃やさない", "資源"]      # 表の列の順
WD = "月火水木金土日"

# 年末年始。off＝収集日を入れない日（両端をふくむ）。tentative＝区がまだ発表していない（アプリでは「未定」）。
# 発表されたら、"tentative": False にして、その期間に収集する日を "days" に {日付: [区分…]}（日程ごと）で書く。
YEAR_END = {
    2026: {"off": ("2026-12-24", "2027-01-10"), "tentative": True,
           "src": "令和8年度 資源とごみの収集カレンダー（PDF）「年末(12/24～12/31)・年始(1/1～1/10)については、12月の広報やホームページ等をご覧ください」"},
}

# 地区の読み（pykakasi では読みちがえる町名。郵便番号一覧の読みで確かめた）
YOMI = {"一ツ家": "ひとつや", "保塚町": "ほづかちょう", "六町": "ろくちょう", "北加平町": "きたかへいちょう",
        "千住中居町": "せんじゅなかいちょう", "千住大川町": "せんじゅおおかわちょう", "千住宮元町": "せんじゅみやもとちょう",
        "千住旭町": "せんじゅあさひちょう", "千住東": "せんじゅあずま", "千住柳町": "せんじゅやなぎちょう",
        "千住橋戸町": "せんじゅはしどちょう", "千住河原町": "せんじゅかわらちょう", "千住緑町": "せんじゅみどりちょう",
        "千住関屋町": "せんじゅせきやちょう", "千住龍田町": "せんじゅたつたちょう", "南花畑": "みなみはなはた",
        "古千谷本町": "こぢやほんちょう", "大谷田": "おおやた", "平野": "ひらの", "弘道": "こうどう", "新田": "しんでん",
        "日ノ出町": "ひのでちょう", "本木東町": "もときひがしまち", "東六月町": "ひがしろくがつちょう", "梅島": "うめじま",
        "神明": "しんめい", "神明南": "しんめいみなみ", "西保木間": "にしほきま", "谷在家": "やざいけ", "関原": "せきばら"}


def nfkc(s):
    return unicodedata.normalize("NFKC", s).replace("～", "〜").replace("~", "〜").replace(",", "、").strip()


def clean(s):
    return re.sub(r"\s+", "", H.unescape(re.sub(r"<[^>]+>", "", s)))


def parse_rule(cat, text):
    """「月曜日・木曜日」→ {"w": [0, 3]}、「第２・４火曜日」→ {"w": [1], "n": [2, 4]}"""
    t = nfkc(text)
    m = re.fullmatch(r"第(\d)・(\d)([月火水木金土])曜日", t)
    if m:
        return {"w": [WD.index(m[3])], "n": [int(m[1]), int(m[2])]}
    ws = re.findall(r"([月火水木金土])曜日", t)
    if ws and re.fullmatch(r"([月火水木金土]曜日・?)+", t):
        return {"w": [WD.index(w) for w in ws]}
    raise ValueError(f"{cat} の曜日が読めません：「{text}」")


def say(rule):
    ws = "・".join(WD[w] for w in rule["w"])
    return f"毎月第{rule['n'][0]}・第{rule['n'][1]}{ws}曜日" if "n" in rule else f"毎週{ws}曜日"


def hits(rule, d):
    return d.weekday() in rule["w"] and ("n" not in rule or (d.day - 1) // 7 + 1 in rule["n"])


def read_list(path):
    """曜日一覧 → [(地区名, {区分: 曜日の文})]"""
    t = Path(path).read_text(encoding="utf-8")
    tb = re.search(r"<table.*?</table>", t, re.S)
    if not tb or "プラスチック" not in tb[0]:
        raise ValueError("曜日一覧の表が見つかりません（ページの形がかわった？）")
    head = [clean(x) for x in re.findall(r'<th scope="col"[^>]*>(.*?)</th>', tb[0], re.S)]
    if [h[:4] for h in head] != ["地域", "燃やすご", "プラスチ", "燃やさな", "資源【週"]:
        raise ValueError(f"曜日一覧の列がかわりました：{head}")
    out = []
    for tr in re.findall(r"<tr>(.*?)</tr>", tb[0], re.S):
        th = re.findall(r'<th scope="row"[^>]*>(.*?)</th>', tr, re.S)
        td = re.findall(r"<td[^>]*>(.*?)</td>", tr, re.S)
        if th and len(td) == 4:
            out.append((nfkc(clean(th[0])), {c: clean(x) for c, x in zip(CATS, td)}))
    if len(out) < 80:
        raise ValueError(f"曜日一覧が {len(out)} 行しか読めません")
    return out


# ---------------- カレンダー PDF ----------------
def color_cat(rgb):
    """ピクセルの色み → 区分（プラ＝紫、資源＝緑、燃やす＝ピンク、燃やさない＝青）。
    マスはぼかし（グラデーション）で塗られていて、ところによってはとてもうすいので、色みで分ける。白・黒・灰色・赤い字は None"""
    r, g, b = rgb
    if max(rgb) - min(rgb) < 6:
        return None
    if b > g + 60 and r > g + 40 and g < 150:
        return "プラ"
    if r > 230 and b > 230 and 150 <= g < 235 and r - g >= 15:
        return "燃やす"
    if g > r + 3 and g > b + 3:
        return "資源"
    if b > r + 8 and b >= g + 3:
        return "燃やさない"
    return None


def cell_cat(pm, z, x, y):
    """マス（左上 x, y、はば 22.2・高さ 15.6）のふち（まん中の数字をよける）の色みの多数決"""
    from collections import Counter
    votes = Counter()
    for dx in (1.2, 2, 3, 4, 18.2, 19.2, 20.2, 21):
        for dy in (2, 4, 6, 8, 10, 12, 14):
            c = color_cat(pm.pixel(int((x + dx) * z), int((y + dy) * z)))
            if c:
                votes[c] += 1
    top = votes.most_common(2)
    if not top or top[0][1] < 6:
        return None, votes
    if len(top) > 1 and top[1][1] >= 6:
        raise ValueError(f"マスの色が2つあります：{dict(votes)}")
    return top[0][0], votes


def pdf_days(pdf, year):
    """カレンダー PDF → (地区の一覧, {日付: [区分]})。12か月が3列×4段。月の見出し（「４月」）の左下から、7列×6行のマス"""
    import pymupdf
    page = pymupdf.open(pdf)[0]
    text = nfkc(page.get_text())
    if f"令和{year - 2018}年({year}年)4月" not in text:
        raise ValueError(f"{Path(pdf).name} は令和{year - 2018}年度のカレンダーではありません")
    areas = nfkc(page.get_text(clip=pymupdf.Rect(80, 60, 560, 140)))
    areas = [a for a in re.split(r"[/／\n]",areas.split("ごみの収集カレンダ")[-1].replace("ー", "", 1)) if a.strip()]
    z = 4
    pm = page.get_pixmap(matrix=pymupdf.Matrix(z, z))
    heads = [w for w in page.get_text("words") if re.fullmatch(r"\d{1,2}月", nfkc(w[4]))]
    if len(heads) != 12:
        raise ValueError(f"{Path(pdf).name}：月の見出しが {len(heads)} しか読めません")
    out = {}
    for w in heads:
        mo = int(nfkc(w[4])[:-1])
        first = dt.date(year if mo >= 4 else year + 1, mo, 1)
        left, top = w[0] - 2.8, w[1] + 31.3          # 日曜日の列の左はし、1行目の上はし（4月：28.2・235.3）
        col0 = (first.weekday() + 1) % 7
        d = first
        while d.month == mo:
            i = col0 + d.day - 1
            x, y = left + 22.2 * (i % 7), top + 15.6 * (i // 7)
            try:
                c, _ = cell_cat(pm, z, x, y)
            except ValueError as e:
                raise ValueError(f"{Path(pdf).name}：{d} {e}")
            if c:
                out[d.isoformat()] = [c]
            d += dt.timedelta(days=1)
    return areas, out


# ---------------- 区のサイトから取ってくる ----------------
def download(year, dest, web, plan):
    page = web.text(web.get(LIST_PAGE))
    if "プラスチック" not in page:
        plan.problem(f"{LIST_PAGE} の表にプラスチックがありません（ページがかわった？）")
    plan.add(LIST_PAGE, dest / "曜日一覧.html", page.encode("utf-8"))
    url = CAL_PAGE.format(year=year)
    cal = web.text(web.get(url))
    if f"令和{year - 2018}年度" not in nfkc(cal):
        plan.problem(f"{url} がまだ令和{year - 2018}年度のカレンダーではありません")
    plan.add(url, dest / "カレンダー.html", cal.encode("utf-8"))
    seen = set()
    for href, label in web.links(cal, url):
        if re.search(r"/documents/\d+/[\d_]+\.pdf$", href) and href not in seen:
            seen.add(href)
            plan.add(href, dest / href.rsplit("/", 1)[1])


# ---------------- 収集日を作る ----------------
def make_calendar(folder, year):
    folder = Path(folder)
    if year in YEAR_END:
        ye = YEAR_END[year]
        off, tentative = ye["off"], ye.get("tentative", False)
    else:
        off, tentative = (f"{year}-12-24", f"{year + 1}-01-10"), True
        print(f"  ！ {year}年度の年末年始がまだ calendar.py の YEAR_END にありません。12/24〜1/10 を「未定」にして作ります")
    rows = read_list(folder / "曜日一覧.html")
    problems, schedules, areas, by_area = [], {}, [], {}
    for name, vals in rows:
        rules = {c: parse_rule(c, vals[c]) for c in CATS}
        key = "／".join(f"{c}:{say(rules[c])}" for c in CATS)
        if key not in schedules:
            days = {}
            d, end = dt.date(year, 4, 1), dt.date(year + 1, 3, 31)
            while d <= end:
                k = d.isoformat()
                if not (off[0] <= k <= off[1]):
                    cs = [c for c in CATS if hits(rules[c], d)]
                    if cs:
                        days[k] = cs
                d += dt.timedelta(days=1)
            for k, cs in (YEAR_END.get(year, {}).get("days", {}).get(key, {})).items():
                days[k] = cs
            schedules[key] = {"rules": {c: say(rules[c]) for c in CATS}, "days": dict(sorted(days.items())), "moved": {}}
        town = re.match(r"\D+", name)[0]
        areas.append({"n": name, "s": key, "y": YOMI.get(town) or kana.yomi(town)})
        by_area[name] = key
    # カレンダー PDF と見くらべる
    seen, checked = {}, []
    for pdf in sorted(folder.glob("0*.pdf")):
        if pdf.name == "002.pdf":           # 町丁別収集曜日一覧表（画像だけ）
            continue
        names, got = pdf_days(pdf, year)
        keys = {by_area.get(n) for n in names}
        if None in keys or len(keys) != 1:
            problems.append(f"{pdf.name}：地区 {names} が曜日一覧の1つの日程になりません（{keys}）")
            continue
        for n in names:
            seen[n] = pdf.name
        want = schedules[keys.pop()]["days"]
        bad = [f"{k}：カレンダー {got.get(k)}／作った日 {want.get(k)}" for k in sorted(set(got) | set(want))
               if not (off[0] <= k <= off[1]) and sorted(got.get(k, [])) != sorted(want.get(k, []))]
        problems += [f"{pdf.name} " + b for b in bad]
        checked.append(pdf.name)
    missing = [n for n, _ in rows if n not in seen]
    if missing:
        problems.append(f"カレンダー PDF のどれにもない地区：{missing}")
    print(f"足立区：地区 {len(areas)}・収集日の組み合わせ {len(schedules)}・見くらべたカレンダー {len(checked)}枚（{'・'.join(checked)}）")
    if problems:
        for p in problems[:40]:
            print("  ！", p)
        raise ValueError(f"区のカレンダーと合わないところが {len(problems)} あります")
    return {"year": year, "schedules": schedules, "areas": areas,
            "yearEnd": {"off": list(off), "tentative": tentative}}
