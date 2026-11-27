"""東京都 中野区（13114）：区のページ「○○地域のごみ収集・資源回収一覧」（町名・丁目ごとの曜日の HTML の表）から収集日データを作り、
日程ごとの「資源とごみのカレンダー」PDF（25枚）のマスの文字と全日くらべる。

このファイルのきまり（どの自治体も同じ形。tools/update_year.py・download_sources.py から使う）:
  NEED                       … 元データ/<県>/<自治体>/<年度>年度/ に置くファイルの名前
  download(year, dest, web, plan) … 区のサイトから NEED のファイルを探して plan に入れる（web は tools/lib/web.py）
  make_calendar(src, year)   … src（上のフォルダ）のファイルから収集日データ（dict）を作る。読めなければ例外で止める

中野区の収集日は、町名・丁目ごとに曜日で決まる（42行）。
  燃やすごみ 週2回・陶器・ガラス・金属ごみ 月2回（第1・第3 か 第2・第4 の曜日）・資源プラスチック 週1回・
  びん・缶・ペットボトル 週1回（びん・缶・ペットボトル集積所）。祝日も収集する。日曜日と年末年始は休み。
  ・曜日：区のページの地域ごとの19ページ（新井地域・江古田地域…。どれも町名が1つ）の最初の表（丁目 → 4区分の曜日）。
    区の「中野区全域のごみと資源の収集曜日一覧」（1つの表）とも、全行同じであることを見る（ちがえば止める）。
  ・古紙（新聞・雑誌・雑がみ・段ボール）・古着・古布は、区ではなく町会・自治会の「集団回収」。曜日は番地ごとに団体で決まり、
    区のカレンダーにも入っていない（「集団回収を除く」）ので、アプリのカレンダーには入れない（city.js の説明で地域のページを案内）。
  ・カレンダー PDF：地域のページの「○○1・2丁目（2026年4月～2027年3月）」のリンク。1枚に2ページ、1ページに6か月（左右2列×3段）。
    マスの文字「燃やす」「資源プラ（プラ）」「び缶ペ」「陶ガラ金」を、曜日の列と週の行で日付に結びつけ、曜日から作った日と全日くらべる。
  ・年末年始：区のお知らせ「年末年始のごみ収集・資源回収のお知らせ（○○○○年度）」の
    「○○○○年12月31日（○曜日）から○○○○年1月3日（○曜日）までお休みです」をページから読む（曜日も合っているか確かめる）。
    その年度のお知らせがまだなければ、12/31〜1/3 を「未定」にして日を入れない。
  ・中野2・3・5丁目は「毎日収集地域は除く」（中野駅の近くなど。区のページに範囲の説明はない）。地区の説明に書く。

フォルダ（元データ/13_東京都/13114_中野区/<年度>年度/）に置くもの:
  地域/<ページ>.html    … https://www.city.tokyo-nakano.lg.jp/kurashi/gomi/syusyuyobi/<ページ>.html（19ページ。PAGES）
  全域.html             … https://www.city.tokyo-nakano.lg.jp/kurashi/gomi/syusyuyobi/nakanoku.html
  年末年始.html         … https://www.city.tokyo-nakano.lg.jp/kurashi/gomi/syusyuyobi/nenmatsu<年度>.html
  カレンダー/<名前>.pdf … 地域のページからリンクしているカレンダー（R8R9-1.pdf〜R8R9-25.pdf。名前は年度でかわる）
"""
import datetime as dt
import html
import re
import sys
import unicodedata
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "lib"))
import kana  # noqa: E402

BASE = "https://www.city.tokyo-nakano.lg.jp/kurashi/gomi/syusyuyobi/"
PAGES = ["arai", "egota", "ehara", "kamisaginomiya", "kamitakada", "saginomiya", "shirasagi", "cyuo", "nakano",
         "numabukuro", "nogata", "higashinakano", "honcyo", "matsugaoka", "maruyama", "minamidai", "yamato", "yayoi", "wakamiya"]
NEED = [f"地域/{p}.html" for p in PAGES] + ["全域.html", "年末年始.html"]
WD = "月火水木金土日"
CATS = ["燃やす", "資源プラ", "びん缶ペット", "陶ガラ金"]
# 地域のページの表の列（丁目の次から）・全域のページの表の列（町名・丁目の次から）
PAGE_COLS = ["燃やす", "陶ガラ金", "資源プラ", "びん缶ペット"]
ALL_COLS = ["資源プラ", "びん缶ペット", "燃やす", "陶ガラ金"]
# カレンダー PDF のマスの文字 → 区分（「プラ」は「資源プラ」の短い書き方。「び缶ぺ」はひらがなの「ぺ」）
LABEL = {"燃やす": "燃やす", "資源プラ": "資源プラ", "プラ": "資源プラ", "び缶ペ": "びん缶ペット", "び缶ぺ": "びん缶ペット", "陶ガラ金": "陶ガラ金"}
# マスの色の四角（fill）。文字だけで色の四角がないもの（白い字で見えない）は数えない（江古田1・3丁目の木曜の「資源プラ」など、見えない字がある）
COLOR = {"燃やす": (1.0, 0.0, 0.0), "資源プラ": (0.573, 0.816, 0.314), "びん缶ペット": (0.776, 0.349, 0.067), "陶ガラ金": (0.0, 0.439, 0.753)}
# 区の PDF の書きまちがい：マスの色（陶器・ガラス・金属ごみの青）と文字（「資源プラ」）がちがう。曜日の表と色に合わせて、文字を読みかえる
MISPRINT = {("R8R9-19.pdf", "2026-05-28"): ("資源プラ", "陶ガラ金"), ("R8R9-19.pdf", "2026-08-27"): ("資源プラ", "陶ガラ金")}
TENTATIVE = ("12-31", "01-03")   # お知らせがまだのとき「未定」にする期間
KANJI = "一二三四五六七八九"
EVERYDAY = "毎日収集地域は除く"

# 地区の読み（pykakasi では読みちがえる町名。郵便番号一覧の読みで確かめた）
YOMI = {"江古田": "えごた"}     # 中野区の江古田は「えごた」（練馬区の江古田駅は「えこだ」）


def nfkc(s):
    return unicodedata.normalize("NFKC", s).replace("～", "〜").replace("~", "〜").replace("　", " ").replace("･", "・").strip()


def cell(s):
    return re.sub(r"\s+", "", nfkc(html.unescape(re.sub(r"<[^>]+>", "", s))))


def main_part(path):
    t = Path(path).read_text(encoding="utf-8")
    m = re.search(r"<main.*?</main>", t, re.S)
    if not m:
        raise ValueError(f"{path}：ページの本文が見つかりません（ページの形がかわった？）")
    return m[0]


def rows_of(table):
    return [[cell(c) for c in re.findall(r"<t[hd][^>]*>(.*?)</t[hd]>", tr, re.S)]
            for tr in re.findall(r"<tr.*?</tr>", table, re.S)]


def chome(s):
    """「一・二・四・五丁目」→「1・2・4・5丁目」、「全域」→「」"""
    s = s.replace("(毎日収集地域は除く)", "")
    if s == "全域":
        return ""
    m = re.fullmatch(r"([一二三四五六七八九](?:・[一二三四五六七八九])*)丁目", s)
    if not m:
        raise ValueError(f"丁目の書き方が読めない：{s}")
    return "・".join(str(KANJI.index(k) + 1) for k in m[1].split("・")) + "丁目"


def read_page(path):
    """地域のページ → (町名, [{"chome", 区分…}], {「新井1・2・4・5丁目」: PDF の URL})"""
    t = main_part(path)
    h1 = cell(re.search(r"<h1[^>]*>(.*?)</h1>", t, re.S)[1])
    m = re.fullmatch(r"(.+?)地域のごみ収集・資源回収(?:曜日)?一覧", h1)
    if not m:
        raise ValueError(f"{path}：見出し「{h1}」から町名が読めません")
    town = m[1]
    table = re.search(r"<table.*?</table>", t, re.S)[0]
    rows = rows_of(table)
    head = [re.sub(r"[（(].*", "", h) for h in rows[0][1:]]
    if re.search(r"rowspan|colspan", table) or head != ["燃やすごみ", "陶器・ガラス・金属ごみ", "資源プラスチック", "びん・缶・ペットボトル"]:
        raise ValueError(f"{path} の表の形がかわりました：{rows[0]}（calendar.py を直す）")
    out = []
    for r in rows[1:]:
        if len(r) != 5:
            raise ValueError(f"{path} の行の形がおかしい：{r}")
        out.append({"chome": chome(r[0]), "everyday": EVERYDAY in r[0], **dict(zip(PAGE_COLS, r[1:]))})
    pdfs = {}
    for u, label in re.findall(r'<a[^>]+href="([^"]+\.pdf)"[^>]*>(.*?)</a>', t, re.S):
        lab = cell(label)
        m = re.fullmatch(r"(.+?)\((\d{4})年4月〜(\d{4})年3月\)\(PDF形式:[\d.,]+KB\)", lab)
        if m:
            pdfs[m[1]] = (u, int(m[2]))
    return town, out, pdfs


def read_all(path):
    """全域のページ → {(町名, 丁目): {区分: 曜日の文字, "everyday": 毎日収集地域をのぞくか}}"""
    t = main_part(path)
    out = {}
    for table in re.findall(r"<table.*?</table>", t, re.S):
        for r in rows_of(table):
            if r[0].startswith("町名"):
                if [re.sub(r"[（(].*", "", h) for h in r[2:]] != ["資源プラスチック", "びん・缶ペットボトル", "燃やすごみ", "陶器・ガラス・金属ごみ"] and \
                   [re.sub(r"[（(].*", "", h) for h in r[2:]] != ["資源プラスチック", "びん・缶・ペットボトル", "燃やすごみ", "陶器・ガラス・金属ごみ"]:
                    raise ValueError(f"{path} の表の見出しがかわりました：{r}")
                continue
            if len(r) != 6:
                raise ValueError(f"{path} の行の形がおかしい：{r}")
            out[(r[0], chome(r[1]))] = {**dict(zip(ALL_COLS, r[2:])), "everyday": EVERYDAY in r[1]}
    return out


def parse_rule(cat, s):
    """「火曜日・金曜日」→ {(1, None), (4, None)}、「第2・第4の土曜日」「第2・第4土曜日」→ {(5, 2), (5, 4)}"""
    m = re.fullmatch(r"第(\d)・第(\d)の?([月火水木金土])曜日", s)
    if m:
        if cat != "陶ガラ金":
            raise ValueError(f"{cat}の曜日の形がいつもとちがう：{s}")
        return frozenset({(WD.index(m[3]), int(m[1])), (WD.index(m[3]), int(m[2]))})
    if cat == "陶ガラ金":
        raise ValueError(f"陶器・ガラス・金属ごみの曜日の形がいつもとちがう：{s}")
    out = set()
    for part in s.split("・"):
        m = re.fullmatch(r"([月火水木金土])曜日", part)
        if not m:
            raise ValueError(f"{cat}の曜日が読めない：{s}")
        out.add((WD.index(m[1]), None))
    return frozenset(out)


def say(rule):
    """{(5,2),(5,4)} →「第2・4土」、{(1,None),(4,None)} →「火・金」"""
    ks = sorted(k for _, k in rule if k)
    ws = sorted({w for w, _ in rule})
    return (f"第{'・'.join(map(str, ks))}" if ks else "") + "・".join(WD[w] for w in ws)


def say_long(cat, rule):
    if cat == "陶ガラ金":
        return f"{say(rule)}曜日（月2回）"
    return f"毎週{say(rule)}曜日"


def hits(rule, d):
    return any(d.weekday() == w and (k is None or (d.day - 1) // 7 + 1 == k) for w, k in rule)


def read_year_end(path, year):
    """年末年始のお知らせ → {区分: (休みの最初の日, 休みの最後の日)}。その年度のお知らせでなければ None"""
    p = Path(path)
    if not p.exists():
        return None
    t = cell(main_part(p))
    pat = r"(\d{4})年(\d+)月(\d+)日\((.)曜日\)から(\d{4})年(\d+)月(\d+)日\((.)曜日\)までお休みです"
    groups = {("燃やす", "陶ガラ金", "資源プラ"): "燃やすごみ、陶器・ガラス・金属ごみ、資源プラスチック", ("びん缶ペット",): "びん・缶・ペットボトル"}
    out = {}
    for cats, head in groups.items():
        m = re.search(re.escape(head) + pat, t)
        if not m:
            raise ValueError(f"{p}：{head}の年末年始の休みが読めません（ページの書き方がかわった？ calendar.py を直す）")
        a = dt.date(int(m[1]), int(m[2]), int(m[3]))
        b = dt.date(int(m[5]), int(m[6]), int(m[7]))
        if a.year != year or b.year != year + 1 or WD[a.weekday()] != m[4] or WD[b.weekday()] != m[8]:
            return None     # ほかの年度のお知らせ
        for c in cats:
            out[c] = (a.isoformat(), b.isoformat())
    return out


def read_pdf(pdf, year):
    """カレンダー PDF → ({日付: [区分]}（その月のマスだけ）, 見出しの地区名, 読めた月の集合)"""
    import pymupdf
    out, months, title = {}, set(), None
    for page in pymupdf.open(pdf):
        ws = [(w[0], w[1], w[2], w[3], nfkc(w[4])) for w in page.get_text("words")]
        # 1つの図形に四角がいくつも入っていることがある（1月の水曜日のマスなど）ので、四角を1つずつ取り出す
        boxes = []
        for g in page.get_drawings():
            if not g.get("fill"):
                continue
            rs = [it[1] for it in g["items"] if it[0] == "re"] + [it[1].rect for it in g["items"] if it[0] == "qu"]
            boxes += [(r, g["fill"]) for r in (rs or [g["rect"]])]
        sc = page.rect.width / 841.68       # A3 の PDF と A4 の PDF がある（R8R9-20 は A4）。位置の目安をページの幅に合わせる
        # 月の見出し：「2026 年 4 月」が1行に並ぶ
        heads = []
        for i, w in enumerate(ws):
            if w[4] == "月" and i >= 3 and ws[i - 2][4] == "年" and re.fullmatch(r"20\d\d", ws[i - 3][4]) and ws[i - 1][4].isdigit():
                heads.append((int(ws[i - 3][4]), int(ws[i - 1][4]), ws[i - 3][0], w[1]))
        if heads and title is None:      # 右上の地区名（「2026年度 資源とごみのカレンダー」の右）
            t = [w for w in ws if w[1] < min(h[3] for h in heads) - 20 * sc and w[0] > page.rect.width * 0.7]
            title = "".join(w[4] for w in sorted(t, key=lambda w: (round(w[1]), w[0])))
        for y, mo, x0, y0 in heads:
            later = [h[3] for h in heads if abs(h[2] - x0) < 50 * sc and h[3] > y0]
            y1 = min(later) if later else 10 ** 6
            inside = [w for w in ws if x0 - 20 * sc <= w[0] <= x0 + 340 * sc and y0 + 5 * sc < w[1] < y1 - 5 * sc]
            cols = [w for w in inside if w[4] in "日月火水木金土" and len(w[4]) == 1 and w[1] < y0 + 30 * sc]
            if [w[4] for w in sorted(cols)] != list("日月火水木金土"):
                raise ValueError(f"{Path(pdf).name}：{y}年{mo}月の曜日の見出しが読めません")
            cx = [(c[0] + c[2]) / 2 for c in sorted(cols)]
            hy = cols[0][1]
            nums = [w for w in inside if re.fullmatch(r"\d{1,2}", w[4]) and w[1] > hy + 5 * sc]
            ys = [round(w[1]) for w in nums]
            nums = [w for w in nums if ys.count(round(w[1])) >= 2]     # マスの中にぽつんとある数字（見えない字。上高田1丁目の12月の「1」）はのぞく
            rows = sorted({round(w[1]) for w in nums})
            grid = {}
            for w in nums:
                c = min(range(7), key=lambda i: abs((w[0] + w[2]) / 2 - cx[i]))
                grid[(rows.index(round(w[1])), c)] = int(w[4])
            last = (dt.date(y + mo // 12, mo % 12 + 1, 1) - dt.timedelta(days=1)).day
            first = dt.date(y, mo, 1)
            # 確かめ：1日のマスが、その月の1日の曜日の列にある・その月の日がすべてある
            col1 = (first.weekday() + 1) % 7
            if grid.get((0, col1)) != 1 or sorted(v for (r, c), v in grid.items()
                                                  if not (r == 0 and v > 7) and not (r >= 4 and v < 15)) != list(range(1, last + 1)):
                raise ValueError(f"{Path(pdf).name}：{y}年{mo}月のマスの日付が、その月と合いません")
            if not (dt.date(year, 4, 1) <= first <= dt.date(year + 1, 3, 1)):
                raise ValueError(f"{Path(pdf).name}：{year}年度でない月 {y}年{mo}月があります")
            months.add((y, mo))
            for w in inside:
                cat = LABEL.get(w[4])
                if not cat or w[1] <= hy + 5 * sc:
                    continue
                c = min(range(7), key=lambda i: abs((w[0] + w[2]) / 2 - cx[i]))
                above = [r for r in rows if r <= round(w[1])]
                if not above:
                    continue
                r = rows.index(max(above))
                v = grid.get((r, c))
                if v is None or (r == 0 and v > 7) or (r >= 4 and v < 15):
                    continue        # 前の月・次の月のマス（その月の見出しのところで読む）
                k = dt.date(y, mo, v).isoformat()
                fix = MISPRINT.get((Path(pdf).name, k))
                if fix and cat == fix[0]:
                    cat = fix[1]
                mid = pymupdf.Point((w[0] + w[2]) / 2, (w[1] + w[3]) / 2)
                fills = [f for rr, f in boxes if rr.contains(mid) and rr.width < 80 * sc]
                if not any(max(abs(a - b) for a, b in zip(f, COLOR[cat])) < 0.02 for f in fills):
                    continue        # 色の四角がない文字（見えない字）
                out.setdefault(k, set()).add(cat)
    return {k: sorted(v, key=CATS.index) for k, v in out.items()}, title, months


def title_key(t):
    """PDF の見出し「新井1・2・4・5、上高田2丁目」→ {"新井1・2・4・5丁目", "上高田2丁目"}"""
    t = t.replace("(毎日収集地域を除く)", "")
    out = set()
    for part in t.split("、"):
        if part.endswith("全域"):
            out.add(part)
        else:
            out.add(part if part.endswith("丁目") else part + "丁目")
    return out


def area_name(town, ch):
    return f"{town}{ch}" if ch else town


# ---------------- 区のサイトから取ってくる ----------------
def download(year, dest, web, plan):
    for p in PAGES:
        raw = web.get(BASE + p + ".html")
        plan.add(BASE + p + ".html", dest / "地域" / f"{p}.html", raw)
        for u, t in web.links(web.text(raw), BASE + p + ".html"):
            if u.endswith(".pdf") and f"{year}年4月" in nfkc(t):
                plan.add(u, dest / "カレンダー" / u.rsplit("/", 1)[1])
    plan.add(BASE + "nakanoku.html", dest / "全域.html")
    news = f"{BASE}nenmatsu{year}.html"
    try:
        raw = web.get(news)
        plan.add(news, dest / "年末年始.html", raw)
    except Exception:
        plan.problem(f"{news} がまだありません（11月ごろに出る。出るまでは 12/31〜1/3 が「未定」）")


# ---------------- 収集日を作る ----------------
def make_calendar(folder, year):
    folder = Path(folder)
    table = read_year_end(folder / "年末年始.html", year)
    tentative = table is None
    if tentative:
        print(f"  ！ {year}年度の年末年始のお知らせ（年末年始.html）がありません。{TENTATIVE[0]}〜{TENTATIVE[1]} を「未定」にして作ります")
    off = (f"{year}-{TENTATIVE[0]}", f"{year + 1}-{TENTATIVE[1]}")
    all_rows = read_all(folder / "全域.html")
    problems, schedules, areas, pdf_of = [], {}, [], {}
    seen_all = set()
    for p in PAGES:
        town, rows, pdfs = read_page(folder / "地域" / f"{p}.html")
        for r in rows:
            name = area_name(town, r["chome"])
            key = name if r["chome"] else town + "全域"
            if key not in pdfs:
                problems.append(f"{p}：{name} のカレンダー PDF のリンクがありません")
                continue
            url, fy = pdfs[key]
            if fy != year:
                problems.append(f"{p}：{name} のカレンダーが {fy}年度のものです")
            pdf = url.rsplit("/", 1)[1]
            rules = {c: parse_rule(c, r[c]) for c in CATS}
            # 全域のページの表と見くらべる
            a = all_rows.get((town, r["chome"]))
            seen_all.add((town, r["chome"]))
            if a is None:
                problems.append(f"全域のページに {name} の行がありません")
            elif {c: parse_rule(c, a[c]) for c in CATS} != rules:
                problems.append(f"{name}：地域のページ {[r[c] for c in CATS]}／全域のページ {[a[c] for c in CATS]}")
            sname = "／".join(f"{c}:{say(rules[c])}" for c in CATS)
            if pdf in pdf_of and pdf_of[pdf] != sname:
                problems.append(f"{pdf} を使う地区で曜日がちがう：{pdf_of[pdf]}／{sname}（{name}）")
            pdf_of[pdf] = sname
            if sname not in schedules:
                days = {}
                d, end = dt.date(year, 4, 1), dt.date(year + 1, 3, 31)
                while d <= end:
                    k = d.isoformat()
                    cs = [c for c in CATS if d.weekday() != 6 and hits(rules[c], d)]
                    if tentative and off[0] <= k <= off[1]:
                        cs = []
                    elif not tentative:
                        cs = [c for c in cs if not (table[c][0] <= k <= table[c][1])]
                    if cs:
                        days[k] = cs
                    d += dt.timedelta(days=1)
                schedules[sname] = {"rules": {c: say_long(c, rules[c]) for c in CATS}, "days": days, "moved": {}, "pdf": pdf, "names": []}
            schedules[sname]["names"].append(key)
            ar = {"n": name, "s": sname, "y": YOMI.get(town) or kana.yomi(town)}
            if r["everyday"] or (a or {}).get("everyday"):     # 「毎日収集地域は除く」は全域のページにだけ書いてある
                ar["d"] = "毎日収集地域をのぞく（毎日収集地域は清掃事務所 03-3387-5353 へ）"
            areas.append(ar)
    for k in all_rows:
        if k not in seen_all:
            problems.append(f"全域のページの {k} が、地域のページにありません")
    # カレンダー PDF と全日くらべる
    for sname, s in schedules.items():
        pdf = folder / "カレンダー" / s.pop("pdf")
        names = s.pop("names")
        if not pdf.exists():
            problems.append(f"{pdf.name} がありません（download_sources.py で取ってくる）")
            continue
        got, title, months = read_pdf(pdf, year)
        if len(months) != 12:
            problems.append(f"{pdf.name}：読めた月が {len(months)}（12か月あるはず）")
        if not set(names) <= title_key(title):
            problems.append(f"{pdf.name} の見出し「{title}」に、地区 {names} がありません")
        ks = sorted(set(got) | set(s["days"]))
        if tentative:
            ks = [k for k in ks if not (off[0] <= k <= off[1])]
        bad = [f"{k} PDF {got.get(k, [])}／作った日 {s['days'].get(k, [])}" for k in ks if got.get(k, []) != s["days"].get(k, [])]
        if bad:
            problems.append(f"{pdf.name}（{sname}）：カレンダーと合わない日 {len(bad)}：{bad[:5]}")
    names = [a["n"] for a in areas]
    dup = {x for x in names if names.count(x) > 1}
    if dup:
        problems.append(f"同じ名前の地区：{dup}")
    print(f"中野区：地区 {len(areas)}・収集日の組み合わせ {len(schedules)}・年末年始 {'未定' if tentative else '発表ずみ'}"
          f"（{(table or {}).get('燃やす', off)}）")
    if problems:
        for p in problems[:40]:
            print("  ！", p)
        raise ValueError(f"区の表・カレンダーと合わないところが {len(problems)} あります")
    return {"year": year, "schedules": schedules, "areas": areas,
            "yearEnd": {"off": list((table or {}).get("燃やす", off)), "tentative": tentative}}
