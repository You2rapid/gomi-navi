"""山口県 防府市（35206）：「家庭ごみ分別収集カレンダー」PDF から収集日を取り出す。

このファイルのきまり（どの自治体も同じ形。tools/update_year.py・download_sources.py から使う）:
  NEED                       … 元データ/<県>/<自治体>/<年度>年度/ に置くファイルの名前
  download(year, dest, web, plan) … 市のサイトから NEED のファイルを探して plan に入れる（web は tools/lib/web.py）
  make_calendar(src, year)   … src（上のフォルダ）のファイルから収集日データ（dict）を作る。読めなければ例外で止める

市のサイトのつくり（令和8年度）:
  クリーンセンターのページ（/soshiki/16/）→「令和８年度家庭ごみ分別収集カレンダー」（/soshiki/16/calendar-.html）。
  ページの下に、地域（牟礼・松崎…大道）ごとの表があり、1行が「自治会名の並び → カレンダーの PDF」。
  PDF は2種類：
    全収集日掲載版   … 燃やせるごみ・プラスチック製容器包装・資源ごみ・危険ごみ・燃やせないごみの収集日
    自主搬入等対応版 … 燃やせるごみ・プラスチック製容器包装の収集日だけ（資源ごみなどを自治会で運ぶ地区）
  PDF は2ページ（1ページ目が4〜9月、2ページ目が10〜3月）。ページは横向きに置いて回してある。
  カレンダーのマスには、日付の数字と、札の文字（可燃・プラ・資源 危険・不燃）が文字で入っている。

フォルダ（元データ/35_山口県/35206_防府市/<年度>年度/）に置くもの:
  カレンダーのページ.html   … 上のページ（自治会名と PDF の対応の元）
  カレンダー/<番号>.pdf     … PDF（番号は市のサイトのファイルの番号）
"""
import collections
import datetime as dt
import html
import re
import unicodedata
from pathlib import Path

import pymupdf

SITE = "https://www.city.hofu.yamaguchi.jp"
TOP = SITE + "/soshiki/16/"          # クリーンセンター
NEED = ["カレンダーのページ.html"]

# 札の文字（最初の1字）→ アプリの区分（city.js の cats）。「資源 危険」は資源ごみと危険ごみが同じ日
LABELS = {"可": ["可燃"], "プ": ["プラ"], "資": ["資源", "危険"], "不": ["不燃"]}
ORDER = ["可燃", "プラ", "資源", "危険", "不燃"]
WD = "日月火水木金土"


def clean(t):
    return re.sub(r"[\s　​]+", "", unicodedata.normalize("NFKC", t))


# ---------- ダウンロード ----------
def page_title(year):
    return f"令和{year - 2018}年度家庭ごみ分別収集カレンダー"


def download(year, dest, web, plan):
    top = web.text(web.get(TOP))
    url = next((u for u, label in web.links(top, TOP) if clean(label) == page_title(year)), None)
    if not url:
        plan.problem(f"クリーンセンターのページに「{page_title(year)}」がありません（{TOP}）")
        return
    raw = web.get(url)
    page = web.text(raw)
    if page_title(year) not in clean(re.sub(r"<[^>]+>", "", page)):
        plan.problem(f"{url} は {page_title(year)} のページではないようです")
        return
    plan.add(url, Path(dest) / "カレンダーのページ.html", raw)
    for row in table_rows(page):
        if row["url"] and not any(p == Path(dest) / "カレンダー" / row["file"] for _, p, _ in plan.todo):
            plan.add(row["url"], Path(dest) / "カレンダー" / row["file"])


def table_rows(page):
    """カレンダーのページの地域の表 → [{"r": 地域, "towns": [自治会名], "label": PDF の名前, "url", "file"}]。
    PDF のない行（「排出日等については、自治会に確認してください。」）は url を空にする"""
    out = []
    for cap, body in re.findall(r"<table[^>]*>\s*<caption>(.*?)</caption>(.*?)</table>", page, re.S):
        region = clean(re.sub(r"<[^>]+>", "", html.unescape(cap)))
        if not region.endswith("地域"):
            continue
        region = region[:-2]
        for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", body, re.S):
            tds = re.findall(r"<td[^>]*>(.*?)</td>", tr, re.S)
            if len(tds) == 3:          # 1行目（地域のマスがある行）
                tds = tds[1:]
            if len(tds) != 2:
                continue
            names = clean(re.sub(r"<[^>]+>", "", html.unescape(tds[0].replace("<br />", "・").replace("<br>", "・"))))
            if names in ("自治会名", ""):
                continue
            m = re.search(r'href="([^"]*?/uploaded/attachment/(\d+)\.pdf)"[^>]*>(.*?)</a>', tds[1], re.S)
            label = clean(re.sub(r"<[^>]+>|\[PDF.*?\]", "", html.unescape(m.group(3)))) if m else ""
            label = re.sub(r"\[PDFファイル/.*?\]", "", label)
            out.append({"r": region, "towns": [t for t in names.split("・") if t],
                        "label": label, "url": (SITE + m.group(1) if m.group(1).startswith("/") else m.group(1)) if m else "",
                        "file": f"{m.group(2)}.pdf" if m else "",
                        "note": "" if m else clean(re.sub(r"<[^>]+>", "", html.unescape(tds[1])))})
    return out


# ---------- PDF の読み取り ----------
def words(page):
    """ページの文字（回したあとの向き）：[(x0, y0, x1, y1, 文字)]"""
    m = page.rotation_matrix
    out = []
    for w in page.get_text("words"):
        r = pymupdf.Rect(w[:4]) * m
        out.append((r.x0, r.y0, r.x1, r.y1, clean(w[4])))
    return out


def month_blocks(ws):
    """曜日の見出し（日 月 火 水 木 金 土）が横に並ぶ所を、月のカレンダー1つとする"""
    heads = [w for w in ws if w[4] in WD and len(w[4]) == 1 and 10 <= w[3] - w[1] <= 30]
    rows = collections.defaultdict(list)
    for w in heads:
        rows[round(w[1])].append(w)
    blocks = []
    for y, ws_ in rows.items():
        ws_.sort()
        # 同じ高さに2つの月が並ぶので、左から「日〜土」の7つずつに分ける
        i = 0
        while i + 7 <= len(ws_):
            seq = ws_[i:i + 7]
            if "".join(w[4] for w in seq) == WD:
                blocks.append(seq)
                i += 7
            else:
                i += 1
    return blocks


def read_month(ws, head, path, pix):
    """1か月のカレンダー → (年, 月, {日: [区分]})"""
    cx = [(w[0] + w[2]) / 2 for w in head]
    colw = cx[1] - cx[0]
    left, right, top = cx[0] - colw / 2, cx[6] + colw / 2, head[0][3]
    # 見出しのすぐ上にある「4 月」と「令和8年（2026年）」
    above = [w for w in ws if left <= w[0] and w[2] <= right and top - 60 <= w[1] < head[0][1]]
    mt = [w for w in above if re.fullmatch(r"\d{1,2}", w[4]) and w[3] - w[1] > 25]
    yt = [re.search(r"(\d{4})年", w[4]) for w in above]
    yt = [int(m.group(1)) for m in yt if m]
    if len(mt) != 1 or len(yt) != 1:
        raise SystemExit(f"{path.name}：月の見出しが読めません（{[w[4] for w in above]}）")
    yy, mm = yt[0], int(mt[0][4])
    # 日付の数字（大きい字）。「24/31」のように2つの日が1マスのこともある。
    # 3月の最後の行の灰色の「4/1」「4/2」は次の年度の日なので入れない（2つ目の数が1つ目の7日あとのときだけ2つの日）
    nums = []
    for w in ws:
        if not (left <= w[0] and w[2] <= right and top < w[1] < top + 220 and 20 < w[3] - w[1] < 35):
            continue   # 次の月の見出し（高さ40）は入れない
        m = re.fullmatch(r"(\d{1,2})(?:/(\d{1,2}))?", w[4])
        if m and (not m.group(2) or int(m.group(2)) == int(m.group(1)) + 7):
            nums.append(w)
    slash = [w for w in ws if w[4] == "/" and left <= w[0] and w[2] <= right and top < w[1] < top + 220]
    small = [w for w in ws if left <= w[0] and w[2] <= right and top < w[1] < top + 230 and w[3] - w[1] < 12]
    ys = sorted({round(w[1]) for w in nums})
    rowh = min(b - a for a, b in zip(ys, ys[1:]) if b - a > 5) if len(ys) > 1 else 31
    ndays = (dt.date(yy + (mm == 12), mm % 12 + 1, 1) - dt.date(yy, mm, 1)).days
    cells = collections.defaultdict(list)   # (行の y, 列) → そのマスの数字
    for w in nums:
        col = min(range(7), key=lambda i: abs(cx[i] - (w[0] + w[2]) / 2))
        cells[(round(w[1] / 4), col)].append(w)
    out = {}
    for (_, col), ws_ in cells.items():
        x0, x1 = cx[col] - colw / 2, cx[col] + colw / 2
        y0 = min(w[1] for w in ws_) - 2
        y1 = y0 + rowh
        singles = sorted((w for w in ws_ if "/" not in w[4]), key=lambda w: w[0])
        if len(singles) >= 2:
            # 勝間の 8月「24 / 31」：1マスを2つに分けて、24日は札（可燃・不燃）、31日は背景の色（可燃のピンク）で示している。
            # 下に隠れた「24/31」の文字もあるので、それは使わない
            if not any(x0 <= s[0] < x1 and y0 <= s[1] < y1 for s in slash):
                raise SystemExit(f"{path.name} {yy}/{mm}：1マスに日付が2つある（{[w[4] for w in singles]}）")
            parts = [(int(singles[0][4]), None)] + [(int(w[4]), bg_cats(pix, w, path)) for w in singles[1:]]
        elif len(ws_) == 1:
            parts = [(int(d), None) for d in ws_[0][4].split("/")]   # 「24/31」：札は両方の日にかかる
        else:
            raise SystemExit(f"{path.name} {yy}/{mm}：マスの日付が読めません（{[w[4] for w in ws_]}）")
        chars = [s[4] for s in small if x0 <= (s[0] + s[2]) / 2 < x1 and y0 <= (s[1] + s[3]) / 2 < y1]
        cats = []
        for ch in chars:
            if ch[:1] in LABELS:
                cats += [c for c in LABELS[ch[:1]] if c not in cats]
            elif ch not in ("燃", "ラ", "源", "危", "険"):
                raise SystemExit(f"{path.name} {yy}/{mm}/{ws_[0][4]}：知らない札の文字「{ch}」")
        for d, bg in parts:
            if d in out:
                raise SystemExit(f"{path.name} {yy}/{mm}/{d}：同じ日が2つある")
            if (dt.date(yy, mm, d).weekday() + 1) % 7 != col:
                raise SystemExit(f"{path.name} {yy}/{mm}/{d}：曜日の列がちがう")
            out[d] = sorted(cats if bg is None else bg, key=ORDER.index)
    if sorted(out) != list(range(1, ndays + 1)):
        raise SystemExit(f"{path.name} {yy}/{mm}：日付がそろいません（{sorted(out)}）")
    return yy, mm, out


# マスの背景の色（画面の色。72dpi で描いたとき）→ 区分。分けたマスの右側の日だけに使う
BG = {(250, 213, 229): ["可燃"], (208, 228, 165): ["プラ"], (199, 234, 251): ["資源", "危険"],
      (255, 244, 96): ["不燃"], (255, 255, 255): []}


def bg_cats(pix, w, path):
    cnt = collections.Counter(pix.pixel(x, y) for x in range(int(w[0]), int(w[2])) for y in range(int(w[1]), int(w[3])))
    for c, _ in cnt.most_common():
        if sum(c) > 450:   # 文字（黒）でない、いちばん多い色
            best = min(BG, key=lambda k: sum(abs(a - b) for a, b in zip(k, c)))
            if sum(abs(a - b) for a, b in zip(best, c)) > 30:
                raise SystemExit(f"{path.name}：「{w[4]}」のマスの色 {c} がどの区分かわかりません")
            return BG[best]
    raise SystemExit(f"{path.name}：「{w[4]}」のマスの色が読めません")


def read_pdf(path, year):
    doc = pymupdf.open(path)
    days = {}
    for page in doc:
        ws = words(page)
        pix = page.get_pixmap()   # 72dpi（1点＝1画素。words と同じ向き）
        heads = month_blocks(ws)
        if len(heads) != 6:
            raise SystemExit(f"{path.name}：1ページに月が {len(heads)}（6のはず）")
        for head in heads:
            yy, mm, md = read_month(ws, head, path, pix)
            for d, cats in md.items():
                days[dt.date(yy, mm, d)] = cats
    first, last = dt.date(year, 4, 1), dt.date(year + 1, 3, 31)
    want = (last - first).days + 1
    if len(days) != want or min(days) != first or max(days) != last:
        raise SystemExit(f"{path.name}：{year}年度の日付がそろいません（{len(days)}日。{min(days)}〜{max(days)}）")
    return {d: c for d, c in days.items() if c}


def rules_of(days):
    """区分ごとに「毎週◯曜日」「毎月第◯◯曜日」などにまとめる（岩国市と同じ考え方）"""
    occ = collections.defaultdict(list)
    for d, ks in days.items():
        for c in ks:
            occ[c].append(d)
    rules, moved = {}, collections.defaultdict(list)
    for c in ORDER:
        ds = occ.get(c)
        if not ds:
            continue
        wds = collections.Counter((d.weekday() + 1) % 7 for d in ds)
        main = sorted(w for w, n in wds.items() if n >= len(ds) * 0.25)
        for d in ds:
            if (d.weekday() + 1) % 7 not in main:
                moved[d.isoformat()].append(c)
        wtxt = "・".join(WD[w] for w in main)
        per = sum(wds[w] for w in main) / len(main)
        nth = collections.Counter((d.day - 1) // 7 + 1 for d in ds if (d.weekday() + 1) % 7 in main)
        if per >= 40:
            rules[c] = f"毎週{wtxt}曜日"
        elif len(main) == 1 and len(nth) <= 2 and all(n >= 10 for n in nth.values()):
            rules[c] = f"毎月第{'・'.join(map(str, sorted(nth)))}{wtxt}曜日"
        else:
            rules[c] = f"月{max(1, round(len(ds) / 12))}回 {wtxt}曜日" if len(ds) >= 10 else f"年{len(ds)}回（日はカレンダーで確認）"
    return rules, {k: sorted(v, key=ORDER.index) for k, v in sorted(moved.items())}


def sched_name(label):
    """PDF の名前 → 日程の名前。「牟礼小校区（全収集日掲載版）」→「牟礼小校区」、
    「牟礼小校区（自主搬入等対応版）」→「牟礼小校区・自主搬入」、「富海」→「富海」"""
    m = re.fullmatch(r"(.+?)[（(](全収集日掲載版|自主搬入等対応版)[）)]", label)
    if not m:
        return label
    return m.group(1) + ("・自主搬入" if m.group(2).startswith("自主") else "")


def yomi_of(n):
    """自治会名のよみ（ひらがな。自動でつけるので、地元の読み方とちがうことがある。検索だけに使う）。
    「ヶ」は「が」にしてから読む（郷ヶ崎・遠ヶ崎・自由ヶ丘）"""
    import kana   # tools/lib（update_year.py から呼ばれるときは読み込める）
    return kana.yomi(n.replace("ヶ", "が")).strip()


def make_calendar(folder, year):
    folder = Path(folder)
    page = (folder / "カレンダーのページ.html").read_text(encoding="utf-8")
    if page_title(year) not in clean(re.sub(r"<[^>]+>", "", page)):
        raise SystemExit(f"カレンダーのページ.html が {page_title(year)} ではありません")
    rows = table_rows(page)
    by_file = {}
    for row in rows:
        if not row["url"]:
            print("カレンダーなし：", row["r"], "・".join(row["towns"]), row["note"])
            continue
        p = folder / "カレンダー" / row["file"]
        if not p.exists():
            raise SystemExit(f"PDF がありません：{p}（download_sources.py で保存する）")
        if row["file"] not in by_file:
            by_file[row["file"]] = (row["label"], read_pdf(p, year))
    res = {"year": year, "schedules": {}, "areas": []}
    names = {}
    for f, (label, days) in by_file.items():
        s = sched_name(label)
        if s in res["schedules"]:
            # 同じ名前の日程が2つ（中関の「田島宿舎」の行は、名前が「中関」で中身は自主搬入等対応版）
            if names[s] == f:
                continue
            s = s + "・" + f
        names[s] = f
        rules, moved = rules_of(days)
        res["schedules"][s] = {"rules": rules, "days": {d.isoformat(): ks for d, ks in sorted(days.items())}, "moved": moved}
        print(s, f, len(days), "日", rules)
    file2s = {f: s for s, f in names.items()}
    # 自主搬入等対応版は、同じ地域の全収集日掲載版から資源ごみ・危険ごみ・燃やせないごみを抜いたものになっているはず
    for s, f in names.items():
        if s.endswith("・自主搬入") and s[:-5] in res["schedules"]:
            full = {d: [c for c in ks if c in ("可燃", "プラ")] for d, ks in res["schedules"][s[:-5]]["days"].items()}
            full = {d: ks for d, ks in full.items() if ks}
            if full != res["schedules"][s]["days"]:
                raise SystemExit(f"{s} の燃やせるごみ・プラの日が、{s[:-5]} とちがいます")
    seen = collections.Counter()
    for row in rows:
        if not row["url"]:
            continue
        s = file2s[row["file"]]
        for t in row["towns"]:
            seen[(row["r"], t)] += 1
            res["areas"].append({"r": row["r"], "n": t, "s": s, "y": yomi_of(t)})
    dup = [k for k, c in seen.items() if c > 1]
    if dup:
        raise SystemExit(f"同じ地域に同じ名前の自治会があります：{dup}")
    print("地区（自治会）", len(res["areas"]), "日程", len(res["schedules"]))
    return res
