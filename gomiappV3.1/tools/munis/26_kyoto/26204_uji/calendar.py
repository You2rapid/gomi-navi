"""京都府 宇治市（26204）：「ごみ収集カレンダー」（地区ごとの PDF）から収集日を作る。

このファイルのきまり（どの自治体も同じ形。tools/update_year.py・download_sources.py から使う）:
  NEED                       … 元データ/<県>/<自治体>/<年度>年度/ に置くファイルの名前
  download(year, dest, web, plan) … 市のサイトから NEED のファイルを探して plan に入れる（web は tools/lib/web.py）
  make_calendar(src, year)   … src（上のフォルダ）のファイルから収集日データ（dict）を作る。読めなければ例外で止める

宇治市は、市を11の「地区」（1・2・3・5・6・8・10・11・12・13・15。4・7・9・14 は欠番）に分け、
地区ごとに「ごみ収集カレンダー」（A4横2ページ。4〜9月・10〜3月）の PDF を出している。
カレンダーの PDF は文字が入っているので、日付の数字と、その下の札（もえる・もえない・ﾌﾟﾗ資源・缶・びん・ﾍﾟｯﾄﾎﾞﾄﾙ）の位置から、
どの日に何を出すかを読む（札は、同じ月・同じ曜日の列で、すぐ上にある日付のもの）。
祝日も収集する。年末（12月28日〜31日）は、カレンダーでは空いていて「12月15日号の市政だより・ホームページ等でお知らせします」とある。
市の発表が出たら YEAR_END に足す（それまでは、その日は収集なし・yearEnd の tentative を True にする）。

地区に入る町（大字・小字）は、市の「ごみ収集カレンダー」のページ（ごみ収集カレンダー.html）の「収集地区検索表」。

フォルダ（元データ/26_京都府/26204_宇治市/<年度>年度/）に置くもの:
  ごみ収集カレンダー.html  … 「「○○年度ごみ収集日程」が分かるごみ収集カレンダーを作成しました。」のページ（収集地区検索表がある）
  カレンダー_<n>地区.pdf   … 地区ごとのページの「○○年度ごみ収集カレンダー<n>地区」
  ごみ収集日程表.pdf       … 市内全地域の日程表（1枚。見くらべ用で、calendar.py では使わない）
"""
import datetime as dt
import html as H
import re
import unicodedata
from pathlib import Path

import pymupdf

SITE = "https://www.city.uji.kyoto.jp"
LIST = SITE + "/site/gomi/list24-40.html"     # 「ごみ収集日程、ごみカレンダー」の一覧
DISTRICTS = [1, 2, 3, 5, 6, 8, 10, 11, 12, 13, 15]
NEED = ["ごみ収集カレンダー.html"] + [f"カレンダー_{n}地区.pdf" for n in DISTRICTS]

# カレンダーの札 → アプリの区分（city.js の cats）
# 1つのマスに2つの札がまとめて書かれていることがある（「缶・びん」「びん・ﾍﾟｯﾄ」）ので、「・」で分けて読む
LABEL = {"もえる": "もえる", "もえない": "もえない", "ﾌﾟﾗ資源": "プラ", "缶": "缶", "びん": "びん", "ﾍﾟｯﾄﾎﾞﾄﾙ": "ペット", "ﾍﾟｯﾄ": "ペット"}
ORDER = ["もえる", "もえない", "プラ", "缶", "びん", "ペット"]


def label_cats(word):
    parts = word.split("・")
    return [LABEL[p] for p in parts] if all(p in LABEL for p in parts) else None
WD = "月火水木金土日"      # Python の weekday() の順
WDH = "日月火水木金土"     # カレンダーの列の順

# 年末（12月28日〜31日）の収集。市が12月15日号の市政だより・ホームページで発表したら、ここに足す。
#   {年度: {"off": ("休みのはじめ", "休みのおわり"), "add": {"2026-12-28": {"1地区": ["もえる"], …}, …}}}
#   "add" は、休みの期間の中で収集する日（地区ごと。全地区なら "*"）
YEAR_END = {}

# 大字の読み（地区の読みに使う。検索だけに使う）
YOMI = {
    "六地蔵": "ろくじぞう", "木幡": "こはた", "平尾台": "ひらおだい", "五ケ庄": "ごかしょう", "宇治": "うじ", "羽戸山": "はとやま",
    "明星町": "みょうじょうちょう", "志津川": "しづかわ", "莵道": "とどう", "折居台": "おりいだい", "白川": "しらかわ", "神明": "しんめい",
    "広野町": "ひろのちょう", "大久保町": "おおくぼちょう", "寺山台": "てらやまだい", "槇島町": "まきしまちょう", "琵琶台": "びわだい",
    "小倉町": "おぐらちょう", "南陵町": "なんりょうちょう", "羽拍子町": "はびょうしちょう", "開町": "ひらきまち", "伊勢田町": "いせだちょう",
    "天神台": "てんじんだい", "安田町": "やすだちょう", "炭山": "すみやま", "東笠取": "ひがしかさとり", "西笠取": "にしかさとり",
    "二尾": "にお", "池尾": "いけのお",
}


def clean(t):
    return re.sub(r"[\s　]+", "", unicodedata.normalize("NFKC", t))


# ---------- 収集地区検索表（地区 → 大字・小字） ----------
def read_districts(path):
    """ごみ収集カレンダーのページの「収集地区検索表」→ {地区番号: [(大字, 小字の書き方), …]}（市の書き方のまま）。
    表は「地区｜大字｜小字（地域）」で、大字・小字のマスは何行かにまたがる（rowspan）"""
    s = Path(path).read_text(encoding="utf-8", errors="replace")
    i = s.find("収集地区検索表")
    if i < 0:
        raise ValueError(f"{path} に「収集地区検索表」がありません")
    s = s[i:s.find("</table>", i)]
    out, dist, oaza, koaza = {}, None, None, None     # 前の行のマスが続いているときは、前の値のまま
    for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", s, re.S):
        for attr, c in re.findall(r"<t[dh]([^>]*)>(.*?)</t[dh]>", tr, re.S):
            t = H.unescape(re.sub(r"<[^>]+>", "", c)).strip()
            w = (re.search(r"width:(\d+)%", attr) or [0, ""])[1]
            if w == "6":
                m = re.match(r"[(（](\d+)[)）]", clean(t))
                dist = int(m[1]) if m else None
            elif w == "10":
                oaza = clean(t)
            elif w == "57":
                koaza = clean(t)
        if dist and oaza and koaza and koaza != "欠番":
            out.setdefault(dist, []).append((oaza, koaza))
    # 小字のマスが何行かにまたがり、大字だけが行ごとに変わる所（15地区：炭山・東笠取…「全域」）を直す
    fixed = {}
    for d, rows in out.items():
        seen = []
        for o, k in rows:
            if (o, k) not in seen:
                seen.append((o, k))
        fixed[d] = seen
    if sorted(fixed) != DISTRICTS:
        raise ValueError(f"収集地区検索表の地区が {sorted(fixed)} です（{DISTRICTS} のはず）")
    return fixed


def district_text(rows):
    """[(大字, 小字), …] → 「六地蔵（ＪＲ以北）、木幡（赤塚、…）、平尾台」（同じ大字は1つにまとめる）"""
    by = {}
    for o, k in rows:
        by.setdefault(o, []).append(k.rstrip("、"))
    parts = []
    for o, ks in by.items():
        if ks == ["全域"]:
            parts.append(o)
        else:
            parts.append(f"{o}（{'、'.join(ks)}）")
    return "、".join(parts)


# ---------- カレンダー PDF ----------
def read_pdf(path, year):
    """地区のカレンダー PDF → {日付: [区分, …]}"""
    doc = pymupdf.open(path)
    days = {}
    months_seen = set()
    for page in doc:
        ws = page.get_text("words")
        heads = []      # 月の見出し (x, y, 月)
        for w in ws:
            m = re.fullmatch(r"(\d+)月", clean(w[4]))
            if m and 1 <= int(m[1]) <= 12:
                heads.append(((w[0] + w[2]) / 2, w[1], int(m[1])))
        if len(heads) != 6:
            raise ValueError(f"{path}：月の見出しが {len(heads)} こです（6こあるはず）")
        cols = [((w[0] + w[2]) / 2, w[1], w[4]) for w in ws if w[4] in WDH and len(w[4]) == 1]
        nums = [((w[0] + w[2]) / 2, w[1], int(w[4])) for w in ws if re.fullmatch(r"\d{1,2}", w[4])]
        labels = [((w[0] + w[2]) / 2, w[1], w[4]) for w in ws if label_cats(w[4])]

        def block(x, y):
            hs = [h for h in heads if h[1] < y]
            top = max(h[1] for h in hs)
            return min((h for h in hs if abs(h[1] - top) < 5), key=lambda h: abs(h[0] - x))

        def column(x, y, hd):
            cs = [c for c in cols if 0 < c[1] - hd[1] < 25]
            c = min(cs, key=lambda c: abs(c[0] - x))
            if abs(c[0] - x) > 20:
                raise ValueError(f"{path}：{hd[2]}月の札（x={x:.0f}）の列が分かりません")
            return c

        for x, y, lab in labels:
            hd = block(x, y)
            col = column(x, y, hd)
            cand = [n for n in nums if abs(n[0] - col[0]) < 20 and 0 < y - n[1] < 60 and block(n[0], n[1]) == hd]
            if not cand:
                raise ValueError(f"{path}：{hd[2]}月の「{lab}」の日付が見つかりません")
            n = max(cand, key=lambda n: n[1])
            mo = hd[2]
            d = dt.date(year if mo >= 4 else year + 1, mo, n[2])
            if WDH[(d.weekday() + 1) % 7] != col[2]:
                raise ValueError(f"{path}：{d} の曜日が、カレンダーの列（{col[2]}）と合いません")
            for cat in label_cats(lab):
                days.setdefault(d.isoformat(), [])
                if cat not in days[d.isoformat()]:
                    days[d.isoformat()].append(cat)
            months_seen.add(mo)
    if len(months_seen) != 12:
        raise ValueError(f"{path}：札のある月が {sorted(months_seen)} だけです")
    return {k: sorted(v, key=ORDER.index) for k, v in sorted(days.items())}


def rule_text(days, cat):
    """収集日の決まりを文にする（例：毎週月・木曜日、第1・第3水曜日、隔週火曜日）"""
    ds = [dt.date.fromisoformat(k) for k, v in days.items() if cat in v]
    wds = sorted({d.weekday() for d in ds})
    w = "・".join(WD[i] for i in wds)
    weeks = {(d - dt.timedelta(days=d.weekday())) for d in ds}
    if len(weeks) > 45 and len(ds) >= len(weeks) * len(wds) - 6:
        return f"毎週{w}曜日"
    nth = sorted({(d.day - 1) // 7 + 1 for d in ds})
    if len(nth) <= 3 and len(ds) >= 12 * len(nth) - 3:
        return f"第{'・第'.join(map(str, nth))}{w}曜日"
    return f"隔週{w}曜日（月2回）" if len(ds) > 15 else f"月1回（{w}曜日）"


# ---------- ダウンロード ----------
def download(year, dest, web, plan):
    dest = Path(dest)
    page = web.text(web.get(LIST))
    title = f"{year}年度"
    found = 0
    for u, label in web.links(page, LIST):
        lab = clean(label)
        m = re.search(rf"「{year}年度」ごみ収集カレンダー[(（](\d+)地区", lab)
        if m:
            sub = web.text(web.get(u))
            pdf = next((p for p, l in web.links(sub, u) if p.endswith(".pdf") and f"{m[1]}地区" in clean(l)), None)
            if pdf:
                plan.add(pdf, dest / f"カレンダー_{m[1]}地区.pdf")
                found += 1
            else:
                plan.problem(f"{u} に {m[1]}地区のカレンダー PDF がありません")
        elif title in lab and "ごみ収集日程" in lab and "カレンダーを作成" in lab:
            raw = web.get(u)
            plan.add(u, dest / "ごみ収集カレンダー.html", raw)
            pdf = next((p for p, l in web.links(web.text(raw), u) if p.endswith(".pdf") and "ごみ収集日程表" in clean(l)), None)
            if pdf:
                plan.add(pdf, dest / "ごみ収集日程表.pdf")
    if found != len(DISTRICTS):
        plan.problem(f"「{title}」ごみ収集カレンダー（○地区）が {found} 地区分しか見つかりません（{LIST}。例年2月末ごろに出る）")


# ---------- 収集日を作る ----------
def make_calendar(folder, year):
    folder = Path(folder)
    dists = read_districts(folder / "ごみ収集カレンダー.html")
    ye = YEAR_END.get(year)
    tentative = ye is None
    off = (dt.date(year, 12, 28), dt.date(year + 1, 1, 3)) if tentative else tuple(dt.date.fromisoformat(x) for x in ye["off"])
    if tentative:
        print(f"  ！ {year}年度の年末の収集日（12月28日〜31日）がまだ YEAR_END にありません。カレンダーのとおり収集なしで作ります（市の発表が出たら足す）")
    schedules, areas = {}, []
    for n in DISTRICTS:
        name = f"{n}地区"
        days = read_pdf(folder / f"カレンダー_{n}地区.pdf", year)
        bad = [k for k in days if off[0] <= dt.date.fromisoformat(k) <= off[1]]
        if bad and tentative:
            raise ValueError(f"{name}：年末年始の休み（{off[0]}〜{off[1]}）に収集日があります：{bad}（YEAR_END を足す）")
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
        rows = dists[n]
        oazas = []
        for o, _ in rows:
            if o not in oazas:
                oazas.append(o)
        areas.append({"n": name, "s": name, "y": " ".join(YOMI[o] for o in oazas), "d": district_text(rows)})
        print(f"  {name}：{len(days)}日  " + "、".join(f"{c} {r}" for c, r in rules.items()))
    print(f"宇治市：地区 {len(areas)}・日程 {len(schedules)}")
    return {"year": year, "schedules": schedules, "areas": areas,
            "yearEnd": {"off": [off[0].isoformat(), off[1].isoformat()], "tentative": tentative}}
