"""東京都 目黒区（13110）：区の「地域別資源・ごみ収集日カレンダー」（地域ごとの年度カレンダー PDF 47枚）から収集日データを作る。

このファイルのきまり（どの自治体も同じ形。tools/update_year.py・download_sources.py から使う）:
  NEED                       … 元データ/<県>/<自治体>/<年度>年度/ に置くファイルの名前
  download(year, dest, web, plan) … 区のサイトから NEED のファイルを探して plan に入れる（web は tools/lib/web.py）
  make_calendar(src, year)   … src（上のフォルダ）のファイルから収集日データ（dict）を作る。読めなければ例外で止める

目黒区の収集日は、町名・丁目ごとに曜日で決まる（47の地域）。
  燃やすごみ 週2回・資源（プラスチック・ペットボトル・びん・缶）週1回・燃やさないごみ 月2回（第1・第3 か 第2・第4 の曜日）。
  水銀を含む製品は、燃やさないごみの2回のうち、決まった1回（一覧表の○の週）。月〜土に収集し、祝日も収集する。
  古紙は町会などの集団回収（曜日は団体ごと）なので、カレンダーに入れない。
  ・収集日：地域ごとの年度カレンダー PDF（2ページ・1ページに6か月。マスに区分の名前の文字「資源」「可燃」「不燃」「不燃・水銀」）を
    全日読む（read_pdf）。日付は、文字のすぐ上にある日の数字（同じ列）で決める。
  ・曜日一覧表（収集曜日一覧表 PDF）と、読んだ日がすべて曜日どおりかをくらべる（地域の名前・曜日・水銀の週）。
  ・年末年始：カレンダーの 12/27〜12/31 は空白（「別途区公式ウェブサイトや12月1日号の区報等でご案内」）。
    区のお知らせ「年末年始の資源回収・ごみ収集」の「令和○年12月31日（○曜日）から令和○年1月3日（○曜日）までの期間は…お休み」を読み、
    その前の日（12/28〜12/30）は曜日どおりに入れる。地域別の「収集終了日・開始日」PDF と全地域くらべる。
    お知らせがその年度のものでなければ、カレンダーの空白の 12/27〜1/3 を「未定」にする。

フォルダ（元データ/13_東京都/13110_目黒区/<年度>年度/）に置くもの:
  収集日.html        … https://www.city.meguro.tokyo.jp/seisou/kurashi/gomi/youbiichiran.html
  収集曜日一覧表.pdf … 上のページの「収集曜日一覧表」
  カレンダー/*.pdf    … 上のページの「地域別資源・ごみ収集日カレンダー」47枚
  年末年始.html      … https://www.city.meguro.tokyo.jp/seisou/kurashi/gomi/nenmatsu_nenshi.html
  年末年始_地域別.pdf … 上のページの「地域別収集終了日・開始日」
"""
import datetime as dt
import html
import re
import sys
import unicodedata
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "lib"))
import kana  # noqa: E402

SITE = "https://www.city.meguro.tokyo.jp"
DAYS_PAGE = SITE + "/seisou/kurashi/gomi/youbiichiran.html"
YE_PAGE = SITE + "/seisou/kurashi/gomi/nenmatsu_nenshi.html"
NEED = ["収集日.html", "収集曜日一覧表.pdf", "年末年始.html", "年末年始_地域別.pdf"]
WD = "月火水木金土日"
CATS = ["可燃", "資源", "不燃", "水銀"]
LABEL = {"可燃": ["可燃"], "資源": ["資源"], "不燃": ["不燃"], "不燃・水銀": ["不燃", "水銀"], "お休み": []}
BLANK = ("12-27", "01-03")     # カレンダーで空白・お休みの期間（年末年始はお知らせで決める）

# 地区の読み（pykakasi では読みちがえる町名。郵便番号一覧の読みで確かめた）
YOMI = {"柿の木坂": "かきのきざか", "五本木": "ごほんぎ", "洗足": "せんぞく", "中町": "なかちょう"}


def nfkc(s):
    return unicodedata.normalize("NFKC", s).replace("～", "〜").replace("~", "〜").replace("　", " ").strip()


def cell(s):
    return re.sub(r"\s+", "", nfkc(html.unescape(re.sub(r"<[^>]+>", "", s))))


# ---------------- 区のサイトから取ってくる ----------------
def download(year, dest, web, plan):
    raw = web.get(DAYS_PAGE)
    plan.add(DAYS_PAGE, dest / "収集日.html", raw)
    page = web.text(raw)
    n = 0
    for u, t in web.links(page, DAYS_PAGE):
        if not u.endswith(".pdf"):
            continue
        if "収集曜日一覧表" in t:
            plan.add(u, dest / "収集曜日一覧表.pdf")
        elif "収集日カレンダー" in t:
            if f"{year}年4月から{year + 1}年3月まで" not in t:
                plan.problem(f"{DAYS_PAGE} のカレンダーが {year}年度のものではありません：{t}")
                return
            plan.add(u, dest / "カレンダー" / u.rsplit("/", 1)[-1])
            n += 1
    if n == 0:
        plan.problem(f"{DAYS_PAGE} に地域別カレンダーが見つかりません")
    raw = web.get(YE_PAGE)
    plan.add(YE_PAGE, dest / "年末年始.html", raw)
    for u, t in web.links(web.text(raw), YE_PAGE):
        if u.endswith(".pdf") and "地域別収集終了日" in t:
            plan.add(u, dest / "年末年始_地域別.pdf")


# ---------------- 地域の名前 ----------------
def area_key(s):
    """「青葉台１丁目から３丁目」「青葉台１～３丁目」「青葉台1～3」→ ("青葉台", (1, 2, 3))（3つの資料の書き方をそろえてくらべる）"""
    s = nfkc(s).replace("から", "〜").replace("丁目", "")
    m = re.fullmatch(r"(\D+?)([\d・〜]+)", s)
    if not m:
        raise ValueError(f"地域の名前が読めない：{s}")
    nums = set()
    for part in m[2].split("・"):
        a, _, b = part.partition("〜")
        nums.update(range(int(a), int(b or a) + 1))
    return m[1], tuple(sorted(nums))


def area_name(key):
    """("青葉台", (1, 2, 3)) →「青葉台1〜3丁目」、(1, 2) →「1・2丁目」（区のカレンダーの書き方）"""
    town, ns = key
    if len(ns) == 1:
        return f"{town}{ns[0]}丁目"
    if len(ns) == 2:
        return f"{town}{ns[0]}・{ns[1]}丁目"
    return f"{town}{ns[0]}〜{ns[-1]}丁目"


# ---------------- 収集曜日一覧表 ----------------
def read_table(pdf):
    """収集曜日一覧表 PDF → {地域: {"資源": {曜日}, "可燃": {曜日}, "不燃": {週}, "不燃曜": 曜日, "水銀": 週}}"""
    import pymupdf
    out = {}
    circled = "①②③④"
    for page in pymupdf.open(pdf):
        lines = {}
        for w in page.get_text("words"):
            lines.setdefault(round(w[1]), []).append(w)
        for y, ws in sorted(lines.items()):
            ws.sort(key=lambda w: w[0])

            def col(x0, x1):     # 左はしの五十音の見出し（「セ」など1文字）は入れない
                return "".join(w[4] for w in ws if x0 <= w[0] < x1 and len(w[4]) > 1)
            name, res, burn, nb = col(0, 290), col(290, 355), col(355, 460), col(460, 700).replace(" ", "")
            if "丁目" not in name:
                continue
            m = re.fullmatch(r"第([1-4①②③④])・第([1-4①②③④])([月火水木金土])曜日", nb)
            if not (m and re.fullmatch(r"[月火水木金土]曜日", res) and re.fullmatch(r"[月火水木金土]曜日・[月火水木金土]曜日", burn)):
                raise ValueError(f"{Path(pdf).name}：行が読めない：{name}／{res}／{burn}／{nb}")
            weeks = [(circled.index(k) + 1, True) if k in circled else (int(k), False) for k in (m[1], m[2])]
            hg = [k for k, c in weeks if c]
            if len(hg) != 1:
                raise ValueError(f"{name}：水銀の週（○）が1つではありません：{nb}")
            out[area_key(name)] = {"資源": {WD.index(res[0])}, "可燃": {WD.index(burn[0]), WD.index(burn[4])},
                                   "不燃": {k for k, _ in weeks}, "不燃曜": WD.index(m[3]), "水銀": hg[0]}
    return out


def rule_days(r, d):
    """曜日一覧表の決まりで、その日に出す区分"""
    if d.weekday() == 6:
        return []
    k = (d.day - 1) // 7 + 1
    cs = [c for c in ("可燃", "資源") if d.weekday() in r[c]]
    if d.weekday() == r["不燃曜"] and k in r["不燃"]:
        cs.append("不燃")
        if k == r["水銀"]:
            cs.append("水銀")
    return sorted(cs, key=CATS.index)


# ---------------- 地域別カレンダー PDF ----------------
def read_pdf(pdf, year):
    """地域のカレンダー PDF → (地域の名前, {日付: [区分]}, 「お休み」の日の集合)。
    1ページに6か月（3×2）。マスの右上に日の数字、その下に区分の文字。日付は数字の位置（行・列）と文字で決める。"""
    import pymupdf
    days, rest, months, names = {}, set(), set(), set()
    for page in pymupdf.open(pdf):
        words = page.get_text("words")
        m = re.search(r"対象地域\s*\n(?:.*\n){0,6}?\s*(\S+丁目)", page.get_text())
        if m:
            names.add(nfkc(m[1]))
        heads = [w for w in words if w[4] == "日曜月曜"]
        for h in heads:
            sat = min((w for w in words if w[4] == "土曜" and abs(w[1] - h[1]) < 3 and w[0] > h[0]), key=lambda w: w[0])
            tue = next(w for w in words if w[4] == "火曜" and abs(w[1] - h[1]) < 3 and h[0] < w[0] < sat[0])
            x0, x1 = h[0] - 2, sat[2] + 2
            cw = ((sat[0] + sat[2]) / 2 - (tue[0] + tue[2]) / 2) / 4
            col0 = (tue[0] + tue[2]) / 2 - 2 * cw                    # 日曜の列の中心
            mon = [w for w in words if w[4] == "月" and x0 < w[0] < x1 and h[1] - 40 < w[1] < h[1]]
            if len(mon) != 1:
                raise ValueError(f"{Path(pdf).name}：月の見出しが読めない（{mon}）")
            num = [w for w in words if re.fullmatch(r"\d{1,2}", w[4]) and x0 < w[0] < mon[0][0] and abs(w[3] - mon[0][3]) < 4]
            yr = [w for w in words if re.fullmatch(r"\d{4}年", w[4]) and x0 - 5 < w[0] < x1 and abs(w[3] - mon[0][3]) < 8]
            if not num or len(yr) != 1:
                raise ValueError(f"{Path(pdf).name}：月の見出しが読めない（{num} {yr}）")
            y, mo = int(yr[0][4][:4]), int(max(num, key=lambda w: w[0])[4])
            months.add((y, mo))
            below = [g for g in heads if abs(g[0] - h[0]) < 5 and g[1] > h[1] + 5]
            # 下の段の月の見出し（「2026年 7 月」）の上まで
            ybot = min((w[1] for g in below for w in words if w[4] == "月" and g[1] - 45 < w[1] < g[1] and x0 < w[0] < x1),
                       default=page.rect.y1) - 1
            first = dt.date(y, mo, 1)
            start = first - dt.timedelta(days=(first.weekday() + 1) % 7)   # 表の左上（日曜）の日
            heads_mon = [w for w in words if w[4] == "月"]
            nums = [w for w in words if re.fullmatch(r"\d{1,2}", w[4]) and x0 < w[0] < x1 and h[3] < w[1] < ybot
                    and not any(abs(w[3] - m[3]) < 5 and 0 < m[0] - w[2] < 30 for m in heads_mon)]   # 月の見出しの数字はのぞく

            def colof(x):
                return round((x - col0) / cw)
            ys = sorted({round(w[1]) for w in nums if colof((w[0] + w[2]) / 2) != 0})
            rows = [ys[0]]
            for v in ys:
                if v - rows[-1] > 5:
                    rows.append(v)
            rh = (rows[-1] - rows[0]) / (len(rows) - 1)
            cells = []     # (数字の word, 日付, 列)
            for w in nums:
                c = colof((w[0] + w[2]) / 2)
                r = int((w[1] - rows[0]) / rh + 0.3)
                for rr in (r, r + 1):
                    d = start + dt.timedelta(days=7 * rr + c)
                    if d.day == int(w[4]):
                        cells.append((w, d, c))
                        break
                else:
                    raise ValueError(f"{Path(pdf).name} {y}/{mo}：数字 {w[4]} の位置が日付と合わない")
            # 区分の文字（となりのマスの文字とくっつかないよう、文字の位置で探す）
            hits = []
            for lab in ("不燃・水銀", "お休み", "資源", "可燃", "不燃"):
                for r in page.search_for(lab, clip=pymupdf.Rect(x0, h[3], x1, ybot)):
                    if lab == "不燃" and any(r.intersects(q) for q, l in hits if l == "不燃・水銀"):
                        continue
                    hits.append((r, lab))
            for r, lab in hits:
                c = colof((r.x0 + r.x1) / 2)
                above = [(w, d) for w, d, cc in cells if cc == c and w[3] <= r.y0 + 2 and r.y0 - w[3] < rh]
                if not above:
                    raise ValueError(f"{Path(pdf).name} {y}/{mo}：「{lab}」の上に日の数字がない（{r}）")
                w, d = max(above, key=lambda a: a[0][3])
                if d.month != mo:
                    raise ValueError(f"{Path(pdf).name}：{d} はほかの月のマスなのに「{lab}」がある")
                if lab == "お休み":
                    rest.add(d.isoformat())
                else:
                    days.setdefault(d.isoformat(), []).extend(LABEL[lab])
    want = {(year + (m < 4), m) for m in range(1, 13)}
    if months != want or len(names) != 1:
        raise ValueError(f"{Path(pdf).name}：{year}年度の12か月がそろっていない（{sorted(months)}）か、対象地域が読めない（{names}）")
    out = {}
    for k, v in sorted(days.items()):
        if len(v) != len(set(v)) or ("水銀" in v and "不燃" not in v):
            raise ValueError(f"{Path(pdf).name} {k}：区分がおかしい {v}")
        out[k] = sorted(v, key=CATS.index)
    return names.pop(), out, rest


# ---------------- 年末年始 ----------------
def read_year_end(path, year):
    """お知らせのページ →（休みのはじめ, 休みのおわり）。その年度のお知らせでなければ None"""
    p = Path(path)
    if not p.exists():
        return None
    t = cell(re.search(r"<main.*?</main>", p.read_text(encoding="utf-8"), re.S)[0])
    m = re.search(r"令和(\d+)年12月(\d+)日\((.)曜日\)から令和(\d+)年1月(\d+)日\((.)曜日\)までの期間は、全ての資源回収・ごみ収集をお休み", t)
    if not m:
        raise ValueError(f"{p}：年末年始の休みの文が読めません（ページの書き方がかわった？ calendar.py を直す）")
    if int(m[1]) + 2018 != year:
        return None
    a, b = dt.date(year, 12, int(m[2])), dt.date(year + 1, 1, int(m[5]))
    if WD[a.weekday()] != m[3] or WD[b.weekday()] != m[6]:
        raise ValueError(f"{p}：年末年始の日と曜日が合いません（{m[0]}）")
    return a.isoformat(), b.isoformat()


def read_year_end_table(pdf, year):
    """地域別収集終了日・開始日 PDF → {地域: {"資源": (12月の最後, 1月の最初), "可燃": …, "不燃": …, "水銀": 12/2以降の水銀の日}}"""
    import pymupdf
    lines = [nfkc(x) for x in pymupdf.open(pdf)[0].get_text().split("\n") if x.strip()]
    out, i = {}, 0
    while i < len(lines):
        if not re.fullmatch(r"\D+[\d・〜]+", lines[i]):
            i += 1
            continue
        name, ds = lines[i], []
        for j in range(6):
            v = lines[i + 1 + j]
            m = re.match(r"(\d+)日\((.)\)", v)
            if not m:
                raise ValueError(f"{Path(pdf).name}：{name} の {j + 1}つ目の日が読めない：{v}")
            d = dt.date(year, 12, int(m[1])) if j < 3 else dt.date(year + 1, 1, int(m[1]))
            if WD[d.weekday()] != m[2]:
                raise ValueError(f"{Path(pdf).name}：{name} の {d} の曜日が合わない")
            ds.append(d.isoformat())
        m = re.search(r"(\d+)/(\d+) \((.)\)$", lines[i + 6])
        step = 7
        if not m:
            m = re.fullmatch(r"(\d+)/(\d+) \((.)\)", lines[i + 7])
            step = 8
        if not m:
            raise ValueError(f"{Path(pdf).name}：{name} の水銀の日が読めない")
        hg = dt.date(year if int(m[1]) == 12 else year + 1, int(m[1]), int(m[2]))
        if WD[hg.weekday()] != m[3]:
            raise ValueError(f"{Path(pdf).name}：{name} の水銀の日 {hg} の曜日が合わない")
        out[area_key(name)] = {"資源": (ds[0], ds[3]), "可燃": (ds[1], ds[4]), "不燃": (ds[2], ds[5]), "水銀": hg.isoformat()}
        i += step
    return out


# ---------------- 収集日を作る ----------------
def say_rules(r):
    nb = "・".join(f"第{k}" for k in sorted(r["不燃"]))
    return {"可燃": "毎週" + "・".join(WD[w] for w in sorted(r["可燃"])) + "曜日",
            "資源": "毎週" + WD[next(iter(r["資源"]))] + "曜日",
            "不燃": f"{nb}{WD[r['不燃曜']]}曜日（月2回）",
            "水銀": f"第{r['水銀']}{WD[r['不燃曜']]}曜日（月1回。燃やさないごみの日に）"}


def make_calendar(folder, year):
    folder = Path(folder)
    ye = read_year_end(folder / "年末年始.html", year)
    tentative = ye is None
    blank = (f"{year}-{BLANK[0]}", f"{year + 1}-{BLANK[1]}")
    off = blank if tentative else ye
    if tentative:
        print(f"  ！ {year}年度の年末年始のお知らせ（年末年始.html）がありません。カレンダーの空白の {off[0]}〜{off[1]} を「未定」にして作ります")
    table = read_table(folder / "収集曜日一覧表.pdf")
    ye_tab = {} if tentative else read_year_end_table(folder / "年末年始_地域別.pdf", year)
    problems, schedules, areas, seen = [], {}, [], set()
    pdfs = sorted((folder / "カレンダー").glob("*.pdf"))
    if not pdfs:
        raise ValueError(f"{folder / 'カレンダー'} に PDF がありません（download_sources.py で取る）")
    for pdf in pdfs:
        name, got, rest = read_pdf(pdf, year)
        key = area_key(name)
        if key in seen:
            problems.append(f"{pdf.name}：同じ地域のカレンダーが2つある（{name}）")
        seen.add(key)
        r = table.get(key)
        if r is None:
            problems.append(f"{pdf.name}：{name} が収集曜日一覧表にない")
            continue
        # カレンダーの日を、一覧表の曜日の決まりとくらべる（カレンダーが空白の年末年始はお知らせで決める）
        days = {}
        d, end = dt.date(year, 4, 1), dt.date(year + 1, 3, 31)
        while d <= end:
            k, want = d.isoformat(), rule_days(r, d)
            if blank[0] <= k <= blank[1]:
                if got.get(k):
                    problems.append(f"{pdf.name} {k}：年末年始の空白のはずの日に {got[k]}")
                if not tentative and want and not (off[0] <= k <= off[1]):
                    days[k] = want                       # お知らせ：休みの前の日（12/28〜12/30）は曜日どおり
            else:
                if got.get(k, []) != want:
                    problems.append(f"{pdf.name} {k}：カレンダー {got.get(k)}／一覧表の曜日 {want}")
                if got.get(k):
                    days[k] = got[k]
            d += dt.timedelta(days=1)
        if rest != {f"{year + 1}-01-01", f"{year + 1}-01-02"}:
            problems.append(f"{pdf.name}：「お休み」の日が {sorted(rest)}")
        # 年末年始の地域別の表とくらべる
        if not tentative:
            yt = ye_tab.get(key)
            if yt is None:
                problems.append(f"{name}：年末年始の地域別の表にない")
            else:
                for c in ("資源", "可燃", "不燃"):
                    last = max(x for x, cs in days.items() if c in cs and x < f"{year + 1}-01-01")
                    first = min(x for x, cs in days.items() if c in cs and x > f"{year}-12-31")
                    if (last, first) != yt[c]:
                        problems.append(f"{name} {c}：年末年始の表 {yt[c]}／作った日 {(last, first)}")
                hg = min(x for x, cs in days.items() if "水銀" in cs and x >= f"{year}-12-02")
                if hg != yt["水銀"]:
                    problems.append(f"{name} 水銀：年末年始の表 {yt['水銀']}／作った日 {hg}")
        rules = say_rules(r)
        sname = "／".join(f"{c}:{v.split('（')[0]}" for c, v in rules.items())
        if sname in schedules and schedules[sname]["days"] != days:
            problems.append(f"{name}：同じ曜日の地域と日がちがう")
        schedules.setdefault(sname, {"rules": rules, "days": days, "moved": {}})
        areas.append({"n": area_name(key), "s": sname, "y": YOMI.get(key[0]) or kana.yomi(key[0])})
    if not tentative and set(ye_tab) != seen:
        problems.append(f"年末年始の地域別の表とカレンダーの地域がちがう：{set(ye_tab) ^ seen}")
    missing = set(table) - seen
    if missing:
        problems.append(f"カレンダー PDF がない地域：{sorted(missing)}")
    areas.sort(key=lambda a: (a["y"], area_key(a["n"])[1]))
    print(f"目黒区：地域 {len(areas)}・収集日の組み合わせ {len(schedules)}・カレンダー {len(pdfs)}枚・"
          f"年末年始 {'未定' if tentative else '発表ずみ'}（{off[0]}〜{off[1]}）")
    if problems:
        for p in problems[:40]:
            print("  ！", p)
        raise ValueError(f"区のカレンダー・一覧表と合わないところが {len(problems)} あります")
    return {"year": year, "schedules": schedules, "areas": areas,
            "yearEnd": {"off": list(off), "tentative": tentative}}
