"""東京都 墨田区（13107）：区の「地域別 資源・ごみの収集日カレンダー」（12地域 × 半年ずつの PDF）から収集日データを作る。

このファイルのきまり（どの自治体も同じ形。tools/update_year.py・download_sources.py から使う）:
  NEED                       … 元データ/<県>/<自治体>/<年度>年度/ に置くファイルの名前
  download(year, dest, web, plan) … 区のサイトから NEED のファイルを探して plan に入れる（web は tools/lib/web.py）
  make_calendar(src, year)   … src（上のフォルダ）のファイルから収集日データ（dict）を作る。読めなければ例外で止める

墨田区の収集日は、12の地域（町名のまとまり）ごとに曜日で決まる。
  資源（古紙・びん・缶・ペットボトル）週1回・プラスチック 週1回・燃やすごみ 週2回・燃やさないごみ 月2回（1回目・3回目 か 2回目・4回目 の曜日）。
  祝日も収集する。日曜日と年末年始は休み。
  ・収集日：地域別カレンダー PDF（1枚に6か月。4〜9月の版と10〜3月の版）。マスの日の数字の下に区分の文字（可燃・資源・プラ・不燃）。
    前の月・次の月のマスは白い字（見えない）なので、白い字はのぞいて読む（read_pdf）。日付は数字の位置（行・列）と数字で決める。
  ・PDF の上の「対象地域」と曜日（資源 火曜日、プラスチック 水曜日、燃やすごみ 月曜日・木曜日、燃やさないごみ 1回目・3回目 土曜日）の
    決まりと、読んだ日を全日くらべる。
  ・年末年始：区のお知らせ「年末年始の資源・ごみ収集日」の表（地域ごと・区分ごとに「12月の最後」「1月の最初」）。
    その間の日は休み。カレンダーの12月末・1月初めの日とも全地域くらべる。その年度のお知らせでなければ（曜日が合わない）、
    12/27〜1/3 を「未定」にする。

フォルダ（元データ/13_東京都/13107_墨田区/<年度>年度/）に置くもの:
  収集日.html     … https://www.city.sumida.lg.jp/kurashi/gomi_recycle/kateikei/gomi-calendar.html
  カレンダー/*.pdf … 上のページの「【地域別】資源・ごみの収集日カレンダー」（4〜9月 12枚・10〜3月 12枚）
  年末年始.html   … https://www.city.sumida.lg.jp/kurashi/gomi_recycle/oshirase/nennmatsunannshi.html
"""
import datetime as dt
import html
import re
import sys
import unicodedata
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "lib"))
import kana  # noqa: E402

SITE = "https://www.city.sumida.lg.jp"
DAYS_PAGE = SITE + "/kurashi/gomi_recycle/kateikei/gomi-calendar.html"
YE_PAGE = SITE + "/kurashi/gomi_recycle/oshirase/nennmatsunannshi.html"
NEED = ["収集日.html", "年末年始.html"]
WD = "月火水木金土日"
CATS = ["可燃", "資源", "プラ", "不燃"]
LABELS = {"可燃", "資源", "プラ", "不燃"}
WHITE = 0xFFFFFF
TENTATIVE = ("12-27", "01-03")
KANJI = "一二三四五六七八九"
# 年末年始の表の列の順番（区のページの見出し：資源・燃やすごみ・燃やさないごみ・プラスチック）
YE_COLS = ["資源", "可燃", "不燃", "プラ"]

# 地区の読み（pykakasi では読みちがえる町名。郵便番号一覧の読みで確かめた）
YOMI = {"吾妻橋": "あづまばし", "本所": "ほんじょ", "東駒形": "ひがしこまがた", "石原": "いしわら", "立川": "たてかわ",
        "菊川": "きくかわ", "東向島": "ひがしむこうじま", "向島": "むこうじま", "文花": "ぶんか"}


def nfkc(s):
    return unicodedata.normalize("NFKC", s).replace("～", "〜").replace("~", "〜").replace("　", " ").strip()


def cell(s):
    s = re.sub(r"<br\s*/?>", " ", s)
    return re.sub(r"\s+", " ", nfkc(html.unescape(re.sub(r"<[^>]+>", "", s)))).strip()


# ---------------- 地域の名前 ----------------
def town_set(name):
    """「本所1・2丁目、東駒形1・2丁目、吾妻橋、向島1・2・3丁目」「本所一・二丁目 東駒形一・二丁目 吾妻橋 向島一〜三丁目」
    → {("本所", 1), ("本所", 2), …, ("吾妻橋", None), …}（資料ごとの書き方をそろえてくらべる）"""
    s = nfkc(name)
    for i, k in enumerate(KANJI):
        s = s.replace(k, str(i + 1))
    out = set()
    for part in re.split(r"[、 ]+", s):
        if not part:
            continue
        m = re.fullmatch(r"(\D+?)([\d・〜]+)丁目", part)
        if not m:
            out.add((part, None))
            continue
        for p in m[2].split("・"):
            a, _, b = p.partition("〜")
            for n in range(int(a), int(b or a) + 1):
                out.add((m[1], n))
    return frozenset(out)


# ---------------- 地域別カレンダー PDF ----------------
def spans(page):
    out = []
    for b in page.get_text("dict")["blocks"]:
        for ln in b.get("lines", []):
            for s in ln["spans"]:
                t = s["text"].strip()
                if t:
                    out.append((s["bbox"], t, s["color"], s["size"]))
    return out


def parse_rules(ss):
    """PDF の上の曜日の決まり →（{区分: 決まり}, 区分の文字の並び）"""
    head = {}
    for (x0, y0, x1, y1), t, c, sz in ss:
        if y0 < 80 and re.search(r"曜日", t) and x0 > 250:
            head[round(x0)] = nfkc(t)
    vals = [head[k] for k in sorted(head)]
    if len(vals) != 4:
        raise ValueError(f"曜日の決まりが4つ読めない：{vals}")
    rules = {}
    for c, v in zip(["資源", "プラ", "可燃", "不燃"], vals):
        if c == "不燃":
            m = re.fullmatch(r"(\d)回目・(\d)回目 ?([月火水木金土])曜日", v)
            if not m:
                raise ValueError(f"燃やさないごみの曜日が読めない：{v}")
            rules[c] = {"w": WD.index(m[3]), "k": {int(m[1]), int(m[2])}}
        else:
            ws = re.findall(r"([月火水木金土])曜日", v)
            if not ws or re.sub(r"[月火水木金土]曜日|・", "", v):
                raise ValueError(f"{c}の曜日が読めない：{v}")
            rules[c] = {"w": {WD.index(w) for w in ws}}
    return rules


def rule_days(r, d):
    if d.weekday() == 6:
        return []
    out = [c for c in ("可燃", "資源", "プラ") if d.weekday() in r[c]["w"]]
    if d.weekday() == r["不燃"]["w"] and (d.day - 1) // 7 + 1 in r["不燃"]["k"]:
        out.append("不燃")
    return sorted(out, key=CATS.index)


def read_pdf(pdf):
    """地域のカレンダー PDF（半年ぶん）→ (地域の名前, 曜日の決まり, {日付: [区分]}, {(年, 月)})"""
    import pymupdf
    page = pymupdf.open(pdf)[0]
    ss = spans(page)
    names = [t for (x0, y0, x1, y1), t, c, sz in ss if y0 < 45 and x0 > 240 and sz > 11 and c != WHITE and "年" not in t]
    if len(names) != 1:
        raise ValueError(f"{Path(pdf).name}：対象地域が読めない（{names}）")
    rules = parse_rules(ss)
    vis = [s for s in ss if s[2] != WHITE]
    days, months = {}, set()
    # 曜日の見出し（日〜土の1文字）を、行ごと・7つずつのまとまりにする
    groups, rows = [], {}
    for x in ss:
        if len(x[1]) == 1 and x[1] in "日月火水木金土":
            rows.setdefault(round(x[0][1]), []).append(x)
    for r in rows.values():
        r.sort(key=lambda x: x[0][0])
        for i in range(0, len(r) - 6):
            if "".join(x[1] for x in r[i:i + 7]) == "日月火水木金土":
                groups.append(r[i:i + 7])
    for (bx0, by0, bx1, by1), t, c, sz in ss:
        m = re.fullmatch(r"月\s*([A-Za-z]+)", nfkc(t))
        if not m:
            continue
        num = [s for s in ss if re.fullmatch(r"\d{1,2}", s[1]) and s[3] > 20 and abs(s[0][3] - by1) < 12 and 0 < bx0 - s[0][2] < 15]
        yr = [s for s in ss if re.fullmatch(r"\d{4}年", s[1]) and abs(s[0][1] - by0) < 6 and 0 < num[0][0][0] - s[0][2] < 15] if num else []
        if len(num) != 1 or len(yr) != 1:
            raise ValueError(f"{Path(pdf).name}：月の見出しが読めない（{t}）")
        y, mo = int(yr[0][1][:4]), int(num[0][1])
        months.add((y, mo))
        # 曜日の見出し（日〜土の1文字）：月の見出しのすぐ下
        mx = (num[0][0][0] + num[0][0][2]) / 2
        wh = next((g for g in groups if 0 < g[0][0][1] - by1 < 20 and g[0][0][0] - 20 < mx < g[6][0][2] + 20), [])
        if [s[1] for s in wh] != list("日月火水木金土"):
            raise ValueError(f"{Path(pdf).name} {y}/{mo}：曜日の見出しが読めない（{[s[1] for s in wh]}）")
        cx = [(s[0][0] + s[0][2]) / 2 for s in wh]
        cw = (cx[6] - cx[0]) / 6
        left, right = cx[0] - cw / 2, cx[6] + cw / 2
        top = wh[0][0][3]
        # 下の月の見出し（同じ列の次の段）まで
        below = [s[0][1] for s in ss if re.fullmatch(r"月\s*[A-Za-z]+", nfkc(s[1])) and abs(s[0][0] - bx0) < 30 and s[0][1] > by1 + 20]
        bottom = min(below, default=page.rect.y1) - 15

        def col(x):
            return int((x - left) // cw)
        first = dt.date(y, mo, 1)
        start = first - dt.timedelta(days=(first.weekday() + 1) % 7)
        nums = [s for s in vis if re.fullmatch(r"\d{1,2}", s[1]) and left <= s[0][0] < right and top < s[0][1] < bottom and s[3] < 12]
        ys = []
        for v in sorted(round(s[0][1]) for s in nums):
            if not ys or v - ys[-1] > 5:
                ys.append(v)
        cells = []
        for s in nums:
            r = min(range(len(ys)), key=lambda i: abs(ys[i] - s[0][1]))
            c = col(s[0][0] + 2)
            # 1行目のはじめのマスが空白のとき、行の番号は日付の数字で決める
            cand = [start + dt.timedelta(days=7 * rr + c) for rr in range(6)]
            ok = [d for d in cand if d.day == int(s[1]) and d.month == mo]
            if len(ok) != 1:
                raise ValueError(f"{Path(pdf).name} {y}/{mo}：数字 {s[1]} の位置が日付と合わない")
            cells.append((s, ok[0], c))
        for s in vis:
            if s[1] not in LABELS or not (left <= s[0][0] < right and top < s[0][1] < bottom):
                continue
            c = col((s[0][0] + s[0][2]) / 2)
            above = [(n, d) for n, d, cc in cells if cc == c and n[0][3] <= s[0][1] + 2 and s[0][1] - n[0][3] < 20]
            if not above:
                raise ValueError(f"{Path(pdf).name} {y}/{mo}：「{s[1]}」の上に日の数字がない（{s[0]}）")
            n, d = max(above, key=lambda a: a[0][0][3])
            days.setdefault(d.isoformat(), []).append(s[1])
    out = {}
    for k, v in sorted(days.items()):
        if len(v) != len(set(v)):
            raise ValueError(f"{Path(pdf).name} {k}：同じ区分が2つ {v}")
        out[k] = sorted(v, key=CATS.index)
    return nfkc(names[0]), rules, out, months


# ---------------- 年末年始 ----------------
def table_rows(tb):
    """HTML の表 → 行の一覧（rowspan・colspan を広げる）"""
    rows, carry = [], {}
    for tr in re.findall(r"<tr.*?</tr>", tb, re.S):
        row, ci = [], 0
        cells = re.findall(r"<t([hd])([^>]*)>(.*?)</t[hd]>", tr, re.S)
        it = iter(cells)
        while True:
            if ci in carry:
                v, n = carry[ci]
                row.append(v)
                carry[ci] = (v, n - 1)
                if n - 1 == 0:
                    del carry[ci]
                ci += 1
                continue
            try:
                _, attr, body = next(it)
            except StopIteration:
                break
            rs = int((re.search(r'rowspan="(\d+)"', attr) or [0, 1])[1])
            cs = int((re.search(r'colspan="(\d+)"', attr) or [0, 1])[1])
            v = cell(body)
            for _ in range(cs):
                row.append(v)
                if rs > 1:
                    carry[ci] = (v, rs - 1)
                ci += 1
        while ci in carry:
            v, n = carry[ci]
            row.append(v)
            carry[ci] = (v, n - 1)
            if n - 1 == 0:
                del carry[ci]
            ci += 1
        rows.append(row)
    return rows


def read_year_end(path, year):
    """お知らせのページ → {地域の町の集合: {区分: (12月の最後, 1月の最初)}}。その年度のお知らせでなければ None"""
    p = Path(path)
    if not p.exists():
        return None
    t = p.read_text(encoding="utf-8")
    m = re.search(r"年末年始（令和(\d+)年末", t)
    if not m:
        raise ValueError(f"{p}：年末年始のお知らせの見出しが読めません")
    if int(m[1]) + 2018 != year:
        return None
    tbs = [tb for tb in re.findall(r"<table.*?</table>", t, re.S) if "12月の最後" in tb]
    if len(tbs) != 1:
        raise ValueError(f"{p}：年末年始の表が見つかりません")
    out = {}
    for r in table_rows(tbs[0]):
        if len(r) != 9 or "最後" in r[1] or "回収日" in r[1]:
            continue
        ds = {}
        for i, c in enumerate(YE_COLS):
            pair = []
            for j, (mo, yy) in enumerate(((12, year), (1, year + 1))):
                mm = re.fullmatch(r"(\d+)日\((.)曜日\)", r[1 + 2 * i + j].replace(" ", ""))
                if not mm:
                    raise ValueError(f"{p}：{r[0]} の日が読めない：{r[1 + 2 * i + j]}")
                d = dt.date(yy, mo, int(mm[1]))
                if WD[d.weekday()] != mm[2]:
                    raise ValueError(f"{p}：{r[0]} の {d} の曜日が合わない")
                pair.append(d.isoformat())
            ds[c] = tuple(pair)
        out[town_set(r[0])] = ds
    return out


# ---------------- 区のサイトから取ってくる ----------------
def download(year, dest, web, plan):
    raw = web.get(DAYS_PAGE)
    plan.add(DAYS_PAGE, dest / "収集日.html", raw)
    n = 0
    for u, t in web.links(web.text(raw), DAYS_PAGE):
        if not u.endswith(".pdf") or "から" not in t or "様式" in t:
            continue
        if not (f"{year}年4月から{year}年9月まで" in t or f"{year}年10月から{year + 1}年3月まで" in t):
            plan.problem(f"{DAYS_PAGE} のカレンダーが {year}年度のものではありません：{t}")
            return
        plan.add(u, dest / "カレンダー" / u.rsplit("/", 1)[-1])
        n += 1
    if n != 24:
        plan.problem(f"{DAYS_PAGE} の地域別カレンダーが {n}枚（12地域 × 2 のはず）")
    plan.add(YE_PAGE, dest / "年末年始.html")


# ---------------- 収集日を作る ----------------
def say_rules(r):
    return {"可燃": "毎週" + "・".join(WD[w] for w in sorted(r["可燃"]["w"])) + "曜日",
            "資源": "毎週" + "・".join(WD[w] for w in sorted(r["資源"]["w"])) + "曜日",
            "プラ": "毎週" + "・".join(WD[w] for w in sorted(r["プラ"]["w"])) + "曜日",
            "不燃": "第" + "・第".join(str(k) for k in sorted(r["不燃"]["k"])) + WD[r["不燃"]["w"]] + "曜日（月2回）"}


def make_calendar(folder, year):
    folder = Path(folder)
    ye = read_year_end(folder / "年末年始.html", year)
    tentative = ye is None
    off = (f"{year}-{TENTATIVE[0]}", f"{year + 1}-{TENTATIVE[1]}")
    if tentative:
        print(f"  ！ {year}年度の年末年始のお知らせ（年末年始.html）がありません。{off[0]}〜{off[1]} を「未定」にして作ります")
    pdfs = sorted((folder / "カレンダー").glob("*.pdf"))
    if not pdfs:
        raise ValueError(f"{folder / 'カレンダー'} に PDF がありません（download_sources.py で取る）")
    byarea, problems = {}, []
    for pdf in pdfs:
        name, rules, got, months = read_pdf(pdf)
        a = byarea.setdefault(town_set(name), {"name": name, "parts": []})
        a["parts"].append((pdf.name, rules, got, months))
    want_months = {(year + (m < 4), m) for m in range(1, 13)}
    schedules, areas = {}, []
    for key, a in byarea.items():
        months = set().union(*(p[3] for p in a["parts"]))
        if months != want_months or sum(len(p[3]) for p in a["parts"]) != 12:
            problems.append(f"{a['name']}：{year}年度の12か月がそろっていない（{sorted(months)}）")
            continue
        rs = [p[1] for p in a["parts"]]
        if any(r != rs[0] for r in rs):
            problems.append(f"{a['name']}：半年ごとの PDF で曜日の決まりがちがう（{rs}）")
            continue
        r = rs[0]
        got = {}
        for p in a["parts"]:
            got.update(p[2])
        yt = None if tentative else ye.get(key)
        if not tentative and yt is None:
            problems.append(f"{a['name']}：年末年始の表にない")
            continue
        days = {}
        d, end = dt.date(year, 4, 1), dt.date(year + 1, 3, 31)
        while d <= end:
            k = d.isoformat()
            cs = rule_days(r, d)
            if tentative:
                if off[0] <= k <= off[1]:
                    cs = []
            else:
                cs = [c for c in cs if not (yt[c][0] < k < yt[c][1])]
            if cs:
                days[k] = cs
            # カレンダーとくらべる（お知らせがまだのときは、年末年始の期間はくらべない）
            if not (tentative and off[0] <= k <= off[1]) and got.get(k, []) != cs:
                problems.append(f"{a['name']} {k}：カレンダー {got.get(k)}／作った日 {cs}")
            d += dt.timedelta(days=1)
        if not tentative:
            for c in CATS:
                last = max(x for x, cs in days.items() if c in cs and x < f"{year + 1}-01-01")
                first = min(x for x, cs in days.items() if c in cs and x > f"{year}-12-31")
                if (last, first) != yt[c]:
                    problems.append(f"{a['name']} {c}：年末年始の表 {yt[c]}／作った日 {(last, first)}")
        sname = "／".join(f"{c}:{v.split('（')[0]}" for c, v in say_rules(r).items())
        if sname in schedules and schedules[sname]["days"] != days:
            problems.append(f"{a['name']}：同じ曜日の地域と日がちがう")
        schedules.setdefault(sname, {"rules": say_rules(r), "days": days, "moved": {}})
        # 読み：地区名の町の読みを、書いてある順につなぐ（どの町の読みでも探せる）
        tws = []
        for part in a["name"].split("、"):
            tw = re.sub(r"[\d・〜]+丁目$", "", part)
            if tw not in tws:
                tws.append(tw)
        areas.append({"n": a["name"], "s": sname, "y": "、".join(YOMI.get(t) or kana.yomi(t) for t in tws)})
    if not tentative and set(ye) != set(byarea):
        problems.append(f"年末年始の表とカレンダーの地域がちがう：{set(ye) ^ set(byarea)}")
    print(f"墨田区：地域 {len(areas)}・収集日の組み合わせ {len(schedules)}・カレンダー {len(pdfs)}枚・"
          f"年末年始 {'未定' if tentative else '発表ずみ'}")
    if problems:
        for p in problems[:40]:
            print("  ！", p)
        raise ValueError(f"区のカレンダー・年末年始の表と合わないところが {len(problems)} あります")
    out = {"year": year, "schedules": schedules, "areas": areas}
    if not tentative:     # どの地域・区分も収集しない日（区の休み）
        a = dt.date.fromisoformat(max(v[c][0] for v in ye.values() for c in CATS)) + dt.timedelta(days=1)
        b = dt.date.fromisoformat(min(v[c][1] for v in ye.values() for c in CATS)) - dt.timedelta(days=1)
        off = (a.isoformat(), b.isoformat())
    out["yearEnd"] = {"off": list(off), "tentative": tentative}
    return out
