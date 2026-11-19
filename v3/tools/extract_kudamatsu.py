"""下松市「家庭ごみ収集カレンダー（A4・月ごと）」PDF から収集日データを作る。

使い方:
  python tools/extract_kudamatsu.py <PDFのフォルダ> > kudamatsu.json
  （できた JSON を index.html の window.GOMI_CAL_KUDAMATSU に貼り付ける）

フォルダには市のサイトからダウンロードした r8nishia4.pdf（西地区）・r8higashia4.pdf（東地区）を置く。
PDF の文字は図形（アウトライン）になっているので、文字の図形の「色」と「点の数」から
ごみの種類を見分ける。見分けられない図形があれば標準エラーに出す。
"""
import calendar, datetime as dt, json, sys
from collections import Counter, defaultdict
from pathlib import Path
import pymupdf

FILES = {"西地区": "r8nishia4.pdf", "東地区": "r8higashia4.pdf"}
YEAR = 2026
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

if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    folder = Path(sys.argv[1])
    res = {"year": YEAR, "schedules": {}, "areas": [
        {"r": "", "n": "西地区", "s": "西地区", "y": "にしちく",
         "d": "花岡地区・米川地区の全域、久保地区の岩徳線より北、末武地区の平田川より西"},
        {"r": "", "n": "東地区", "s": "東地区", "y": "ひがしちく",
         "d": "下松地区・笠戸島の全域、久保地区の岩徳線より南、末武地区の平田川より東"},
    ]}
    for name, f in FILES.items():
        days = extract(folder / f)
        res["schedules"][name] = {
            "rules": rules(days),
            "days": {k: sorted(v, key=ORDER.index) for k, v in sorted(days.items())},
            "moved": {},
        }
    print(json.dumps(res, ensure_ascii=False, separators=(",", ":")))
