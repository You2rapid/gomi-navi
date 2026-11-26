"""東京都 葛飾区（13122）：区の「資源とごみの収集カレンダー」（収集地区1〜16の簡易版 PDF）から収集日データを作る。

このファイルのきまり（どの自治体も同じ形。tools/update_year.py・download_sources.py から使う）:
  NEED                       … 元データ/<県>/<自治体>/<年度>年度/ に置くファイルの名前
  download(year, dest, web, plan) … 区のサイトから NEED のファイルを探して plan に入れる（web は tools/lib/web.py）
  make_calendar(src, year)   … src（上のフォルダ）のファイルから収集日データ（dict）を作る。読めなければ例外で止める

葛飾区の収集日は、区を16の「収集地区」に分けて、収集地区ごとに曜日で決まる。
  プラスチック製容器包装（プラマークの日）週1回・資源（製品プラスチック・ペットボトル・びん・缶・古紙など）週1回・
  燃やすごみ 週2回・燃やさないごみ 月2回（第1・第3 か 第2・第4 の曜日）。祝日も収集する。年末年始は休み。
  ・地区：区のページ「○年度版『資源とごみの収集カレンダー』」の、町名・丁目ごとのカレンダーのリンク（「青戸1・2丁目のカレンダー（収集地区4）」。45行）。
    簡易版 PDF の見出しの町名とも見くらべる。
  ・収集日：収集地区ごとの「地区別（簡易版）」PDF（1ページに12か月。日付は文字、区分は絵）。
    マスの位置で日付を決め（月の見出しの下の何行目・何列目か）、マスの中の絵の色で区分を決める
    （緑の星＝資源、赤い玉＝燃やすごみ、青い三角＝燃やさないごみ、水色の四角＝プラマーク）。
    マスに書いてある日の数字は見くらべに使う（10地区の6月・4地区の5月は書きまちがいがあるので MISPRINT に書いた）。
  ・年末年始もカレンダーのとおりに作る（休みの日は地区によってちがう。12地区は 12/30 も休み）。

フォルダ（元データ/13_東京都/13122_葛飾区/<年度>年度/）に置くもの:
  収集カレンダー.html … 区のページ「○年度版『資源とごみの収集カレンダー』」
  簡易版/<番号>.pdf   … 上のページの「収集地区○（…）」の PDF（1〜16）
  （見くらべ用に、町名ごとのくわしいカレンダー（カレンダー/<番号>.pdf。画像）も置いた。全地区共通ページは 分別の冊子/ に置いた）
"""
import collections
import datetime as dt
import html
import re
import sys
import unicodedata
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "lib"))
import kana  # noqa: E402

SITE = "https://www.city.katsushika.lg.jp"
LIST_PAGE = SITE + "/kurashi/1000048/1017199/index.html"
N_AREAS = 16
NEED = ["収集カレンダー.html"] + [f"簡易版/{i}.pdf" for i in range(1, N_AREAS + 1)]
WD = "月火水木金土日"
CATS = ["燃やす", "プラ", "資源", "燃やさない"]
# 絵の色 → 区分
COLOR = {"G": "資源", "R": "燃やす", "B": "燃やさない", "C": "プラ"}
MIN_PIXELS = 100     # 4倍の画像で、この数より多くその色があれば絵がある（2026年度：絵は 270 以上、となりの絵のはみ出しなどは 41 まで）
# 区の PDF の日の数字の書きまちがい（{(地区, 年, 月): 説明}）。日付はマスの位置で決めるので、ここに書いたものは止めずに進む
MISPRINT = {
    (10, 2026, 6): "10地区の6月の最後の行は「30・31」と書いてあるが、マスの位置は6/29（月）・6/30（火）",
    (4, 2026, 5): "4地区の5月の最後の土曜日のマスに「31」と書いてある（マスの位置は5/30）。5/31（日）のマスはない（日曜日は収集がない）",
}

# 地区の読み（pykakasi では読みちがえる町名。郵便番号一覧の読みで確かめた）
YOMI = {
    "お花茶屋": "おはなぢゃや",
    "金町": "かなまち",
    "白鳥": "しらとり",
    "新宿": "にいじゅく",
    "東金町": "ひがしかなまち",
    "東堀切": "ひがしほりきり",
    "東四つ木": "ひがしよつぎ",
    "南水元": "みなみみずもと",
    "四つ木": "よつぎ",
}


def nfkc(s):
    return unicodedata.normalize("NFKC", s).replace("～", "〜").replace("~", "〜").replace("　", " ").strip()


def read_list(path):
    """区のページ → [(地区名, 収集地区の番号)]。同じ行が2回出ることはない"""
    t = Path(path).read_text(encoding="utf-8")
    out = []
    for x in re.findall(r"<a[^>]+href=\"[^\"]+\.pdf\"[^>]*>(.*?)</a>", t, re.S):
        x = nfkc(html.unescape(re.sub(r"<[^>]+>", "", x)))
        m = re.fullmatch(r"(.+?)のカレンダー\(収集地区(\d+)\).*", x)
        if m:
            out.append((m[1], int(m[2])))
    if len(out) < 40:
        raise ValueError(f"{path} の町名のカレンダーの行が {len(out)} しかありません（ページの形が変わった？ calendar.py を直す）")
    return out


def easy_links(page_html, base, web):
    """区のページ → {収集地区の番号: 簡易版 PDF の URL}"""
    out = {}
    for u, t in web.links(page_html, base):
        m = re.match(r"収集地区(\d+)\(", nfkc(t))
        if m and u.lower().endswith(".pdf"):
            out[int(m[1])] = u
    return out


def cls(r, g, b):
    if g > 140 and r < 130 and b < 130:
        return "G"
    if r > 180 and g < 130 and b < 110:
        return "R"
    if b > 140 and r < 90 and g < 130:
        return "B"
    if b > 180 and g > 140 and r < 120:
        return "C"
    return None


def read_pdf(pdf, n, year, problems):
    """簡易版 PDF → ({日付: {区分}}, 簡易版の見出しの町名の文字)"""
    import pymupdf
    page = pymupdf.open(pdf)[0]
    Z = 4
    pix = page.get_pixmap(matrix=pymupdf.Matrix(Z, Z))
    words = page.get_text("words")
    heads = []
    for w in words:
        m = re.fullmatch(r"(\d{4})年(\d{1,2})月", w[4])
        if m:
            heads.append((int(m[1]), int(m[2]), (w[0] + w[2]) / 2, w[3]))
    if sorted((y, m) for y, m, *_ in heads) != sorted((year + (m < 4), m) for m in range(1, 13)):
        problems.append(f"収集地区{n}：月の見出しが12か月そろっていない（{[(y, m) for y, m, *_ in heads]}）")
        return {}, ""
    cols = []      # 曜日の見出しの列のまん中（上下の月で同じ位置なので、1つにまとめる）
    for c in sorted((w[0] + w[2]) / 2 for w in words if len(w[4]) == 1 and w[4] in "日月火水木金土"):
        if not cols or c - cols[-1] > 3:
            cols.append(c)
    nums = [w for w in words if re.fullmatch(r"\d{1,2}", w[4])]
    ys = sorted({round(w[1], 1) for w in nums})
    gaps = sorted(b - a for a, b in zip(ys, ys[1:]) if 15 < b - a < 40)
    rh = gaps[len(gaps) // 2]          # 1行の高さ
    blocks = collections.defaultdict(list)
    for w in nums:
        cand = [h for h in heads if h[3] < w[1] and abs(h[2] - w[0]) < 85]
        if not cand:
            problems.append(f"収集地区{n}：日の数字「{w[4]}」がどの月かわからない")
            continue
        blocks[min(cand, key=lambda h: w[1] - h[3])[:2]].append(w)
    days = {}
    for (y, m), ws in sorted(blocks.items()):
        cx = sorted(c for c in cols if min(abs(c - w[0] - 5) for w in ws) < 12)   # この月の7列
        rows = []      # この月の行の上のはし（上から順に）
        for y0 in sorted(w[1] for w in ws):
            if not rows or y0 - rows[-1] > 5:
                rows.append(y0)
        first = dt.date(y, m, 1)
        nmonth = ((first.replace(day=28) + dt.timedelta(days=4)).replace(day=1) - first).days
        seen = set()
        for w in ws:
            c = min(range(len(cx)), key=lambda i: abs(cx[i] - w[0] - 5))
            row = min(range(len(rows)), key=lambda i: abs(rows[i] - w[1]))
            # 日曜はじまりの列（0＝日）→ 日付
            day = row * 7 + c - (first.weekday() + 1) % 7 + 1
            if not 1 <= day <= nmonth or len(cx) != 7:
                problems.append(f"収集地区{n} {y}年{m}月：「{w[4]}」のマスの位置がおかしい（行 {row}・列 {c}）")
                continue
            if int(w[4]) != day and (n, y, m) not in MISPRINT:
                problems.append(f"収集地区{n} {y}年{m}月：マスの位置は{day}日なのに「{w[4]}」と書いてある")
            seen.add(day)
            cnt = collections.Counter()
            for yy in range(int((w[1] - 1) * Z), int((w[1] + rh - 2) * Z)):
                for xx in range(int((cx[c] - 9.3) * Z), int((cx[c] + 9.3) * Z)):
                    if w[0] - 0.5 <= xx / Z <= w[2] + 0.5 and w[1] - 0.5 <= yy / Z <= w[3] + 0.5:
                        continue      # 日の数字（祝日は赤い字）は数えない
                    k = cls(*pix.pixel(xx, yy)[:3])
                    if k:
                        cnt[k] += 1
            cs = {COLOR[k] for k, v in cnt.items() if v >= MIN_PIXELS}
            if "-vv" in sys.argv and cnt:
                print("   ", n, y, m, day, dict(cnt))
            if cs:
                days[dt.date(y, m, day)] = cs
        if seen != set(range(1, nmonth + 1)) and (n, y, m) not in MISPRINT:
            problems.append(f"収集地区{n} {y}年{m}月：日のマスが足りない（{sorted(set(range(1, nmonth + 1)) - seen)}）")
    title = nfkc(page.get_text())
    return days, title


def key_of(d, cat):
    """区分ごとの決まりのかぎ：燃やさないごみは（曜日, 第何）、ほかは曜日"""
    return (d.weekday(), (d.day - 1) // 7 + 1) if cat == "燃やさない" else d.weekday()


def rules_of(days):
    cnt = collections.defaultdict(collections.Counter)
    for d, cs in days.items():
        for c in cs:
            cnt[c][key_of(d, c)] += 1
    return {c: {k for k, v in cnt[c].items() if v >= 4} for c in CATS}


def say(rule, cat):
    if cat == "燃やさない":
        by = collections.defaultdict(list)
        for w, k in sorted(rule):
            by[w].append(f"第{k}")
        return "・".join(f"{'・'.join(ks)}{WD[w]}曜日" for w, ks in sorted(by.items())) + "（月2回）"
    return f"毎週{'・'.join(WD[w] for w in sorted(rule))}曜日"


# ---------------- 区のサイトから取ってくる ----------------
def download(year, dest, web, plan):
    page_url = None
    top = web.text(web.get(LIST_PAGE))
    for u, t in web.links(top, LIST_PAGE):
        if f"{year}年度版" in nfkc(t) and "収集カレンダー" in nfkc(t):
            page_url = u
    if not page_url:
        plan.problem(f"{LIST_PAGE} に「{year}年度版『資源とごみの収集カレンダー』」のページがありません（まだ出ていない？）")
        return
    raw = web.get(page_url)
    page = web.text(raw)
    plan.add(page_url, dest / "収集カレンダー.html", raw)
    links = easy_links(page, page_url, web)
    for n in range(1, N_AREAS + 1):
        if n in links:
            plan.add(links[n], dest / "簡易版" / f"{n}.pdf")
        else:
            plan.problem(f"{page_url} に「収集地区{n}（…）」の簡易版 PDF がありません")


# ---------------- 収集日を作る ----------------
def make_calendar(folder, year):
    folder = Path(folder)
    rows = read_list(folder / "収集カレンダー.html")
    problems, schedules, odd = [], {}, []
    titles = {}
    for n in range(1, N_AREAS + 1):
        days, titles[n] = read_pdf(folder / "簡易版" / f"{n}.pdf", n, year, problems)
        if not days:
            continue
        rule = rules_of(days)
        for c in CATS:
            if not rule[c]:
                problems.append(f"収集地区{n}：{c}の曜日がわからない")
        # ふだんの曜日からはずれた日（年末年始のほかにあれば、絵の読みまちがいかもしれないので止める）
        d = dt.date(year, 4, 1)
        while d <= dt.date(year + 1, 3, 31):
            want = {c for c in CATS if key_of(d, c) in rule[c]}
            have = days.get(d, set())
            if want != have:
                txt = f"収集地区{n} {d}：カレンダー {sorted(have)}／ふだん {sorted(want)}"
                if dt.date(year, 12, 29) <= d <= dt.date(year + 1, 1, 4) and have <= want:
                    odd.append(txt)
                else:
                    problems.append(txt)
            d += dt.timedelta(days=1)
        schedules[str(n)] = {"rules": {c: say(rule[c], c) for c in CATS},
                             "days": {d.isoformat(): [c for c in CATS if c in days[d]] for d in sorted(days)},
                             "moved": {}}
    # 区のページの町名と、簡易版の見出しの町名を見くらべる
    areas = []
    for name, n in rows:
        town = re.sub(r"[\d・〜]+丁目$", "", name)
        if town not in titles.get(n, ""):
            problems.append(f"「{name}」（収集地区{n}）が、収集地区{n}の簡易版の見出しにない")
        areas.append({"n": name, "s": str(n), "y": YOMI.get(town) or kana.yomi(town), "d": f"収集地区{n}"})
    if {int(a["s"]) for a in areas} != set(range(1, N_AREAS + 1)):
        problems.append("町名のない収集地区がある")
    off = sorted(d for d in (dt.date(year, 12, 29) + dt.timedelta(days=i) for i in range(7))
                 if all(d.isoformat() not in s["days"] for s in schedules.values()))
    print(f"葛飾区：地区 {len(areas)}・収集地区 {len(schedules)}・年末年始でふだんとちがう日 {len(odd)}・"
          f"数字の書きまちがいを直した月 {len(MISPRINT)}")
    if "-v" in sys.argv:
        for s in odd:
            print("  ・", s)
    if problems:
        for p in problems[:40]:
            print("  ！", p)
        raise ValueError(f"読めないところが {len(problems)} あります")
    return {"year": year, "schedules": schedules, "areas": areas,
            "yearEnd": {"off": [off[0].isoformat(), off[-1].isoformat()] if off else [], "tentative": False}}
