"""東京都 大田区（13111）：区のオープンデータ「資源・ごみ収集曜日、清掃事業所管轄一覧」と、区のページ「年末年始の資源とごみ収集のお知らせ」から収集日データを作る。

このファイルのきまり（どの自治体も同じ形。tools/update_year.py・download_sources.py から使う）:
  NEED                       … 元データ/<県>/<自治体>/<年度>年度/ に置くファイルの名前
  download(year, dest, web, plan) … 区のサイトから NEED のファイルを探して plan に入れる（web は tools/lib/web.py）
  make_calendar(src, year)   … src（上のフォルダ）のファイルから収集日データ（dict）を作る。読めなければ例外で止める

大田区の収集日は、町丁目（番地で分かれるところもある）ごとに曜日で決まっている。
  プラスチック 週1回・資源（新聞・雑誌・紙パック・段ボール・びん・缶・ペットボトル）週1回・可燃ごみ 週2回・不燃ごみ 月2回（その月の1・3回目か2・4回目の○曜日）。
  祝日も収集する。年末年始だけ休み（令和8年度：12月31日〜1月3日。「年末年始の資源とごみ収集のお知らせ」）。
  ・曜日：東京都オープンデータカタログの大田区「資源・ごみ収集曜日、清掃事業所管轄一覧」（xlsx、CC BY。シート名「R07全域」）。
  ・地区：「年末年始の資源とごみ収集のお知らせ」の住所別の表（その年度の町丁目の分け方。87行）。
  ・年末年始の表の「年末最終日」「年始開始日」（4区分 × 2）が、曜日で作った日と合うか、地区ごとに確かめる（合わなければ止まる）。
    これで、オープンデータの曜日がその年度も同じか確かめられる。
  ・不燃ごみは、「資源とごみの収集日」のページの「地区別収集日一覧（令和○年4月から令和○年3月分）」の日付とも見くらべる。

フォルダ（元データ/13_東京都/13111_大田区/<年度>年度/）に置くもの:
  資源とごみの収集日.html     … https://www.city.ota.tokyo.jp/seikatsu/gomi/shigentogomi/gomishigen.html（不燃ごみの日付の表）
  年末年始のお知らせ.html     … https://www.city.ota.tokyo.jp/oshirase/mokutekibetsu/gomi/nennmatunennsi.html（例年11月ごろ更新）
  オープンデータは 元データ/13_東京都/13111_大田区/オープンデータ/資源・ごみ収集曜日、清掃事業所管轄一覧.xlsx
"""
import datetime as dt
import html as H
import re
import sys
import unicodedata
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "lib"))
import kana  # noqa: E402
import xlsx  # noqa: E402

SITE = "https://www.city.ota.tokyo.jp"
PAGE = SITE + "/seikatsu/gomi/shigentogomi/gomishigen.html"
YE_PAGE = SITE + "/oshirase/mokutekibetsu/gomi/nennmatunennsi.html"
OPENDATA = "資源・ごみ収集曜日、清掃事業所管轄一覧.xlsx"
NEED = ["資源とごみの収集日.html", "年末年始のお知らせ.html"]
PERENNIAL = True
# オープンデータの「管轄の清掃事務所」→ 区のページの書き方
OFFICE = {"大森": "大森清掃事務所", "蒲田": "蒲田清掃事務所（蒲田地区）", "調布": "蒲田清掃事務所（調布地区）"}
CATS = ["プラ", "資源", "可燃", "不燃"]
WD = "月火水木金土日"

# 年末年始：off＝収集しない日（両端をふくむ）
YEAR_END = {
    2026: {"off": ("2026-12-31", "2027-01-03"), "src": "年末年始の資源とごみ収集のお知らせ（2026-11-09 更新）「12月31日（木曜日）から1月3日（日曜日）まで、すべての収集を休みます」"},
}
DEFAULT_OFF = ("12-31", "01-03")

# 年末年始の表（その年度の分け方）にあって、オープンデータ（令和7年度）にない行 → オープンデータのどの行と同じ曜日か。
# 区の「収集曜日」PDF（令和8年度、資源とごみの分け方・出し方 17ページ）を見て決めた（2行とも同じ曜日）
SAME_AS = {
    ("大森北", "1丁目、4丁目、5丁目 [1から8番、12番、13番、15番、16番]"): ("大森北", "1丁目・4丁目・5丁目"),
    ("大森北", "5丁目 [9から11番、14番]"): ("大森北", "1丁目・4丁目・5丁目"),
}


def nfkc(s):
    return unicodedata.normalize("NFKC", s).strip()


def key(town, part):
    """町名・町丁目の書き方をそろえる（オープンデータと年末年始の表で、「、」「・」「から」「〜」「全域 (1丁目、2丁目)」がちがう）"""
    p = nfkc(part)
    p = re.sub(r"^全域\s*\(.*\)$", "全域", p)
    p = p.replace("から", "~").replace("～", "~").replace("〜", "~").replace("、", "・").replace("〔", "[").replace("〕", "]")
    p = re.sub(r"[番号・]", "", p)       # 「18・19番」と「18番、19番」、「〕（改行）3丁目」と「]・3丁目」をそろえる
    return re.sub(r"\s+", "", nfkc(town)), re.sub(r"\s+", "", p)


# ---------------- 曜日（オープンデータ） ----------------
def read_opendata(path):
    """→ {(町名, 町丁目): {"vals": (プラ, 資源, 可燃, 不燃), "office": 清掃事務所}}。空のセルは上の行と同じ（結合セル）"""
    rows = list(xlsx.sheets(path).values())[0]
    head = [re.sub(r"\s", "", c) for c in rows[0]]
    if head[3:8] != ["プラ", "資源", "可燃ごみ", "不燃ごみ", "管轄の清掃事務所"]:
        raise ValueError(f"オープンデータの列がかわりました：{head}（calendar.py を直す）")
    out, town, prev = {}, "", ["", "", "", "", ""]
    for r in rows[1:]:
        r = (r + [""] * 8)[:8]
        if not r[2].strip():
            continue
        town = r[1].strip() or town
        cur = [r[i].strip() or prev[i - 3] for i in range(3, 8)]
        prev = cur
        out[key(town, r[2])] = {"vals": tuple(cur[:4]), "office": cur[4]}
    return out


def parse_rule(cat, text):
    """「月曜\\n木曜」→ {"w": [0, 3]}、「第2第4\\n金曜」→ {"w": [4], "n": [2, 4]}"""
    t = re.sub(r"\s", "", nfkc(text))
    m = re.fullmatch(r"第(\d)第(\d)([月火水木金土])曜", t)
    if m:
        return {"w": [WD.index(m[3])], "n": [int(m[1]), int(m[2])]}
    ws = re.findall(r"([月火水木金土])曜", t)
    if ws and re.fullmatch(r"([月火水木金土]曜)+", t):
        return {"w": [WD.index(w) for w in ws]}
    raise ValueError(f"{cat} の曜日が読めません：「{text}」")


def say(rule):
    ws = "・".join(WD[w] for w in rule["w"])
    return f"毎月{rule['n'][0]}回目・{rule['n'][1]}回目の{ws}曜日" if "n" in rule else f"毎週{ws}曜日"


def hits(rule, d):
    return d.weekday() in rule["w"] and ("n" not in rule or (d.day - 1) // 7 + 1 in rule["n"])


# ---------------- 区のページの表 ----------------
def table_rows(tb):
    """HTML の表 → 行のリスト（rowspan・colspan を広げる）"""
    grid, spans = [], {}
    for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", tb, re.S):
        row, col = [], 0
        cells = re.findall(r"<t([dh])([^>]*)>(.*?)</t[dh]>", tr, re.S)
        ci = 0
        while ci < len(cells) or col in spans:
            if col in spans:
                txt, left = spans[col]
                row.append(txt)
                spans[col] = (txt, left - 1)
                if left - 1 == 0:
                    del spans[col]
                col += 1
                continue
            _, attr, body = cells[ci]
            ci += 1
            txt = H.unescape(re.sub(r"<[^>]+>", "", re.sub(r"<br\s*/?>", "\n", body))).strip()
            rs = int((re.search(r'rowspan="(\d+)"', attr) or [0, 1])[1])
            cs = int((re.search(r'colspan="(\d+)"', attr) or [0, 1])[1])
            for _ in range(cs):
                row.append(txt)
                if rs > 1:
                    spans[col] = (txt, rs - 1)
                col += 1
        grid.append(row)
    return grid


def read_year_end(path, year):
    """年末年始の表 → [(町名, 町丁目, {区分: (年末最終日, 年始開始日)})]"""
    t = Path(path).read_text(encoding="utf-8")
    out = []
    for tb in re.findall(r"<table.*?</table>", t, re.S):
        if "年末最終日" not in tb:
            continue
        for r in table_rows(tb):
            dates = [re.fullmatch(r"(\d+)日\((.)\)", nfkc(x).replace(" ", "")) for x in r[-8:]]
            if len(r) < 10 or not all(dates):
                continue
            town, part = r[-10], r[-9]
            ds = []
            for i, m in enumerate(dates):
                y, mo = (year, 12) if i < 4 else (year + 1, 1)
                d = dt.date(y, mo, int(m[1]))     # 年末最終日は12月、年始開始日は1月（表に月は書いていない）
                if WD[d.weekday()] != m[2]:
                    raise ValueError(f"年末年始の表：{town}{part} の「{m[0]}」の曜日が合いません")
                ds.append(d.isoformat())
            out.append((town, part, {c: (ds[i], ds[i + 4]) for i, c in enumerate(CATS)}))
    if len(out) < 50:
        raise ValueError(f"年末年始の表が {len(out)} 行しか読めません（ページの形がかわった？）")
    return out


def read_funen(path, year):
    """「資源とごみの収集日」のページの不燃ごみの表 → {"第1・3月": [日付…]}。
    表は「第1第3月曜地区」（縦に結合したセル）の右に、その月の2つの日付が並ぶ形"""
    t = Path(path).read_text(encoding="utf-8")
    out = {}
    for tb in re.findall(r"<table.*?</table>", t, re.S):
        if "地区" not in tb or "月" not in tb:
            continue
        for r in table_rows(tb):
            for i, x in enumerate(r):
                m = re.fullmatch(r"第(\d)第(\d)([月火水木金土])曜地区", re.sub(r"\s", "", nfkc(x)))
                if not m:
                    continue
                for cell in r[i + 1:i + 3]:
                    mm = re.fullmatch(r"(\d+)月(\d+)日", nfkc(cell))
                    if mm:
                        mo, d = int(mm[1]), int(mm[2])
                        out.setdefault(f"第{m[1]}・{m[2]}{m[3]}", set()).add(dt.date(year if mo >= 4 else year + 1, mo, d).isoformat())
    return {k: sorted(v) for k, v in out.items()}


# ---------------- 区のサイトから取ってくる ----------------
def download(year, dest, web, plan):
    page = web.text(web.get(PAGE))
    if f"令和{year - 2018}年4月から" not in page:
        plan.problem(f"{PAGE} の不燃ごみの表が、まだ令和{year - 2018}年度ではありません")
    plan.add(PAGE, dest / "資源とごみの収集日.html", page.encode("utf-8"))
    ye = web.text(web.get(YE_PAGE))
    if f"令和{year - 2018}年度年末年始" not in ye:
        plan.problem(f"{YE_PAGE} がまだ令和{year - 2018}年度の年末年始になっていません（例年11月ごろ）")
    plan.add(YE_PAGE, dest / "年末年始のお知らせ.html", ye.encode("utf-8"))


# ---------------- 収集日を作る ----------------
def make_calendar(folder, year):
    folder = Path(folder)
    if year in YEAR_END:
        off, tentative = YEAR_END[year]["off"], False
    else:
        off = (f"{year}-{DEFAULT_OFF[0]}", f"{year + 1}-{DEFAULT_OFF[1]}")
        tentative = True
        print(f"  ！ {year}年度の年末年始がまだ calendar.py の YEAR_END にありません。12/31〜1/3 を休みとして作ります")
    od = read_opendata(folder.parent / "オープンデータ" / OPENDATA)
    ye = read_year_end(folder / "年末年始のお知らせ.html", year)
    funen = read_funen(folder / "資源とごみの収集日.html", year)
    problems, schedules, areas = [], {}, []
    for town, part, edges in ye:
        k = key(town, part)
        same = {key(*a): key(*b) for a, b in SAME_AS.items()}
        k = same.get(k, k)
        if k not in od:
            raise ValueError(f"年末年始の表の「{town} {part}」が、オープンデータの曜日の一覧にありません（町丁目の分け方がかわった？）")
        v = od[k]
        rules = {c: parse_rule(c, x) for c, x in zip(CATS, v["vals"])}
        name = "／".join(f"{c}:{say(rules[c])}" for c in CATS)
        if name not in schedules:
            days = {}
            d, end = dt.date(year, 4, 1), dt.date(year + 1, 3, 31)
            while d <= end:
                kk = d.isoformat()
                if not (off[0] <= kk <= off[1]):
                    cs = [c for c in CATS if hits(rules[c], d)]
                    if cs:
                        days[kk] = cs
                d += dt.timedelta(days=1)
            schedules[name] = {"rules": {c: say(rules[c]) for c in CATS}, "days": days, "moved": {}}
        days = schedules[name]["days"]
        for c in CATS:
            last = max(x for x, cs in days.items() if c in cs and x < off[0])
            first = min(x for x, cs in days.items() if c in cs and x > off[1])
            if (last, first) != edges[c]:
                problems.append(f"{town}{part}：{c} 年末最終日・年始開始日 表 {edges[c]}／曜日から {last, first}")
        p = nfkc(part).replace("～", "〜").replace("から", "〜")
        n = town if p.startswith("全域") else f"{town}{p}"
        n = re.sub(r"\s*\n\s*", "・", n)
        a = {"n": n, "s": name, "y": kana.yomi(town)}
        if v["office"]:
            a["d"] = OFFICE.get(re.sub(r"\s", "", v["office"]), v["office"] + "清掃事務所")
        areas.append(a)
    # 不燃ごみの日付の表とくらべる
    for g, ds in funen.items():
        m = re.fullmatch(r"第(\d)・(\d)(.)", g)
        rule = {"w": [WD.index(m[3])], "n": [int(m[1]), int(m[2])]}
        want = sorted(x.isoformat() for x in (dt.date(year, 4, 1) + dt.timedelta(days=i) for i in range(366))
                      if x <= dt.date(year + 1, 3, 31) and hits(rule, x) and not (off[0] <= x.isoformat() <= off[1]))
        if ds != want:
            problems.append(f"不燃ごみ {g}：ページの日付と曜日から作った日がちがう（{sorted(set(ds) ^ set(want))}）")
    print(f"大田区：地区 {len(areas)}・収集日の組み合わせ {len(schedules)}・不燃ごみの日付の表 {len(funen)}グループ")
    if problems:
        for p in problems:
            print("  ！", p)
        raise ValueError(f"区の表と合わないところが {len(problems)} あります")
    return {"year": year, "schedules": schedules, "areas": areas,
            "yearEnd": {"off": list(off), "tentative": tentative}}
