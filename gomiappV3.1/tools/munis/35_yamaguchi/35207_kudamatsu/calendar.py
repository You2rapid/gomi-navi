"""山口県 下松市（35207）：オープンデータ「【下松市】ゴミ収集カレンダー」（CSV）から収集日データを作り、
市のサイトの「家庭ごみ収集カレンダー（A4・月ごと）」PDF と見くらべて確かめる。

このファイルのきまり（どの自治体も同じ形。tools/update_year.py・download_sources.py から使う）:
  NEED                       … 元データ/<県>/<自治体>/<年度>年度/ に置くファイルの名前
  download(year, dest, web, plan) … 市のサイトから NEED のファイルを探して plan に入れる（web は tools/lib/web.py）
  make_calendar(src, year)   … src（上のフォルダ）のファイルから収集日データ（dict）を作る。読めなければ例外で止める

フォルダには、山口県オープンデータカタログサイトの「【下松市】ゴミ収集カレンダー（○○○○年度）」の CSV を opendata.csv、
市のサイトからダウンロードした「A4・月ごと」のカレンダーを
nishi.pdf（西地区。令和8年度は r8nishia4.pdf）・higashi.pdf（東地区。r8higashia4.pdf）の名前で置く。
収集日は CSV（CC BY 4.0）から作る。CSV と PDF で違う日があれば一覧に出し、その日は PDF（市が配っているカレンダー）に合わせる
（令和8年度は、CSV に東地区の 8/31 の燃やす袋ごみが抜けていた）。
PDF の文字は図形（アウトライン）になっているので、文字の図形の「色」と「点の数」から
ごみの種類を見分ける。見分けられない図形があれば標準エラーに出す。
"""
import calendar, csv, datetime as dt, io, json, re, sys
from collections import Counter, defaultdict
from pathlib import Path
import pymupdf

FILES = {"西地区": "nishi.pdf", "東地区": "higashi.pdf"}
CSV = "opendata.csv"
NEED = [CSV] + list(FILES.values())
PAGE = "https://www.city.kudamatsu.lg.jp/kankyou/seikatsu/kankyou/kannrikakari/gomikarenda.html"
DATASET = "https://yamaguchi-opendata.jp/ckan/dataset/352071_garbage_collection_cal"
# オープンデータの収集区分 → アプリの区分（「収集なし」は使わない）
CSV_CATS = {"燃やす袋ごみ": "燃やす", "可燃系資源": "可燃資源", "プラスチック製容器包装": "容プラ", "その他プラスチック類": "他プラ",
            "ペットボトル": "ペット", "びん・かん類": "びん缶", "金属類": "金属", "小型家電品": "小型家電", "埋立ごみ": "埋立",
            "大型不燃ごみ": "大型不燃", "大型可燃ごみ": "大型可燃", "有害ごみ": "有害"}
YEAR = 2026   # 実行するときに年度で上書きする
COLS = [51, 107, 233, 360, 487, 612, 740, 794]   # 日〜土 の列の境目
ROW_TOP, ROW_H = 162, 71.3                         # 1週目の上端と週の高さ
BLACK, RED, BLUE, WHITE = (0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 0.0, 1.0), (1.0, 1.0, 1.0)
# (塗り色, 図形の点の数) → 区分
SIG = {
    (RED, 204): "燃やす",      # 燃やす袋
    (BLACK, 245): "可燃資源",  # 可燃系資源
    (BLACK, 233): "容プラ",    # プラ容器包装
    (BLACK, 135): "他プラ",    # その他プラ
    (BLACK, 105): "ペット",    # ペットボトル
    (BLACK, 179): "金属",      # 金属類
    (BLACK, 117): "びん缶",    # びん・かん
    (BLACK, 205): "小型家電",  # 小型家電品
    (BLACK, 128): "埋立",      # 埋立ごみ
    (BLUE, 94): "大型不燃",    # 大型「不燃」ごみ
    (RED, 102): "大型可燃",    # 大型「可燃」ごみ
    (BLACK, 85): "有害",       # 有害ごみ
    (WHITE, 135): "なし",      # 収集なし
}
IGNORE = {(BLACK, 54), (RED, 54), (BLACK, 76), (BLACK, 69), (WHITE, 1), ((0.5, 0.5, 0.5), 1), ((0.5, 0.5, 0.5), 2)}

def col(x):
    for i in range(7):
        if COLS[i] <= x < COLS[i + 1]:
            return i

def month_pages():
    for i in range(12):
        y, m = (YEAR, 4 + i) if i < 9 else (YEAR + 1, i - 8)
        yield i, y, m

def extract(pdf):
    days = defaultdict(set)
    doc = pymupdf.open(pdf)
    for pi, y, m in month_pages():
        p = doc[pi]
        dr = [x for x in p.get_drawings() if x["type"] == "f" and x.get("fill")]
        first = dt.date(y, m, 1)
        wd = (first.weekday() + 1) % 7  # 日曜=0
        # 1週目の日曜の数字が灰色なら前の月から始まる。赤なら今月の最初の日曜から始まる
        sun0 = [x for x in dr if x["rect"].x0 < 70 and 163 <= x["rect"].y0 < 185 and x["rect"].height < 17]
        gray = any(tuple(round(v, 2) for v in x["fill"]) == (0.75, 0.75, 0.75) for x in sun0)
        start = first - dt.timedelta(days=wd) if (gray or wd == 0) else first + dt.timedelta(days=7 - wd)
        cells = defaultdict(list)
        for x in dr:
            r = x["rect"]
            if r.y0 < ROW_TOP or r.width > 300:
                continue
            ri = int((r.y0 - ROW_TOP) // ROW_H)
            if r.y0 < ROW_TOP + ri * ROW_H + 19:   # 日付の数字や祝日名・届出制の札
                continue
            k = (tuple(round(v, 2) for v in x["fill"]), len(x["items"]))
            c = col((r.x0 + r.x1) / 2)
            if k in SIG:
                cells[(ri, c)].append(SIG[k])
            elif k not in IGNORE:
                print(f"? {pdf.name} {y}-{m} row{ri} col{c} {k} {[round(v) for v in r]}", file=sys.stderr)
        for (ri, c), cats in cells.items():
            d = start + dt.timedelta(days=7 * ri + c)
            if (d.year, d.month) != (y, m):
                print(f"! {pdf.name} {y}-{m} cell row{ri} col{c} -> {d} {cats}", file=sys.stderr)
                continue
            for cat in cats:
                if cat != "なし":
                    days[d.isoformat()].add(cat)
    return days

ORDER = ["燃やす", "可燃資源", "容プラ", "他プラ", "ペット", "びん缶", "金属", "小型家電", "埋立", "大型不燃", "大型可燃", "有害"]
WD = "日月火水木金土"

def rules(days):
    # 区分ごとに「毎週◯曜日」「毎月第◯◯曜日」の形にまとめる
    occ = defaultdict(list)
    for k, cats in days.items():
        d = dt.date.fromisoformat(k)
        for c in cats:
            occ[c].append(d)
    out = {}
    for c in ORDER:
        ds = occ.get(c)
        if not ds:
            continue
        wds = Counter((d.weekday() + 1) % 7 for d in ds)
        main = [w for w, n in wds.items() if n >= len(ds) * 0.15]
        nth = Counter((d.day - 1) // 7 + 1 for d in ds)
        months = len({(d.year, d.month) for d in ds})
        wtxt = "・".join(WD[w] for w in sorted(wds))
        if len(ds) >= 40 and len(wds) <= 2:
            out[c] = f"毎週{wtxt}曜日"
        elif len(wds) == 1 and len(nth) <= 2 and all(n >= 9 for n in nth.values()):
            out[c] = f"毎月第{'・'.join(map(str, sorted(nth)))}{wtxt}曜日"
        else:
            per = len(ds) / months
            n = f"年{len(ds)}回" if len(ds) <= 6 else "月1〜2回" if 1.2 <= per < 1.8 else f"月{round(per)}回"
            out[c] = f"{n} {wtxt}曜日" if len(wds) == 1 else f"{n}（日はカレンダーで確認）"
    return out

def download(year, dest, web, plan):
    # オープンデータの CSV（「【下松市】ゴミ収集カレンダー（2026年度）」のように、名前に年度が入っている）
    import opendata
    res = [r for r in opendata.info(DATASET, web)["resources"] if r["format"] == "CSV" and f"{year}年度" in r["name"]]
    if res:
        plan.add(res[0]["url"], dest / CSV)
    else:
        plan.problem(f"オープンデータに {year}年度 の CSV がまだありません（{DATASET}）")
    # 見くらべる用の「A4・月ごと」の版：r○nishia4.pdf / r○higashia4.pdf（○は令和の年）
    reiwa = year - 2018
    page = web.text(web.get(PAGE))
    for key, fn in (("nishi", "nishi.pdf"), ("higashi", "higashi.pdf")):
        found = [u for u, _ in web.links(page, PAGE) if re.search(rf"/r{reiwa}{key}a4\.pdf$", u, re.I)]
        if found:
            plan.add(found[0], dest / fn)
        else:
            others = sorted({u.rsplit("/", 1)[-1] for u, _ in web.links(page, PAGE) if key in u and u.endswith(".pdf")})
            plan.problem(f"r{reiwa}{key}a4.pdf が {PAGE} に見つかりません（あったもの：{', '.join(others) or 'なし'}）")


def csv_days(path, year):
    """オープンデータの CSV → {地区: {日付: [区分]}}（その年度の4月〜3月の分だけ）"""
    raw = Path(path).read_bytes()
    text = next((raw.decode(e) for e in ("utf-8-sig", "cp932") if _decodes(raw, e)), None)
    out, unknown = {name: defaultdict(list) for name in FILES}, set()
    for r in csv.DictReader(io.StringIO(text)):
        k = r["ゴミ収集カレンダー_西暦年月日"]
        k = f"{k[:4]}-{k[4:6]}-{k[6:8]}"
        if not (f"{year}-04-01" <= k <= f"{year + 1}-03-31"):
            continue
        name = r["ゴミ収集カレンダー_収集区分"].strip()
        if name == "収集なし":
            continue
        c = CSV_CATS.get(name)
        if not c:
            unknown.add(name)
            continue
        out[r["ゴミ収集カレンダー_収集地区"].strip()][k].append(c)
    if unknown:
        raise SystemExit(f"CSV に知らない収集区分があります（CSV_CATS に足す）：{'、'.join(sorted(unknown))}")
    if not all(out.values()):
        raise SystemExit(f"CSV に {year}年度 の収集日がありません（年度のちがう CSV かもしれません）")
    return out


def _decodes(raw, enc):
    try:
        raw.decode(enc)
        return True
    except UnicodeDecodeError:
        return False


def make_calendar(folder, year):
    global YEAR
    folder = Path(folder)
    YEAR = year
    res = {"year": YEAR, "schedules": {}, "areas": [
        {"r": "", "n": "西地区", "s": "西地区", "y": "にしちく",
         "d": "花岡地区・米川地区の全域、久保地区の岩徳線より北、末武地区の平田川より西"},
        {"r": "", "n": "東地区", "s": "東地区", "y": "ひがしちく",
         "d": "下松地区・笠戸島の全域、久保地区の岩徳線より南、末武地区の平田川より東"},
    ]}
    from_csv = csv_days(folder / CSV, year)
    for name, f in FILES.items():
        days = {k: sorted(set(v), key=ORDER.index) for k, v in from_csv[name].items()}
        # 市の PDF と見くらべる。違う日は PDF に合わせる
        pdf = {k: sorted(v, key=ORDER.index) for k, v in extract(folder / f).items()}
        for k in sorted(set(days) | set(pdf)):
            if days.get(k, []) != pdf.get(k, []):
                print(f"  ！ {name} {k}：オープンデータ {'・'.join(days.get(k, [])) or 'なし'} ／ 市のPDF {'・'.join(pdf.get(k, [])) or 'なし'} → PDF に合わせる（オープンデータの入力もれかもしれません）")
                if pdf.get(k):
                    days[k] = pdf[k]
                else:
                    days.pop(k, None)
        res["schedules"][name] = {
            "rules": rules(days),
            "days": dict(sorted(days.items())),
            "moved": {},
        }
    for name, sc in res["schedules"].items():
        print(name, len(sc["days"]), "日", sc["rules"])
    return res
