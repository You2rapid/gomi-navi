"""東京都 杉並区（13115）：区のページの「ごみと資源 収集曜日」の CSV と、地域ごとの「収集カレンダー」（PDF）から収集日データを作る。

このファイルのきまり（どの自治体も同じ形。tools/update_year.py・download_sources.py から使う）:
  NEED                       … 元データ/<県>/<自治体>/<年度>年度/ に置くファイルの名前
  download(year, dest, web, plan) … 区のサイトから NEED のファイルを探して plan に入れる（web は tools/lib/web.py）
  make_calendar(src, year)   … src（上のフォルダ）のファイルから収集日データ（dict）を作る。読めなければ例外で止める

杉並区の収集日は、町丁目ごとに曜日で決まっている。
  可燃ごみ 週2回・不燃ごみ 月2回（第1・3か第2・4の○曜日）・びん・かん・資源プラスチック 週1回・古紙・ペットボトル 週1回。祝日も収集する。
  年末年始だけ休み（令和8年度：12月31日〜1月3日。カレンダーで空いている）。
  ・曜日と地区：区のページ「ごみと資源 収集曜日検索」の CSV（garbage.csv。52地区。地区ごとにカレンダー PDF の URL がある）。
  ・見くらべ：地域ごとの収集カレンダー（PDF、28枚。令和8年度版。マスに「可燃」「不燃」「びん かん プラ」「古紙 ペット」の文字）。
    PDF の日付のマスの文字を読んで、曜日から作った日と1日ずつくらべる（合わなければ止まる）。年末年始の休みも PDF で確かめる。

フォルダ（元データ/13_東京都/13115_杉並区/<年度>年度/）に置くもの:
  garbage.csv              … https://www.city.suginami.tokyo.jp/documents/12125/garbage.csv
  カレンダー/<番号>.pdf    … CSV の pdf_url（https://www.city.suginami.tokyo.jp/shared/garbage/<番号>.pdf）
"""
import csv
import datetime as dt
import re
import sys
import unicodedata
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "lib"))
import kana  # noqa: E402

SITE = "https://www.city.suginami.tokyo.jp"
CSV_URL = SITE + "/documents/12125/garbage.csv"
NEED = ["garbage.csv"]
PERENNIAL = True
COLS = {"可燃ごみ": "可燃", "不燃ごみ": "不燃", "びん・かん・プラ": "びんかんプラ", "古紙・ペットボトル": "古紙ペット"}
CATS = list(COLS.values())
WD = "月火水木金土日"
# カレンダーのマスの文字 → 区分
LABEL = {"可燃": "可燃", "不燃": "不燃", "びん": "びんかんプラ", "かん": "びんかんプラ", "プラ": "びんかんプラ",
         "古紙": "古紙ペット", "ペット": "古紙ペット", "古紙・ペット": "古紙ペット"}
MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"]

# 年末年始：off＝収集しない日（両端をふくむ）
YEAR_END = {
    2026: {"off": ("2026-12-31", "2027-01-03"), "src": "令和8年度版 収集カレンダー（12月31日〜1月3日のマスが空いている。1月4日から収集）"},
}
DEFAULT_OFF = ("12-31", "01-03")

# 地区の読み（pykakasi では読みちがえる町名。郵便番号一覧の読みで確かめた）
YOMI = {"上高井戸": "かみたかいど", "堀ノ内": "ほりのうち"}


def nfkc(s):
    return unicodedata.normalize("NFKC", s).replace("～", "〜").replace("~", "〜").strip()


def parse_rule(cat, text):
    """「水曜日・土曜日」→ {"w": [2, 5]}、「第1,3月曜日」→ {"w": [0], "n": [1, 3]}"""
    t = nfkc(text)
    m = re.fullmatch(r"第(\d)[,、・](\d)([月火水木金土])曜日", t)
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


def read_csv(path):
    rows = list(csv.DictReader(open(path, encoding="utf-8-sig")))
    if not rows or not set(COLS) <= set(rows[0]):
        raise ValueError(f"CSV の列がかわりました：{list(rows[0]) if rows else ''}")
    if len(rows) < 40:
        raise ValueError(f"CSV が {len(rows)} 行しか読めません")
    return rows


def read_pdf(pdf, year):
    """地域の収集カレンダー（A4 3ページ。2・3ページに6か月ずつ）→ {日付: [区分]}"""
    import pymupdf
    doc = pymupdf.open(pdf)
    if f"令和{year - 2018}年度" not in nfkc(doc[0].get_text()):
        raise ValueError(f"{Path(pdf).name} は令和{year - 2018}年度のカレンダーではありません")
    out, months = {}, 0
    for page in doc:
        # 同じ文字が同じ場所に2つ重なっていることがある（10.pdf の「月 December」）ので、1つにする
        ws = list(dict.fromkeys((round(w[0], 1), round(w[1], 1), round(w[2], 1), round(w[3], 1), nfkc(w[4])) for w in page.get_text("words")))
        heads = [w for w in ws if w[4].split(" ")[-1] in MONTHS and w[1] < page.rect.height - 50]     # 「月　May」
        half = page.rect.width / 2
        for hw in heads:
            mo = MONTHS.index(hw[4].split(" ")[-1]) + 1
            y = year if mo >= 4 else year + 1
            side = 0 if hw[0] < half else 1
            x0, x1 = side * half, (side + 1) * half
            below = [h[1] for h in heads if h is not hw and (h[0] < half) == (hw[0] < half) and h[1] > hw[1]]
            top, bottom = hw[3], (min(below) - 12 if below else page.rect.height)     # 下の月の見出しの大きい数字（「７」）は入れない
            cols = [w for w in ws if top <= w[1] < top + 16 and x0 <= w[0] < x1 and len(w[4]) == 1 and w[4] in "日月火水木金土"]
            if len(cols) != 7:
                raise ValueError(f"{Path(pdf).name}：{y}年{mo}月の曜日の見出しが読めません（{[w[4] for w in cols]}）")
            centers = [(w[0] + w[2]) / 2 for w in sorted(cols, key=lambda w: w[0])]
            width = (centers[-1] - centers[0]) / 6

            def col(w):
                c = (w[0] + w[2]) / 2
                i = min(range(7), key=lambda i: abs(centers[i] - c))
                return i if abs(centers[i] - c) < width * 0.38 else None     # 余白の地区名（縦書きの数字）は入れない
            hb = max(w[3] for w in cols) - 6         # 曜日の見出しの下（1行目の日付は見出しのすぐ下にある）
            block = [w for w in ws if hb <= w[1] < bottom and x0 <= w[0] < x1 and w not in cols]
            last = (dt.date(y + mo // 12, mo % 12 + 1, 1) - dt.timedelta(days=1)).day
            nums = {}
            for w in block:
                if re.fullmatch(r"\d{1,2}", w[4]) and col(w) is not None:
                    n = int(w[4])
                    if n > last or (dt.date(y, mo, n).weekday() + 1) % 7 != col(w):
                        raise ValueError(f"{Path(pdf).name}：{y}年{mo}月{n}日の曜日の列が合いません")
                    nums[n] = w
            if len(nums) != last:
                raise ValueError(f"{Path(pdf).name}：{y}年{mo}月の日付が {len(nums)} しか読めません（ない日：{sorted(set(range(1, last + 1)) - set(nums))}）")
            for w in block:
                if w[4] not in LABEL:
                    continue
                c = col(w)
                cand = [x for x in nums.values() if col(x) == c and 0 < w[1] - x[1] < 45]
                if c is None or not cand:
                    raise ValueError(f"{Path(pdf).name}：{y}年{mo}月の札「{w[4]}」の日付が決まりません")
                n = int(min(cand, key=lambda x: w[1] - x[1])[4])
                k = dt.date(y, mo, n).isoformat()
                if LABEL[w[4]] not in out.setdefault(k, []):
                    out[k].append(LABEL[w[4]])
            months += 1
    if months != 12:
        raise ValueError(f"{Path(pdf).name}：{months}か月しか読めません")
    return out


# ---------------- 区のサイトから取ってくる ----------------
def download(year, dest, web, plan):
    raw = web.get(CSV_URL)
    plan.add(CSV_URL, dest / "garbage.csv", raw)
    seen = set()
    for r in csv.DictReader(web.text(raw).splitlines()):
        u = r.get("pdf_url", "")
        if u and u not in seen:
            seen.add(u)
            plan.add(SITE + u, dest / "カレンダー" / u.rsplit("/", 1)[1])


# ---------------- 収集日を作る ----------------
def make_calendar(folder, year):
    folder = Path(folder)
    if year in YEAR_END:
        off, tentative = YEAR_END[year]["off"], False
    else:
        off = (f"{year}-{DEFAULT_OFF[0]}", f"{year + 1}-{DEFAULT_OFF[1]}")
        tentative = True
        print(f"  ！ {year}年度の年末年始がまだ calendar.py の YEAR_END にありません。12/31〜1/3 を休みとして作ります")
    rows = read_csv(folder / "garbage.csv")
    problems, schedules, areas, pdf_of = [], {}, [], {}
    for r in rows:
        rules = {COLS[k]: parse_rule(k, r[k]) for k in COLS}
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
            schedules[key] = {"rules": {c: say(rules[c]) for c in CATS}, "days": days, "moved": {}}
        name = nfkc(r["町名"])
        town = re.match(r"\D+", name)[0]
        areas.append({"n": name, "s": key, "y": YOMI.get(town) or kana.yomi(town)})
        pdf_of.setdefault(r["pdf_url"].rsplit("/", 1)[1], set()).add(key)
    # カレンダー PDF と見くらべる
    checked = []
    for name, keys in sorted(pdf_of.items()):
        if len(keys) != 1:
            problems.append(f"{name}：1つのカレンダーに、ちがう曜日の地区がある（{keys}）")
            continue
        pdf = folder / "カレンダー" / name
        if not pdf.exists():
            problems.append(f"{name} がありません")
            continue
        got = read_pdf(pdf, year)
        want = schedules[next(iter(keys))]["days"]
        bad = [f"{k}：カレンダー {got.get(k)}／作った日 {want.get(k)}" for k in sorted(set(got) | set(want))
               if sorted(got.get(k, [])) != sorted(want.get(k, []))]
        problems += [f"{name} " + b for b in bad]
        checked.append(name)
    print(f"杉並区：地区 {len(areas)}・収集日の組み合わせ {len(schedules)}・見くらべたカレンダー {len(checked)}枚")
    if problems:
        for p in problems[:40]:
            print("  ！", p)
        raise ValueError(f"区のカレンダーと合わないところが {len(problems)} あります")
    return {"year": year, "schedules": schedules, "areas": areas,
            "yearEnd": {"off": list(off), "tentative": tentative}}
