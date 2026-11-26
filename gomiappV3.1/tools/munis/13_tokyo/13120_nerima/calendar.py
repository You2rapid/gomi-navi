"""東京都 練馬区（13120）：区の「地域別収集曜日一覧」と、地域ごとの年度のカレンダー（PDF）から収集日データを作る。

このファイルのきまり（どの自治体も同じ形。tools/update_year.py・download_sources.py から使う）:
  NEED                       … 元データ/<県>/<自治体>/<年度>年度/ に置くファイルの名前
  download(year, dest, web, plan) … 区のサイトから NEED のファイルを探して plan に入れる（web は tools/lib/web.py）
  make_calendar(src, year)   … src（上のフォルダ）のファイルから収集日データ（dict）を作る。読めなければ例外で止める

練馬区は「地域別収集曜日一覧」（あ行・か行・さ行・た行・な行・は行・ま行や行の7ページ）に、町名・丁目ごとの曜日の表と、
その地域の「令和○年4月〜○年3月」のカレンダー（PDF、A4 2ページ、文字入り）がある。
  区分：可燃ごみ（週2回）・不燃ごみ（月2回、第1・3か第2・4の○曜）・容器包装プラスチックと古紙（週1回、同じ日）・びん・缶（週1回）・ペットボトル（週1回）
  カレンダーの札の文字：可＝可燃、不＝不燃、プ 紙＝古紙・プラ、び 缶＝びん・缶、ペ＝ペットボトル
  ・**収集日はカレンダーの PDF の日付**（年末年始・祝日の扱いがそのまま入っている。祝日も収集する）。
  ・表の曜日で作った日とくらべ、ちがう日（年末年始の休み）は README・読み取りの注意.txt に出す。
    休み以外でちがう日（表とカレンダーが食いちがう）があれば止まる。
  ・地区は表の行（101）。名前は「町名＋丁目」（全域は町名だけ。「都営光が丘第一アパート」などは町名（…））。説明はカレンダーの問合せ先の清掃事務所。

フォルダ（元データ/13_東京都/13120_練馬区/<年度>年度/）に置くもの:
  曜日一覧_<a・ka・sa・ta・na・ha・maya>.html … 地域別収集曜日一覧の7ページ
  カレンダー/<PDF の名前>                    … 表の「カレンダー（PDF）」のリンク先（101）。download が保存する
"""
import datetime as dt
import html as H
import re
import sys
import unicodedata
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "lib"))
import kana  # noqa: E402

SITE = "https://www.city.nerima.tokyo.jp"
BASE = SITE + "/kurashi/gomi/wakekata/ichiran/"
GROUPS = ["a", "ka", "sa", "ta", "na", "ha", "maya"]
NEED = [f"曜日一覧_{g}.html" for g in GROUPS]
CATS = ["可燃", "不燃", "プラ紙", "びん缶", "ペット"]       # 表の列の順
LABEL = {"可": "可燃", "不": "不燃", "プ": "プラ紙", "紙": "プラ紙", "び": "びん缶", "缶": "びん缶", "ペ": "ペット", "ぺ": "ペット"}
WD = "月火水木金土日"


def nfkc(s):
    return unicodedata.normalize("NFKC", s).strip()


# ---------------- 曜日の表 ----------------
def read_tables(folder):
    """7ページの表 → [{"town", "part", "vals": (可燃, 不燃, プラ紙, びん缶, ペット), "pdf"}]"""
    rows = []
    for g in GROUPS:
        t = (Path(folder) / f"曜日一覧_{g}.html").read_text(encoding="utf-8")
        head = re.search(r"<tr>(.*?)</tr>", t, re.S)[1]
        ths = [nfkc(re.sub(r"<[^>]+>", "", x)) for x in re.findall(r"<th[^>]*>(.*?)</th>", head, re.S)]
        if not (ths[2:5] == ["可燃ごみ", "不燃ごみ", "容器包装プラスチック(注釈)・古紙(新聞、ダンボール等)"] and ths[5] == "びん・缶"):
            raise ValueError(f"曜日一覧_{g}.html の表の列がかわりました：{ths}（calendar.py を直す）")
        for tr in re.findall(r"<tr>(.*?)</tr>", t, re.S):
            tds = re.findall(r"<td[^>]*>(.*?)</td>", tr, re.S)
            if len(tds) < 8:
                continue
            c = [nfkc(H.unescape(re.sub(r"<[^>]+>", "", x))) for x in tds]
            pdf = re.search(r'href="[^"]*/([^"/]+\.pdf)"', tds[7])
            if not pdf:
                raise ValueError(f"{c[0]}{c[1]}：カレンダーの PDF のリンクがありません")
            rows.append({"town": c[0], "part": c[1], "vals": tuple(c[2:7]), "pdf": pdf[1]})
    return rows


def parse_rule(cat, text):
    """「月曜･木曜」→ {"w": [0, 3]}、「第1･3 月曜」→ {"w": [0], "n": [1, 3]}"""
    t = re.sub(r"\s", "", nfkc(text)).replace("･", "・")
    m = re.fullmatch(r"第(\d)・(\d)([月火水木金土])曜", t)
    if m:
        return {"w": [WD.index(m[3])], "n": [int(m[1]), int(m[2])]}
    ws = re.findall(r"([月火水木金土])曜", t)
    if ws and re.fullmatch(r"([月火水木金土]曜・?)+", t):
        return {"w": [WD.index(w) for w in ws]}
    raise ValueError(f"{cat} の曜日が読めません：「{text}」")


def say(rule):
    ws = "・".join(WD[w] for w in rule["w"])
    return f"毎月第{rule['n'][0]}・{rule['n'][1]}{ws}曜日" if "n" in rule else f"毎週{ws}曜日"


def hits(rule, d):
    return d.weekday() in rule["w"] and ("n" not in rule or (d.day - 1) // 7 + 1 in rule["n"])


def area_name(town, part):
    if part in ("全域", ""):
        return town
    if re.fullmatch(r"[\d・～〜~]+丁目", part):
        return town + part.replace("～", "〜").replace("~", "〜")
    return f"{town}（{part}）"


# ---------------- カレンダーの PDF ----------------
def read_pdf(pdf, year):
    """年度のカレンダー（A4 2ページ、1ページに6か月）→ (地域名, {日付: [区分…]})"""
    import pymupdf
    doc = pymupdf.open(pdf)
    out, title, months = {}, "", 0
    for page in doc:
        ws = page.get_text("words")
        if not title:
            big = [w for w in ws if w[1] < 45 and not re.fullmatch(r"[\d]+", w[4])]
            title = "".join(w[4] for w in sorted(big, key=lambda w: w[0]))
        heads = [w for w in ws if re.fullmatch(r"20\d\d", w[4])]
        for hw in heads:
            mw = [w for w in ws if abs(w[1] - hw[1]) < 3 and 0 < w[0] - hw[2] < 30 and re.fullmatch(r"\d{1,2}", w[4])]
            if not mw:
                raise ValueError(f"{Path(pdf).name}：{hw[4]}年の月が読めません")
            y, mo = int(hw[4]), int(mw[0][4])
            x0, top = hw[0] - 10, hw[3]
            cols = [w for w in ws if top <= w[1] < top + 12 and x0 <= w[0] < x0 + 240 and w[4] in "日月火水木金土"]
            if len(cols) != 7:
                raise ValueError(f"{Path(pdf).name}：{y}年{mo}月の曜日の見出しが読めません")
            cx = {w[4]: (w[0] + w[2]) / 2 for w in cols}
            centers = [cx[c] for c in "日月火水木金土"]

            def col(w):
                c = (w[0] + w[2]) / 2
                i = min(range(7), key=lambda i: abs(centers[i] - c))
                return i if abs(centers[i] - c) < 17 else None
            block = [w for w in ws if top + 8 <= w[1] < top + 230 and x0 <= w[0] < x0 + 245]
            nums = [w for w in block if re.fullmatch(r"\d{1,2}", w[4]) and col(w) is not None]
            # 次の月の見出しより下は、この月ではない
            nxt = [h for h in heads if h is not hw and abs(h[0] - hw[0]) < 20 and h[1] > hw[1]]
            if nxt:
                lim = min(h[1] for h in nxt)
                nums = [w for w in nums if w[1] < lim]
                block = [w for w in block if w[1] < lim]
            block = [w for w in block if w[1] < max(n[1] for n in nums) + 34]     # 下の凡例（可・不燃…）は入れない
            last = (dt.date(y + mo // 12, mo % 12 + 1, 1) - dt.timedelta(days=1)).day
            days = {}
            for w in nums:
                n = int(w[4])
                d = dt.date(y, mo, n) if n <= last else None
                if d is None or (d.weekday() + 1) % 7 != col(w):
                    raise ValueError(f"{Path(pdf).name}：{y}年{mo}月{w[4]}日の曜日の列が合いません")
                days[n] = w
            for w in block:
                if w[4] not in LABEL:
                    continue
                c = col(w) if col(w) is not None else min(range(7), key=lambda i: abs(centers[i] - (w[0] + w[2]) / 2))
                cand = [x for x in days.values() if col(x) == c and 0 < w[1] - x[1] < 34]
                if not cand:
                    raise ValueError(f"{Path(pdf).name}：{y}年{mo}月の札「{w[4]}」の日付が決まりません")
                n = int(min(cand, key=lambda x: w[1] - x[1])[4])
                k = dt.date(y, mo, n).isoformat()
                cat = LABEL[w[4]]
                if cat not in out.setdefault(k, []):
                    out[k].append(cat)
            months += 1
    if months != 12:
        raise ValueError(f"{Path(pdf).name}：{months}か月しか読めません")
    if any(not (f"{year}-04-01" <= k <= f"{year + 1}-03-31") for k in out):
        raise ValueError(f"{Path(pdf).name}：{year}年度のカレンダーではありません")
    office = re.search(r"問合せ先】\s*(\S+清掃事務所)", doc[0].get_text())
    return title, {k: [c for c in CATS if c in v] for k, v in sorted(out.items())}, office[1] if office else ""


# ---------------- 区のサイトから取ってくる ----------------
def download(year, dest, web, plan):
    for g in GROUPS:
        url = BASE + f"{g}_gyochiiki.html"
        page = web.text(web.get(url))
        cap = re.search(r"<caption>(.*?)</caption>", page)
        if not cap or f"令和{year - 2018}年度" not in cap[1]:
            plan.problem(f"{url} の表が令和{year - 2018}年度ではありません（{cap[1] if cap else '見出しなし'}）")
            continue
        plan.add(url, dest / f"曜日一覧_{g}.html", page.encode("utf-8"))
        for u, label in web.links(page, url):
            if u.endswith(".pdf") and "カレンダー" in label:
                plan.add(u, dest / "カレンダー" / u.split("/")[-1])


# ---------------- 収集日を作る ----------------
def make_calendar(folder, year):
    folder = Path(folder)
    rows = read_tables(folder)
    schedules, areas, notes, offdays = {}, [], [], set()
    for r in rows:
        pdf = folder / "カレンダー" / r["pdf"]
        if not pdf.exists():
            raise FileNotFoundError(f"カレンダーがありません：{pdf}（download_sources.py で保存する）")
        title, days, office = read_pdf(pdf, year)
        if nfkc(title).replace(" ", "") and r["town"] not in nfkc(title):
            notes.append(f"{r['town']}{r['part']}：カレンダーの題が「{title}」")
        rules = {c: parse_rule(c, v) for c, v in zip(CATS, r["vals"])}
        # 表の曜日で作った日とくらべる。カレンダーにない日は「休み」、カレンダーにだけある日は食いちがい
        d, end = dt.date(year, 4, 1), dt.date(year + 1, 3, 31)
        while d <= end:
            k = d.isoformat()
            want = [c for c in CATS if hits(rules[c], d)]
            got = days.get(k, [])
            extra = [c for c in got if c not in want]
            if extra:
                raise ValueError(f"{area_name(r['town'], r['part'])} {k}：カレンダーに表の曜日にない「{'・'.join(extra)}」がある")
            if [c for c in want if c not in got]:
                offdays.add(k)
            d += dt.timedelta(days=1)
        key = "／".join(f"{c}:{re.sub(r'\s', '', v).replace('･', '・')}" for c, v in zip(CATS, r["vals"]))
        if key in schedules and schedules[key]["days"] != days:
            raise ValueError(f"同じ曜日の地域で、カレンダーの日がちがいます：{area_name(r['town'], r['part'])}")
        schedules.setdefault(key, {"rules": {c: say(rules[c]) for c in CATS}, "days": days, "moved": {}})
        a = {"n": area_name(r["town"], r["part"]), "s": key, "y": kana.yomi(r["town"])}
        d = []
        if r["part"] == "上記以外の地域":
            others = [x["part"] for x in rows if x["town"] == r["town"] and x is not r and x["part"] != "上記以外の地域"]
            d.append("・".join(others) + "以外")
        if office:
            d.append(office)
        if d:
            a["d"] = "／".join(d)
        areas.append(a)
    off = sorted(offdays)
    print(f"練馬区：地区 {len(areas)}・収集日の組み合わせ {len(schedules)}")
    print(f"  表の曜日にあるのにカレンダーにない日（年末年始など）：{'・'.join(off)}")
    for n in notes:
        print("  ？", n)
    (folder / "読み取りの注意.txt").write_text(
        f"練馬区 {year}年度：表の曜日にあるのに、カレンダーで収集がない日（どれかの地域で）\n" + "\n".join(off) + "\n\n"
        + "\n".join(notes) + "\n", encoding="utf-8")
    ye = [k for k in off if k[5:7] in ("12", "01")]
    return {"year": year, "schedules": schedules, "areas": areas,
            "yearEnd": {"off": [ye[0], ye[-1]] if ye else [], "tentative": False}}
