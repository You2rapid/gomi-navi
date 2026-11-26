"""東京都 世田谷区（13112）：区の「資源・ごみ収集曜日一覧」（CSV）と「資源とごみの収集カレンダー」の対象地区の一覧から、収集日データを作る。

このファイルのきまり（どの自治体も同じ形。tools/update_year.py・download_sources.py から使う）:
  NEED                       … 元データ/<県>/<自治体>/<年度>年度/ に置くファイルの名前
  download(year, dest, web, plan) … 区のサイトから NEED のファイルを探して plan に入れる（web は tools/lib/web.py）
  make_calendar(src, year)   … src（上のフォルダ）のファイルから収集日データ（dict）を作る。読めなければ例外で止める

世田谷区の収集日は、町（丁目のまとまり）ごとに曜日で決まっている。
  資源（古紙・びん・缶）週1回、可燃ごみ 週2回、不燃ごみ 月2回（1回目・3回目 か 2回目・4回目の○曜日）、ペットボトル 月2回。
  祝日も収集する。年末年始だけ休み（区のカレンダーで「収集はありません」の日。YEAR_END に書く）。
区は「資源とごみの収集カレンダー」（暦年。1〜12月と前の年の12月）を対象地区ごとに41種類（対象地区1〜41）作っていて、
カレンダーのページに「町名丁目 → 対象地区の番号（PDF）」の一覧がある。対象地区1〜37は収集曜日一覧（CSV）の町のまとまり、
38〜41は、まわりの町とちがう日に集める集合住宅（防衛省池尻宿舎・都営下馬二丁目アパートなど）。
  ・地区（アプリの地区）は、カレンダーのページの一覧のとおり（町名丁目と集合住宅。決まり A1）。日程は対象地区の番号。
  ・対象地区1〜37の曜日は CSV。同じ番号の町の曜日がすべて同じか確かめる（ちがえば止まる）。
  ・対象地区38〜41の曜日は CSV にないので、カレンダー（PDF）を見て SPECIAL に書いた。
  ・カレンダーの PDF（令和9年版から文字と色の札が入っている）が カレンダー/<暦年>_<番号>.pdf にあれば、
    札の日付を読んで、作った収集日と見くらべる（合わなければ止まる）。令和8年版は画像だけなので読まない。

フォルダ（元データ/13_東京都/13112_世田谷区/<年度>年度/）に置くもの:
  収集曜日一覧.csv          … 「資源・ごみ収集日(一覧)」のページの CSV（Shift_JIS）
  カレンダー_<年>年版.html   … 「令和○年(<年>年)版資源とごみの収集カレンダー（PDF）」のページ（年度の4〜12月の年と、次の年の1〜3月の年の2つ）
  カレンダー/<年>_<番号>.pdf … 見くらべ用（なくてもよい）
"""
import csv
import datetime as dt
import io
import re
import sys
import unicodedata
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "lib"))
import kana  # noqa: E402

SITE = "https://www.city.setagaya.lg.jp"
LIST_PAGE = SITE + "/02241/416.html"                       # 資源・ごみ収集日(一覧)（CSV）
CAT_PAGE = SITE + "/kurashi/gomi/category/11684.html"      # 資源・ごみの収集日（カレンダーのページへのリンク）
PERENNIAL = True   # 曜日で決まる（毎年のカレンダーは配布するが、曜日はふつう変わらない）


def need(year):
    return ["収集曜日一覧.csv", f"カレンダー_{year}年版.html", f"カレンダー_{year + 1}年版.html"]


NEED = need(2026)

# 年末年始：off＝収集しない日（両端をふくむ）。区のカレンダー（12月と1月のページ）の「収集はありません」の日
YEAR_END = {
    2026: {"off": ("2026-12-31", "2027-01-03"),
           "src": "令和9年（2027年）版資源とごみの収集カレンダー 2ページ（2026年12月31日・2027年1月1日〜3日 収集はありません）"},
}
DEFAULT_OFF = ("12-31", "01-03")

# 対象地区38〜41（集合住宅）の曜日。収集曜日一覧（CSV）にないので、カレンダー（令和8年版・令和9年版の PDF）を見て書いた。
# 値の形は CSV と同じ（資源, 可燃ごみ, 不燃ごみ, ペットボトル）
SPECIAL = {
    38: ("金曜日", "月曜日・木曜日", "1回目・3回目の金曜日", "1回目・3回目の火曜日"),
    39: ("金曜日", "火曜日・金曜日", "2回目・4回目の月曜日", "1回目・3回目の月曜日"),
    40: ("金曜日", "火曜日・金曜日", "1回目・3回目の月曜日", "2回目・4回目の月曜日"),
    41: ("金曜日", "火曜日・金曜日", "1回目・3回目の金曜日", "1回目・3回目の火曜日"),
}

CATS = ["資源", "可燃", "不燃", "ペット"]       # CSV の列の順（資源・可燃ごみ・不燃ごみ・ペットボトル）
WD = "月火水木金土日"           # Python の weekday() の順
# カレンダーの PDF の札の色 → 区分（令和9年版の札の色。city.js の色と同じ）
PDF_COLORS = {"e60012": "可燃", "008d43": "資源", "0068b7": "不燃", "a7d397": "ペット"}


def nfkc(s):
    return unicodedata.normalize("NFKC", s).strip()


def wave(s):
    """「1～3」の波の形をそろえる（全角チルダ → 波ダッシュ）"""
    return s.replace("～", "〜").replace("~", "〜")


# ---------------- 曜日の決まり ----------------
def parse_rule(cat, text):
    """「火曜日・金曜日」→ {"w": [1, 4]}、「1回目・3回目の水曜日」→ {"w": [2], "n": [1, 3]}"""
    t = nfkc(text)
    m = re.fullmatch(r"(\d)回目・(\d)回目の([月火水木金土])曜日", t)
    if m:
        return {"w": [WD.index(m[3])], "n": [int(m[1]), int(m[2])]}
    ws = re.findall(r"([月火水木金土])曜日", t)
    if ws and re.fullmatch(r"([月火水木金土]曜日・?)+", t):
        return {"w": [WD.index(w) for w in ws]}
    raise ValueError(f"{cat} の曜日が読めません：「{text}」")


def say(rule):
    ws = "・".join(WD[w] for w in rule["w"])
    if "n" in rule:
        return f"毎月{rule['n'][0]}回目・{rule['n'][1]}回目の{ws}曜日"
    return f"毎週{ws}曜日"


def hits(rule, d):
    return d.weekday() in rule["w"] and ("n" not in rule or (d.day - 1) // 7 + 1 in rule["n"])


def days_of(rules, year, off):
    out = {}
    d, end = dt.date(year, 4, 1), dt.date(year + 1, 3, 31)
    while d <= end:
        k = d.isoformat()
        if not (off[0] <= k <= off[1]):
            cs = [c for c in CATS if hits(rules[c], d)]
            if cs:
                out[k] = cs
        d += dt.timedelta(days=1)
    return out


# ---------------- 区の資料を読む ----------------
def read_csv(path):
    """収集曜日一覧（CSV）→ [{"town": 町名, "chome": 丁目, "vals": (資源, 可燃, 不燃, ペット), "office": 清掃事務所}]"""
    raw = Path(path).read_bytes()
    for enc in ("cp932", "utf-8-sig"):
        try:
            text = raw.decode(enc)
            break
        except UnicodeDecodeError:
            pass
    rows = list(csv.reader(io.StringIO(text)))
    head = next(i for i, r in enumerate(rows) if r and r[1:3] == ["町名", "丁目"])
    want = ["資源（週1回）", "可燃ごみ（週2回）", "不燃ごみ（月2回）", "ペットボトル（月2回）", "管轄清掃事務所"]
    if rows[head][3:8] != want:
        raise ValueError(f"収集曜日一覧の列がかわりました：{rows[head]}（calendar.py を直す）")
    out = []
    for r in rows[head + 1:]:
        if len(r) >= 8 and r[1].strip():
            out.append({"town": nfkc(r[1]), "chome": nfkc(r[2]), "vals": tuple(nfkc(x) for x in r[3:7]), "office": nfkc(r[7])})
    return out


def read_list(path):
    """カレンダーのページ → [(地区名, 対象地区の番号)]（ページの順）"""
    t = Path(path).read_text(encoding="utf-8", errors="replace")
    out = []
    for href, label in re.findall(r'<a[^>]+href="([^"]+\.pdf)"[^>]*>([^<]*)</a>', t):
        m = re.search(r"/(?:no)?0*(\d+)(?:_r\d+)?\.pdf$", href)
        label = re.sub(r"（PDF：[^）]*）", "", label).strip()
        if m and label and "共通" not in label:
            out.append((label, int(m[1])))
    if len(out) < 100:
        raise ValueError(f"{path}：対象地区の一覧が {len(out)} 件しか読めません（ページの形がかわった？）")
    return out


def split_label(label):
    """「赤堤1・3～5丁目」→ (赤堤, {1,3,4,5})、「砧公園」→ (砧公園, None)、
    「防衛省池尻宿舎（池尻1丁目4番1番）」→ (防衛省池尻宿舎, None, 池尻1丁目4番1番)"""
    s = wave(nfkc(label))
    m = re.fullmatch(r"(.+?)（(.+)）", s)
    if m:
        return m[1], None, m[2]
    m = re.fullmatch(r"(.+?)([\d・〜]+)丁目", s)
    if not m:
        return s, None, ""
    nums = set()
    for part in m[2].split("・"):
        a, _, b = part.partition("〜")
        nums |= set(range(int(a), int(b or a) + 1))
    return m[1], frozenset(nums), ""


def csv_key(r):
    """CSV の行 → くらべる形（町名, 丁目の集合）"""
    return split_label(r["town"] + (r["chome"] + "丁目" if r["chome"] else ""))[:2]


# ---------------- カレンダーの PDF と見くらべる ----------------
def pdf_days(pdf, cal_year):
    """カレンダーの PDF（令和9年版の形）→ {日付: 区分の集合}。文字のない PDF は None。
    2ページ目の左が前の年の12月、そのあと左右の順に1〜12月。日付の数字の下の色の札を、その日の区分とする"""
    import pymupdf
    doc = pymupdf.open(pdf)
    if not doc[1].get_text().strip():
        return None
    out, month = {}, dt.date(cal_year - 1, 12, 1)
    for page in doc:
        nums = [s for b in page.get_text("dict")["blocks"] for ln in b.get("lines", []) for s in ln["spans"]
                if s["size"] >= 14 and re.fullmatch(r"\d{1,2}", s["text"].strip())]
        rects = [(PDF_COLORS["%02x%02x%02x" % tuple(round(x * 255) for x in d["fill"])], d["rect"]) for d in page.get_drawings()
                 if d.get("fill") and "%02x%02x%02x" % tuple(round(x * 255) for x in d["fill"]) in PDF_COLORS
                 and 18 <= d["rect"].width <= 60 and 9 <= d["rect"].height <= 18]
        for half in (0, 1):
            x0 = half * page.rect.width / 2
            ns = [s for s in nums if x0 <= s["bbox"][0] < x0 + page.rect.width / 2]
            if len({int(s["text"]) for s in ns}) < 25 or not any(s["text"].strip() == "1" for s in ns):   # 1か月の日付がない（文のページ）
                continue
            first = min((s for s in ns if int(s["text"]) == 1), key=lambda s: s["bbox"][1])
            gx = min(s["bbox"][0] for s in ns)      # いちばん左の列（日曜日）の左はし

            def column(x):
                return int((x - gx + 6) // 56.7)
            col = column(first["bbox"][0])
            if col != (month.weekday() + 1) % 7:
                raise ValueError(f"{Path(pdf).name}：{month:%Y年%m月}のつもりのページで、1日の曜日が合いません（ページの順がかわった？）")
            last = (month.replace(month=month.month % 12 + 1, year=month.year + month.month // 12) - dt.timedelta(days=1)).day
            for cat, r in rects:
                if not (x0 <= r.x0 < x0 + page.rect.width / 2):
                    continue
                # 同じ列（曜日）で、札より上にあって、いちばん近い日付の数字（同じマスの中）。
                # 「24/31」のように1マスに2日あるとき、右下の日付は左の列（日曜日）のマスにあるので、列で分ける
                cand = [s for s in ns if column(s["bbox"][0]) == column(r.x0) and 0 < r.y0 - s["bbox"][1] < 95]   # 2月は行が高い
                if not cand:
                    continue
                s = min(cand, key=lambda s: r.y0 - s["bbox"][1])
                n = int(s["text"])
                if 1 <= n <= last:
                    out.setdefault(month.replace(day=n).isoformat(), set()).add(cat)
            month = month.replace(month=month.month % 12 + 1, year=month.year + month.month // 12)
    return out or None      # 色の札がない（画像だけの PDF。令和8年版）


def check_pdfs(folder, year, schedules, problems):
    """カレンダー/<暦年>_<番号>.pdf があれば、その年度の範囲の日付を見くらべる"""
    checked = []
    for pdf in sorted((Path(folder) / "カレンダー").glob("*_*.pdf")):
        m = re.fullmatch(r"(\d{4})_(\d+)\.pdf", pdf.name)
        if not m or m[2].lstrip("0") not in schedules:
            continue
        got = pdf_days(pdf, int(m[1]))
        if got is None:
            continue
        want = schedules[m[2].lstrip("0")]["days"]
        lo, hi = max(f"{year}-04-01", f"{int(m[1]) - 1}-12-01"), min(f"{year + 1}-03-31", f"{m[1]}-12-31")
        keys = sorted({k for k in list(got) + list(want) if lo <= k <= hi})
        bad = [f"{k}：カレンダー {'・'.join(sorted(got.get(k, [])))}／作った日 {'・'.join(want.get(k, []))}"
               for k in keys if set(got.get(k, [])) != set(want.get(k, []))]
        if bad:
            problems += [f"対象地区{m[2].lstrip('0')}（{pdf.name}）" + b for b in bad]
        checked.append(f"{pdf.name}（{keys[0] if keys else ''}〜{keys[-1] if keys else ''}、{len(keys)}日）")
    return checked


# ---------------- 区のサイトから取ってくる ----------------
def download(year, dest, web, plan):
    page = web.text(web.get(LIST_PAGE))
    csvs = [u for u, l in web.links(page, LIST_PAGE) if u.lower().endswith(".csv") and "収集曜日一覧" in l]
    if csvs:
        plan.add(csvs[0], dest / "収集曜日一覧.csv")
    else:
        plan.problem(f"資源・ごみ収集曜日一覧（CSV）が {LIST_PAGE} に見つかりません")
    cat = web.text(web.get(CAT_PAGE))
    for y in (year, year + 1):
        found = [u for u, l in web.links(cat, CAT_PAGE) if f"({y}年)版資源とごみの収集カレンダー" in l.replace("（", "(").replace("）", ")")]
        if found:
            plan.add(found[0], dest / f"カレンダー_{y}年版.html")
        else:
            plan.problem(f"「令和{y - 2018}年({y}年)版資源とごみの収集カレンダー」のページが {CAT_PAGE} に見つかりません"
                         + ("（例年11月ごろに出る）" if y == year + 1 else ""))


# ---------------- 収集日を作る ----------------
def make_calendar(folder, year):
    folder = Path(folder)
    if year in YEAR_END:
        off, tentative = YEAR_END[year]["off"], False
    else:
        off = (f"{year}-{DEFAULT_OFF[0]}", f"{year + 1}-{DEFAULT_OFF[1]}")
        tentative = True
        print(f"  ！ {year}年度の年末年始がまだ calendar.py の YEAR_END にありません。12/31〜1/3 を休みとして作ります（区のカレンダーで確かめて直す）")
    problems = []
    rows = read_csv(folder / "収集曜日一覧.csv")
    lists = [read_list(folder / f) for f in need(year)[1:]]
    if lists[0] != lists[1]:
        a, b = dict(lists[0]), dict(lists[1])
        diff = sorted({k for k in a.keys() | b.keys() if a.get(k) != b.get(k)})
        raise ValueError(f"{year}年版と{year + 1}年版で、対象地区の一覧がちがいます：{'・'.join(diff[:10])}"
                         "（年の途中で番号がかわるときは、calendar.py で月ごとに分ける）")
    labels = lists[1]

    # 対象地区の番号ごとの曜日：CSV の町を、一覧の地区名とくらべて番号を決める
    plain = [(split_label(l)[:2], n) for l, n in labels if not split_label(l)[2]]
    vals, office = {}, {}
    for r in rows:
        k = csv_key(r)
        n = next((v for kk, v in plain if kk == k), None)
        if n is None:
            raise ValueError(f"収集曜日一覧の「{r['town']}{r['chome']}」が、カレンダーの対象地区の一覧にありません")
        if vals.setdefault(n, r["vals"]) != r["vals"]:
            raise ValueError(f"対象地区{n}の町で、曜日がちがいます：{r['town']}{r['chome']} {r['vals']}／{vals[n]}")
        office[k] = r["office"]
    for n, v in SPECIAL.items():
        if n in vals:
            raise ValueError(f"対象地区{n}が収集曜日一覧にもあります（SPECIAL を消す）")
        vals[n] = v
    missing = sorted({n for _, n in labels} - set(vals))
    if missing:
        raise ValueError(f"対象地区 {missing} の曜日がわかりません（収集曜日一覧にも SPECIAL にもない）")

    schedules = {}
    for n in sorted({n for _, n in labels}):
        rules = {c: parse_rule(c, v) for c, v in zip(CATS, vals[n])}
        schedules[str(n)] = {"rules": {c: say(rules[c]) for c in CATS}, "days": days_of(rules, year, off), "moved": {}}

    areas = []
    for label, n in labels:
        town, nums, place = split_label(label)
        a = {"n": wave(label), "s": str(n), "y": kana.yomi(town)}
        if place:
            a["d"] = f"{wave(place)}の集合住宅（まわりの町とちがう日）"
        else:
            o = office.get((town, nums))
            if o:
                a["d"] = f"{o}清掃事務所"
        areas.append(a)

    checked = check_pdfs(folder, year, schedules, problems)
    res = {"year": year, "schedules": schedules, "areas": areas,
           "yearEnd": {"off": list(off), "tentative": tentative}}
    print(f"世田谷区：地区 {len(areas)}・対象地区（日程） {len(schedules)}")
    print(f"  カレンダーの PDF と見くらべた：{len(checked)}件" + ("（" + "、".join(checked) + "）" if checked else ""))
    if problems:
        for p in problems[:40]:
            print("  ！", p)
        raise ValueError(f"カレンダーの PDF と合わない日が {len(problems)} 日あります（上の一覧）")
    return res
