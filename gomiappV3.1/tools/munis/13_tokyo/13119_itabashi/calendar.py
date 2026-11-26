"""東京都 板橋区（13119）：区のページ「地域別 資源回収・ごみ収集曜日カレンダー」の表と、地域ごとのカレンダー（PDF）から収集日データを作る。

このファイルのきまり（どの自治体も同じ形。tools/update_year.py・download_sources.py から使う）:
  NEED                       … 元データ/<県>/<自治体>/<年度>年度/ に置くファイルの名前
  download(year, dest, web, plan) … 区のサイトから NEED のファイルを探して plan に入れる（web は tools/lib/web.py）
  make_calendar(src, year)   … src（上のフォルダ）のファイルから収集日データ（dict）を作る。読めなければ例外で止める

板橋区の収集日は、町丁目ごとに曜日で決まっている。
  資源（古紙・びん・缶・ペットボトル・プラスチックなど）週1回・可燃ごみ 週3回・不燃ごみ 月2回（「1回目・3回目」か「2回目・4回目」の○曜日）。
  祝日も収集する。年末年始は区が11月ごろ別に知らせる（令和8年度：1月1日〜3日は休み。12月31日は資源は休み、可燃ごみは収集する）。
  ・曜日と地区：区のページの「資源回収・ごみ収集地域別一覧表」（HTML の表。70地区。地区ごとにカレンダー PDF の番号がある）。
  ・見くらべ：地域ごとの「資源回収・ごみ収集曜日カレンダー」（PDF、24枚。日付のマスの色：緑＝資源、ピンク＝可燃、水色＝不燃）。
    マスの色を読んで、曜日から作った日と1日ずつくらべる（年末年始の 12/29〜1/4 はカレンダーにのらないので、のぞく）。
  ・年末年始：区の「年末年始の資源・ごみの収集日」（PDF）の表（地域ごとの 12月の収集最終日・1月の収集開始日）を YEAR_END に書き写し、作った日とくらべる。

フォルダ（元データ/13_東京都/13119_板橋区/<年度>年度/）に置くもの:
  曜日一覧.html          … https://www.city.itabashi.tokyo.jp/tetsuduki/gomi/kaishu/1038152.html
  カレンダー/<番号>.pdf  … 表のリンク（e01〜e12・w01〜w12）
  年末年始.pdf           … https://www.city.itabashi.tokyo.jp/tetsuduki/gomi/1035547.html の PDF（見くらべ用）
"""
import datetime as dt
import html
import re
import sys
import unicodedata
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "lib"))
import kana  # noqa: E402

SITE = "https://www.city.itabashi.tokyo.jp"
PAGE = SITE + "/tetsuduki/gomi/kaishu/1038152.html"
NEED = ["曜日一覧.html"]
PERENNIAL = True
COLS = {"資源": "資源", "可燃ごみ": "可燃", "不燃ごみ": "不燃"}
CATS = list(COLS.values())
WD = "月火水木金土日"
COLOR = {(0, 255, 0): "資源", (255, 204, 204): "可燃", (0, 255, 255): "不燃"}     # カレンダーのマスの色
KANJI = {"一": 1, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9}

# 年末年始：off＝収集しない日（両端をふくむ）、keep＝その間でも収集する区分と日、table＝区の表（地域、12月の最終日、1月の開始日）
YEAR_END = {
    2026: {
        "off": ("2026-12-31", "2027-01-03"), "keep": {"2026-12-31": ["可燃"]},
        "src": "区の「令和8年度 年末年始の資源・ごみの収集日」（PDF、2026-11-02）。1/1〜1/3 は休み、12/31 は資源・粗大は休みで可燃ごみは収集",
        # 地域、12月の最終日（資源・可燃・不燃）、1月の開始日（資源・可燃・不燃）
        "table": [
            ("小豆沢、稲荷台、清水町、蓮沼町、本町、中台、西台一～二丁目、若木三丁目", (28, 31, 23), (4, 5, 13)),
            ("西台三～四丁目、若木一～二丁目", (28, 31, 18), (4, 5, 15)),
            ("前野町", (28, 31, 25), (4, 5, 8)),
            ("大谷口、大谷口上町、大谷口北町、大山西町、向原", (29, 30, 17), (5, 4, 7)),
            ("赤塚三丁目、成増二～三丁目", (29, 30, 24), (5, 4, 14)),
            ("赤塚四～五・八丁目、成増四～五丁目", (29, 30, 19), (5, 4, 16)),
            ("小茂根、桜川、東山町", (29, 30, 26), (5, 4, 9)),
            ("坂下、蓮根、東坂下、舟渡、徳丸五～八丁目", (30, 31, 18), (6, 5, 15)),
            ("相生町、志村、徳丸一～四丁目", (30, 31, 25), (6, 5, 8)),
            ("泉町、大原町、上板橋三丁目、常盤台、富士見町、南常盤台、宮本町、大門、三園一丁目、四葉", (24, 30, 19), (7, 4, 16)),
            ("上板橋一～二丁目、東新町、新河岸、高島平六～九丁目、三園二丁目", (24, 30, 26), (7, 4, 9)),
            ("板橋、中板橋、氷川町、双葉町、大和町、高島平二～五丁目", (25, 31, 16), (8, 5, 6)),
            ("加賀、仲宿、高島平一丁目", (25, 31, 23), (8, 5, 13)),
            ("仲町、弥生町、赤塚一～二・六～七丁目、赤塚新町", (26, 30, 17), (9, 4, 7)),
            ("大山町、大山金井町、大山東町、熊野町、幸町、栄町、中丸町、南町、成増一丁目", (26, 30, 24), (9, 4, 14)),
        ],
    },
}
DEFAULT_OFF = ("12-31", "01-03")

# 地区の読み（pykakasi では読みちがえる町名。郵便番号一覧の読みで確かめた）
YOMI = {
        "大原町": "おおはらちょう",
        "大谷口": "おおやぐち",
        "大谷口上町": "おおやぐちかみちょう",
        "大谷口北町": "おおやぐちきたちょう",
        "大山金井町": "おおやまかないちょう",
        "大山西町": "おおやまにしちょう",
        "熊野町": "くまのちょう",
        "栄町": "さかえちょう",
        "新河岸": "しんがし",
        "高島平": "たかしまだいら",
        "東新町": "とうしんちょう",
        "中台": "なかだい",
        "中丸町": "なかまるちょう",
        "蓮根": "はすね",
        "東坂下": "ひがしさかした",
        "東山町": "ひがしやまちょう",
        "氷川町": "ひかわちょう",
        "舟渡": "ふなど",
        "前野町": "まえのちょう",
        "南町": "みなみちょう",
        "南常盤台": "みなみときわだい",
        "宮本町": "みやもとちょう"}


def nfkc(s):
    return unicodedata.normalize("NFKC", s).replace("～", "〜").replace("~", "〜").strip()


def parse_rule(cat, text):
    """「水」→ {"w": [2]}、「火・木・土」→ {"w": [1, 3, 5]}、「毎月2回目・4回目の金」→ {"w": [4], "n": [2, 4]}"""
    t = nfkc(text)
    m = re.fullmatch(r"毎月(\d)回目・(\d)回目の([月火水木金土])", t)
    if m:
        return {"w": [WD.index(m[3])], "n": [int(m[1]), int(m[2])]}
    if re.fullmatch(r"[月火水木金土](・[月火水木金土])*", t):
        return {"w": [WD.index(w) for w in t.split("・")]}
    raise ValueError(f"{cat} の曜日が読めません：「{text}」")


def say(rule):
    ws = "・".join(WD[w] for w in rule["w"])
    return f"毎月第{rule['n'][0]}・第{rule['n'][1]}{ws}曜日" if "n" in rule else f"毎週{ws}曜日"


def hits(rule, d):
    return d.weekday() in rule["w"] and ("n" not in rule or (d.day - 1) // 7 + 1 in rule["n"])


def read_table(path):
    """区のページの表 → [{地域, 資源, 可燃ごみ, 不燃ごみ, 事務所, pdf}]"""
    t = Path(path).read_text(encoding="utf-8")
    rows = []
    for tr in re.findall(r"<tr.*?</tr>", t, flags=re.S):
        if "rowspan" in tr or "colspan" in tr:
            raise ValueError("表に結合したセルがあります（読み方を直す）")
        cells = [nfkc(html.unescape(re.sub(r"<[^>]+>", "", c))) for c in re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", tr, flags=re.S)]
        pdf = re.findall(r'href="([^"]*/(\w+)\.pdf)"', tr)
        if len(cells) == 6 and pdf:
            rows.append({"地域": cells[0], "資源": cells[1], "可燃ごみ": cells[2], "不燃ごみ": cells[3], "事務所": cells[4],
                         "pdf": pdf[0][1] + ".pdf", "url": pdf[0][0]})
    if len(rows) < 60:
        raise ValueError(f"表が {len(rows)} 行しか読めません（ページの形がかわった？）")
    return rows


def read_pdf(pdf, year):
    """地域のカレンダー（A4 1ページ。12か月）→ ({日付: 区分}, 2つの日付が1つのマスのもの)"""
    import pymupdf
    page = pymupdf.open(pdf)[0]
    if f"令和{year - 2018}年4月" not in nfkc(page.get_text()).replace(" ", ""):
        raise ValueError(f"{Path(pdf).name} は令和{year - 2018}年度のカレンダーではありません")
    ws = [(w[0], w[1], w[2], w[3], nfkc(w[4])) for w in page.get_text("words")]
    heads = [(w, int(re.match(r"(\d+)月", w[4])[1])) for w in ws if re.fullmatch(r"\d{1,2}月[A-Za-z]*", w[4])]
    if len(heads) != 12:
        raise ValueError(f"{Path(pdf).name}：月の見出しが {len(heads)}")
    cells = []
    for dr in page.get_drawings():
        f, r = dr.get("fill"), dr["rect"]
        if f and 30 < r.width < 45 and 10 < r.height < 20:
            c = COLOR.get(tuple(round(v * 255) for v in f))
            if c:
                cells.append((r, c))
    half = page.rect.width / 2
    out, split = {}, []
    for w in ws:
        if not re.fullmatch(r"\d{1,2}(/\d{1,2})?", w[4]):
            continue
        cx, cy = (w[0] + w[2]) / 2, (w[1] + w[3]) / 2
        above = [(h, mo) for h, mo in heads if (h[0] < half) == (cx < half) and h[1] < cy]
        if not above:
            continue
        h, mo = max(above, key=lambda x: x[0][1])
        if cy - h[1] > 105:          # 見出しの説明の数字など
            continue
        y = year if mo >= 4 else year + 1
        cat = [c for r, c in cells if r.x0 <= cx <= r.x1 and abs((r.y0 + r.y1) / 2 - cy) < 10]     # 「24/31」の文字はマスの下にはみ出す
        days = [dt.date(y, mo, int(n)) for n in w[4].split("/")]
        if "/" in w[4]:
            split.append((days, cat[0] if cat else None))
        elif cat:
            out[days[0].isoformat()] = cat[0]
    if len(out) < 150:
        raise ValueError(f"{Path(pdf).name}：色のついたマスが {len(out)} しか読めません")
    return out, split


def town_chome(s):
    """「西台一～二丁目」「赤塚四～五・八丁目」「赤塚1〜2丁目」→ (町名, {丁目} / None)"""
    s = nfkc(s)
    m = re.match(r"(.+?)([\d一二三四五六七八九・〜]+)丁目$", s)
    if not m:
        return s, None
    spec = "".join(str(KANJI.get(c, c)) for c in m[2])      # 町名の「四葉」の四は変えない
    ch = set()
    for part in spec.split("・"):
        a, _, b = part.partition("〜")
        ch |= set(range(int(a), int(b or a) + 1))
    return m[1], ch


# ---------------- 区のサイトから取ってくる ----------------
def download(year, dest, web, plan):
    raw = web.get(PAGE)
    plan.add(PAGE, dest / "曜日一覧.html", raw)
    seen = set()
    for u, name in re.findall(r'href="([^"]*/(\w+)\.pdf)"', web.text(raw)):
        if u not in seen and re.fullmatch(r"[ew]\d\d", name):
            seen.add(u)
            plan.add(SITE + "/" + re.sub(r"^(\.\./)+", "", u), dest / "カレンダー" / f"{name}.pdf")


# ---------------- 収集日を作る ----------------
def make_calendar(folder, year):
    folder = Path(folder)
    ye = YEAR_END.get(year)
    if ye:
        off, keep, tentative = ye["off"], ye.get("keep", {}), False
    else:
        off, keep, tentative = (f"{year}-{DEFAULT_OFF[0]}", f"{year + 1}-{DEFAULT_OFF[1]}"), {}, True
        print(f"  ！ {year}年度の年末年始がまだ calendar.py の YEAR_END にありません。12/31〜1/3 を休みとして作ります")
    rows = read_table(folder / "曜日一覧.html")
    problems, schedules, areas, pdf_of = [], {}, [], {}
    for r in rows:
        rules = {COLS[k]: parse_rule(k, r[k]) for k in COLS}
        key = "／".join(f"{c}:{say(rules[c])}" for c in CATS)
        if key not in schedules:
            days = {}
            d, end = dt.date(year, 4, 1), dt.date(year + 1, 3, 31)
            while d <= end:
                k = d.isoformat()
                cs = [c for c in CATS if hits(rules[c], d)]
                if off[0] <= k <= off[1]:
                    cs = [c for c in cs if c in keep.get(k, [])]
                if cs:
                    days[k] = cs
                d += dt.timedelta(days=1)
            schedules[key] = {"rules": {c: say(rules[c]) for c in CATS}, "days": days, "moved": {}}
        name = r["地域"]
        town = re.match(r"\D+", name)[0]
        areas.append({"n": name, "s": key, "y": YOMI.get(town) or kana.yomi(town), "d": r["事務所"]})
        pdf_of.setdefault(r["pdf"], set()).add(key)
    # カレンダー PDF と見くらべる（年末年始の 12/29〜1/4 はのぞく）
    checked, nsplit = [], 0
    for name, keys in sorted(pdf_of.items()):
        if len(keys) != 1:
            problems.append(f"{name}：1つのカレンダーに、ちがう曜日の地区がある（{keys}）")
            continue
        pdf = folder / "カレンダー" / name
        if not pdf.exists():
            problems.append(f"{name} がありません")
            continue
        got, split = read_pdf(pdf, year)
        want = schedules[next(iter(keys))]["days"]
        skip = (f"{year}-12-29", f"{year + 1}-01-04")
        two = {d.isoformat() for days, _ in split for d in days}
        for k in sorted(set(got) | set(want)):
            if skip[0] <= k <= skip[1] or k in two:
                continue
            w = want.get(k, [])
            if [got[k]] != w if k in got else w:
                problems.append(f"{name} {k}：カレンダー {got.get(k)}／作った日 {w}")
        for days, c in split:      # 「24/31」のように2つの日が1つのマス：色はどちらかの日の区分
            nsplit += 1
            ws = [want.get(d.isoformat(), []) for d in days]
            if (c is None and any(ws) and all(ws)) or (c is not None and not any(c in w for w in ws)):
                problems.append(f"{name} {days}：カレンダー {c}／作った日 {ws}")
        checked.append(name)
    # 年末年始の表と見くらべる
    nye = 0
    for towns, last, first in (ye or {}).get("table", []):
        keys = [town_chome(t) for t in re.split("、", towns)]
        hit = [a for a in areas if any(tw == town_chome(a["n"])[0] and (ch is None or (town_chome(a["n"])[1] or set()) <= ch) for tw, ch in keys)]
        if not hit:
            problems.append(f"年末年始の表「{towns}」に合う地区がない")
        for a in hit:
            a["_ye"] = a.get("_ye", 0) + 1
            days = schedules[a["s"]]["days"]
            for i, c in enumerate(CATS):
                l = max(k for k, v in days.items() if c in v and k < f"{year + 1}-01-01")
                f = min(k for k, v in days.items() if c in v and k > f"{year}-12-31")
                if (int(l[8:]), int(f[8:])) != (last[i], first[i]) or l[5:7] != "12" or f[5:7] != "01":
                    problems.append(f"年末年始 {a['n']} {c}：表 12/{last[i]}・1/{first[i]}／作った日 {l}・{f}")
            nye += 1
    if ye and ye.get("table"):
        miss = [a["n"] for a in areas if a.get("_ye") != 1]
        if miss:
            problems.append(f"年末年始の表で地区が決まらない（または2つある）：{miss}")
    for a in areas:
        a.pop("_ye", None)
    print(f"板橋区：地区 {len(areas)}・収集日の組み合わせ {len(schedules)}・見くらべたカレンダー {len(checked)}枚"
          f"（2つの日が1つのマス {nsplit}）・年末年始の表で見くらべた地区 {nye}")
    if problems:
        for p in problems[:40]:
            print("  ！", p)
        raise ValueError(f"区のカレンダーと合わないところが {len(problems)} あります")
    return {"year": year, "schedules": schedules, "areas": areas,
            "yearEnd": {"off": list(off), "tentative": tentative}}
