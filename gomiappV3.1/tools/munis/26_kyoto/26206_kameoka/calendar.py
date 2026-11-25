"""京都府 亀岡市（26206）：「ごみ出しカレンダー」（町ごとの PDF）から収集日を作る。

このファイルのきまり（どの自治体も同じ形。tools/update_year.py・download_sources.py から使う）:
  NEED                       … 元データ/<県>/<自治体>/<年度>年度/ に置くファイルの名前
  download(year, dest, web, plan) … 市のサイトから NEED のファイルを探して plan に入れる（web は tools/lib/web.py）
  make_calendar(src, year)   … src（上のフォルダ）のファイルから収集日データ（dict）を作る。読めなければ例外で止める

亀岡市は、市を24の「町」（旭町・馬路町…。亀岡地区は東部・中部・西部、篠町はⅠ・Ⅱに分ける）に分け、
町ごとに「亀岡市ごみ出しカレンダー」（A4たて6ページ。1ページに2か月）の PDF を出している（同じ日程の町は同じ PDF）。
カレンダーの PDF は文字が入っているので、日付の数字と、その下の札（燃やすしかないごみ・埋立てるしかないごみ・プラスチック…）の位置から読む。
札は、同じ月の中で、すぐ上の日付の行のうち、横の位置がいちばん近い日付のもの（札はマスの真ん中、日付もマスの真ん中にある）。
読んだ日付の曜日が、いちばん近い曜日の見出しと合わなければ止まる。12か月すべてに札がなければ止まる。
白い文字（月の終わりのあとのマスに、見えない数字と札がある）は読まない。
祝日もふだんどおり収集する（カレンダーのとおり）。
年末年始（12月30日〜1月3日）はカレンダーで空いているが、市のページに「年末年始の収集については、収集日程を変更する場合がありますので、
市のホームページや広報誌にて改めてお知らせいたします」とあるので、yearEnd の tentative を True にしている。
市のお知らせが出たら YEAR_END に足す（変更がなければ "add" を空にして足す）。

地区に入る町は、カレンダーのページ（ごみ出しカレンダー.html）の町の名前と、亀岡地区・篠町の町名の表。

フォルダ（元データ/26_京都府/26206_亀岡市/<年度>年度/）に置くもの:
  ごみ出しカレンダー.html  … 「令和○年度ごみ出しカレンダーを掲載します」のページ（町の名前と PDF へのリンク、亀岡地区・篠町の町名の表）
  カレンダー_<町>.pdf      … 町ごとの「亀岡市ごみ出しカレンダー」
  町別収集日程.pdf         … 「各町別のごみの収集日の確認はこちら」（見くらべ用で、calendar.py では使わない）
"""
import datetime as dt
import html as H
import re
import unicodedata
from pathlib import Path

import pymupdf

SITE = "https://www.city.kameoka.kyoto.jp"
LIST = SITE + "/life/1/6/23/"       # 「ごみ・リサイクル」の一覧

# 地区（カレンダーのページの順）と読み
AREAS = [
    ("旭町", "あさひちょう"), ("馬路町", "うまじちょう"), ("千歳町", "ちとせちょう"), ("河原林町", "かわらばやしちょう"),
    ("保津町", "ほづちょう"), ("千代川町", "ちよかわちょう"), ("大井町", "おおいちょう"),
    ("亀岡地区東部", "かめおかちく とうぶ"), ("亀岡地区中部", "かめおかちく ちゅうぶ"), ("亀岡地区西部", "かめおかちく せいぶ"),
    ("篠町Ⅰ", "しのちょう いち"), ("篠町Ⅱ", "しのちょう に"),
    ("東つつじケ丘", "ひがしつつじがおか"), ("西つつじケ丘", "にしつつじがおか"), ("南つつじケ丘", "みなみつつじがおか"),
    ("東本梅町", "ひがしほんめちょう"), ("本梅町", "ほんめちょう"), ("宮前町", "みやざきちょう"), ("畑野町", "はたのちょう"),
    ("吉川町", "よしかわちょう"), ("薭田野町", "ひえだのちょう"), ("曽我部町", "そがべちょう"),
    ("東別院町", "ひがしべついんちょう"), ("西別院町", "にしべついんちょう"),
]
NAMES = [a for a, _ in AREAS]
NEED = ["ごみ出しカレンダー.html"] + [f"カレンダー_{a}.pdf" for a in NAMES]

# カレンダーの札 → アプリの区分（city.js の cats）
LABEL = {
    "燃やすしかないごみ": "燃やす", "埋立てるしかないごみ": "埋立", "プラスチック": "プラ", "紙類": "紙類", "草・木類": "草木",
    "ペットボトル": "ペット", "空きカン・空きビン": "カンビン", "スプレー缶・小型金属類": "金属", "乾電池・ライター": "電池",
}
ORDER = ["燃やす", "埋立", "プラ", "紙類", "草木", "ペット", "カンビン", "金属", "電池"]
WD = "月火水木金土日"      # Python の weekday() の順
WDH = "日月火水木金土"     # カレンダーの列の順

# 年末年始の収集。市がホームページ・広報誌で知らせたら、ここに足す。
#   {年度: {"off": ("休みのはじめ", "休みのおわり"), "add": {"2026-12-30": {"旭町": ["燃やす"], …}, …}}}
#   "add" は、休みの期間の中で収集する日（地区ごと。全地区なら "*"）。カレンダーのとおりなら "add" は {}
YEAR_END = {}
OFF = ((12, 30), (1, 3))       # カレンダーで空いている期間（2026年度のカレンダーで、どの町も12月30日〜1月3日に札がない）


def clean(t):
    return re.sub(r"[\s　]+", "", unicodedata.normalize("NFKC", t))


# ---------- カレンダーのページ（地区の町名） ----------
def read_page(path):
    """ごみ出しカレンダーのページ → ({地区: PDF の URL}, {地区: 町名の説明})"""
    s = Path(path).read_text(encoding="utf-8", errors="replace")
    pdfs = {}
    for href, label in re.findall(r'<a[^>]*href="([^"]+\.pdf)"[^>]*>(.*?)</a>', s, re.S):
        lab = clean(H.unescape(re.sub(r"<[^>]+>", "", label)))
        lab = re.sub(r"\[PDF.*$", "", lab)
        for a in NAMES:
            if clean(a) == lab:
                pdfs.setdefault(a, href if href.startswith("http") else SITE + href)
    desc = {}
    text = H.unescape(re.sub(r"<[^>]+>", "\n", s))
    lines = [clean(x) for x in text.split("\n") if clean(x)]
    split = {clean(a): a for a in ("亀岡地区東部", "亀岡地区中部", "亀岡地区西部", "篠町Ⅰ", "篠町Ⅱ")}   # clean で「Ⅰ」は「I」になる
    for i, ln in enumerate(lines[:-1]):
        if ln in split and lines[i + 1] not in split and "PDF" not in lines[i + 1] and "、" in lines[i + 1]:
            desc.setdefault(split[ln], lines[i + 1].replace(",", "、").replace("(", "（").replace(")", "）").replace("~", "〜"))
    return pdfs, desc


# ---------- カレンダー PDF ----------
def read_pdf(path, year):
    """町のカレンダー PDF → {日付: [区分, …]}"""
    doc = pymupdf.open(path)
    days = {}
    months_seen = set()
    for page in doc:
        spans = []
        for b in page.get_text("dict")["blocks"]:
            for ln in b.get("lines", []):
                for sp in ln["spans"]:
                    t = clean(sp["text"])
                    if t:
                        x0, y0, x1, y1 = sp["bbox"]
                        spans.append(((x0 + x1) / 2, y0, t, sp["color"]))
        heads = []      # 月の見出し (y, 月)
        for x, y, t, c in spans:
            m = re.fullmatch(r"令和(\d+)年(\d+)月", t)
            if m:
                heads.append((y, int(m[2])))
        if len(heads) != 2:
            raise ValueError(f"{path}：月の見出しが {len(heads)} こです（2こあるはず）")
        heads.sort()
        cols = [(x, y, t) for x, y, t, c in spans if len(t) == 1 and t in WDH]
        nums = [(x, y, int(t)) for x, y, t, c in spans if re.fullmatch(r"\d{1,2}", t) and c != 0xFFFFFF]
        labels = [(x, y, t) for x, y, t, c in spans if t in LABEL and c != 0xFFFFFF]

        def block(y):
            hs = [h for h in heads if h[0] < y]
            return max(hs) if hs else None

        for x, y, lab in labels:
            hd = block(y)
            if not hd:
                raise ValueError(f"{path}：「{lab}」（y={y:.0f}）の月が分かりません")
            row = [n for n in nums if block(n[1]) == hd and 0 < y - n[1] < 48]   # マスの高さは約50。札が4つ重なると、いちばん下は日付から42ほど下
            if not row:
                raise ValueError(f"{path}：{hd[1]}月の「{lab}」の日付が見つかりません")
            top = max(n[1] for n in row)
            row = [n for n in row if abs(n[1] - top) < 3]
            n = min(row, key=lambda n: abs(n[0] - x))
            if abs(n[0] - x) > 30:
                raise ValueError(f"{path}：{hd[1]}月の「{lab}」（x={x:.0f}）の日付が分かりません")
            col = min((c for c in cols if block(c[1]) == hd), key=lambda c: abs(c[0] - n[0]))
            mo = hd[1]
            d = dt.date(year if mo >= 4 else year + 1, mo, n[2])
            if WDH[(d.weekday() + 1) % 7] != col[2]:
                raise ValueError(f"{path}：{d} の曜日が、カレンダーの列（{col[2]}）と合いません")
            cat = LABEL[lab]
            days.setdefault(d.isoformat(), [])
            if cat not in days[d.isoformat()]:
                days[d.isoformat()].append(cat)
            months_seen.add(mo)
    if len(months_seen) != 12:
        raise ValueError(f"{path}：札のある月が {sorted(months_seen)} だけです")
    return {k: sorted(v, key=ORDER.index) for k, v in sorted(days.items())}


def rule_text(days, cat):
    """収集日の決まりを文にする（例：毎週火・金曜日、第2・第4水曜日、第3水曜日）"""
    ds = [dt.date.fromisoformat(k) for k, v in days.items() if cat in v]
    wds = sorted({d.weekday() for d in ds})
    w = "・".join(WD[i] for i in wds)
    weeks = {(d - dt.timedelta(days=d.weekday())) for d in ds}
    if len(weeks) > 45 and len(ds) >= len(weeks) * len(wds) - 6:
        return f"毎週{w}曜日"
    if len(wds) == 1:
        nth = sorted({(d.day - 1) // 7 + 1 for d in ds})
        if len(nth) <= 3:
            return f"第{'・第'.join(map(str, nth))}{w}曜日"
    return f"月{round(len(ds) / 12)}回（{w}曜日）"


# ---------- ダウンロード ----------
def reiwa(year):
    return year - 2018


def download(year, dest, web, plan):
    dest = Path(dest)
    page = web.text(web.get(LIST))
    title = f"令和{reiwa(year)}年度ごみ出しカレンダー"
    url = next((u for u, label in web.links(page, LIST) if title in clean(label)), None)
    if not url:
        plan.problem(f"「{title}を掲載します」のページが見つかりません（{LIST}。例年3月1日ごろに出る）")
        return
    raw = web.get(url)
    plan.add(url, dest / "ごみ出しカレンダー.html", raw)
    found = 0
    for u, label in web.links(web.text(raw), url):
        lab = re.sub(r"\[PDF.*$", "", clean(label))
        if u.endswith(".pdf") and lab in [clean(a) for a in NAMES]:
            a = next(a for a in NAMES if clean(a) == lab)
            plan.add(u, dest / f"カレンダー_{a}.pdf")
            found += 1
        elif u.endswith(".pdf") and lab == "こちら":
            plan.add(u, dest / "町別収集日程.pdf")
    if found != len(NAMES):
        plan.problem(f"{url} に町のカレンダーが {found} こしかありません（{len(NAMES)} こあるはず）")


# ---------- 収集日を作る ----------
def make_calendar(folder, year):
    folder = Path(folder)
    _, desc = read_page(folder / "ごみ出しカレンダー.html")
    ye = YEAR_END.get(year)
    tentative = ye is None
    if tentative:
        off = (dt.date(year, *OFF[0]), dt.date(year + 1, *OFF[1]))
        print(f"  ！ {year}年度の年末年始（{off[0]}〜{off[1]}）は、カレンダーのとおり収集なしで作ります（市のお知らせが出たら YEAR_END に足す）")
    else:
        off = tuple(dt.date.fromisoformat(x) for x in ye["off"])
    schedules, areas = {}, []
    for name, yomi in AREAS:
        days = read_pdf(folder / f"カレンダー_{name}.pdf", year)
        bad = [k for k in days if off[0] <= dt.date.fromisoformat(k) <= off[1]]
        if bad and tentative:
            raise ValueError(f"{name}：年末年始の休み（{off[0]}〜{off[1]}）に収集日があります：{bad}（OFF を直す）")
        if ye:
            for k, by in ye.get("add", {}).items():
                cs = by.get(name, by.get("*", []))
                if cs:
                    days[k] = sorted(set(days.get(k, [])) | set(cs), key=ORDER.index)
        cats = []
        for v in days.values():
            cats += [c for c in v if c not in cats]
        rules = {c: rule_text(days, c) for c in ORDER if c in cats}
        schedules[name] = {"rules": rules, "days": dict(sorted(days.items())), "moved": {}}
        areas.append({"n": name, "s": name, "y": yomi, "d": desc.get(name, "")})
        print(f"  {name}：{len(days)}日  " + "、".join(f"{c} {r}" for c, r in rules.items()))
    for a in ("亀岡地区東部", "亀岡地区中部", "亀岡地区西部", "篠町Ⅰ", "篠町Ⅱ"):
        if a not in desc:
            raise ValueError(f"ごみ出しカレンダー.html に「{a}」の町名がありません")
    print(f"亀岡市：地区 {len(areas)}・日程 {len(schedules)}")
    return {"year": year, "schedules": schedules, "areas": areas,
            "yearEnd": {"off": [off[0].isoformat(), off[1].isoformat()], "tentative": tentative}}
