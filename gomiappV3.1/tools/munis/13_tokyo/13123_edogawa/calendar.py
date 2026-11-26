"""東京都 江戸川区（13123）：区のページ「ごみ収集・資源回収地域別曜日表」と「年末・年始のごみ収集・資源回収のお知らせ」から収集日データを作る。

このファイルのきまり（どの自治体も同じ形。tools/update_year.py・download_sources.py から使う）:
  NEED                       … 元データ/<県>/<自治体>/<年度>年度/ に置くファイルの名前
  download(year, dest, web, plan) … 区のサイトから NEED のファイルを探して plan に入れる（web は tools/lib/web.py）
  make_calendar(src, year)   … src（上のフォルダ）のファイルから収集日データ（dict）を作る。読めなければ例外で止める

江戸川区の収集日は、町丁目（番地・建物で分かれるところもある）ごとに曜日で決まっている。
  資源（古紙・びん・缶・ペットボトル・容器包装プラスチック）週1回・燃やすごみ 週2回・燃やさないごみ 月2回（第1・3か第2・4の○曜日。第5曜日は収集なし）。
  祝日も収集する。年末年始だけ休み（令和8年度：12月31日〜1月3日）。
  ・曜日と地区：「ごみ収集・資源回収地域別曜日表」の6つの表（町名の列は縦に結合したセル）。
  ・年末年始の表は、曜日ごと（燃やすごみ3・資源6・燃やさないごみ12）の「年内収集作業最終日」「年始収集作業開始日」。
    曜日から作った日と、すべての曜日で合うか確かめる（合わなければ止まる）。

フォルダ（元データ/13_東京都/13123_江戸川区/<年度>年度/）に置くもの:
  曜日表.html              … https://www.city.edogawa.tokyo.jp/e025/kurashi/gomi_recycle/kategomi/yobihyo.html
  年末年始のお知らせ.html  … https://www.city.edogawa.tokyo.jp/e025/kurashi/gomi_recycle/topics/nenmatukaisyu.html（例年11月ごろ更新）
"""
import datetime as dt
import html as H
import re
import sys
import unicodedata
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "lib"))
import kana  # noqa: E402

SITE = "https://www.city.edogawa.tokyo.jp"
PAGE = SITE + "/e025/kurashi/gomi_recycle/kategomi/yobihyo.html"
YE_PAGE = SITE + "/e025/kurashi/gomi_recycle/topics/nenmatukaisyu.html"
NEED = ["曜日表.html", "年末年始のお知らせ.html"]
PERENNIAL = True
CATS = ["資源", "燃やす", "燃やさない"]
HEAD = {"資源": "資源", "燃やすごみ": "燃やす", "燃やさないごみ": "燃やさない"}
WD = "月火水木金土日"
OFFICE = {"小松川": "小松川清掃分室", "小岩": "小岩清掃事務所", "葛西": "葛西清掃事務所"}

# 年末年始：off＝収集しない日（両端をふくむ）
YEAR_END = {
    2026: {"off": ("2026-12-31", "2027-01-03"), "src": "2026年(令和8年)度年末・年始のごみ収集・資源回収のお知らせ（2026-11-16 更新）「令和8年12月31日(木曜日)から令和9年1月3日(日曜日)までお休みします」"},
}
DEFAULT_OFF = ("12-31", "01-03")

# 地区の読み（pykakasi では読みちがえる町名。郵便番号一覧の読みで確かめた）
YOMI = {"上一色": "かみいっしき", "上篠崎": "かみしのざき", "下篠崎町": "しもしのざきまち", "北葛西": "きたかさい",
        "宇喜田町": "うきたちょう", "新堀": "にいほり", "春江町": "はるえちょう", "本一色": "ほんいっしき",
        "東葛西": "ひがしかさい", "清新町": "せいしんちょう", "臨海町": "りんかいちょう", "興宮町": "おきのみやちょう",
        "西小松川町": "にしこまつがわちょう", "谷河内": "やごうち", "鹿骨": "ししぼね", "鹿骨町": "ししぼねちょう"}
# 町名を正式な町名に直すもの（決まり A3。郵便番号一覧・e-Stat の町名と1字だけちがう）
FIX = {"西小松川": "西小松川町"}


def nfkc(s):
    return unicodedata.normalize("NFKC", s).strip()


def table_rows(tb):
    """HTML の表 → 行のリスト（rowspan・colspan を広げる。大田区と同じ）"""
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


# ---------------- 曜日 ----------------
def parse_rule(cat, text):
    """「月曜日」→ {"w": [0]}、「水曜日・土曜日」→ {"w": [2, 5]}、「第1・3金曜日」→ {"w": [4], "n": [1, 3]}"""
    t = re.sub(r"\s", "", nfkc(text))
    m = re.fullmatch(r"第(\d)・(?:第)?(\d)([月火水木金土])曜日?", t)
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


def paren(s):
    """「(1から10)」→「（1〜10）」"""
    s = nfkc(s).replace("から", "〜").replace("～", "〜").replace("~", "〜")
    return s.replace("(", "（").replace(")", "）")


def read_table(path):
    """曜日表 → [{"town", "part", "vals": {区分: 文}, "office"}]。収集のない行（臨海町3丁目「-」）は飛ばす"""
    t = Path(path).read_text(encoding="utf-8-sig")
    out, skipped = [], []
    for tb in re.findall(r"<table.*?</table>", t, re.S):
        if "管轄" not in tb:
            continue
        for r in table_rows(tb):
            if len(r) != 6 or r[0] == "地域":
                continue
            town, part = r[0], r[1]
            if r[2].strip() == "-":
                skipped.append(nfkc(town) + nfkc(part))
                continue
            vals = {}
            for cell in r[2:5]:
                head, _, body = cell.partition("\n")
                c = HEAD.get(head.strip())
                if not c:
                    raise ValueError(f"曜日表の「{cell}」の区分が読めません（{town}{part}）")
                vals[c] = body.strip()
            office = r[5].replace("管轄", "").strip()
            out.append({"town": town, "part": part, "vals": vals, "office": office})
    if len(out) < 100:
        raise ValueError(f"曜日表が {len(out)} 行しか読めません（ページの形がかわった？）")
    return out, skipped


def area_name(town, part):
    """「清新町\\n1丁目」「（1）清新中央ハイツ・清新南ハイツ」→「清新町1丁目（1）清新中央ハイツ・清新南ハイツ」"""
    town = re.sub(r"\s+", "", nfkc(town))
    town = FIX.get(town, town)
    p = ""
    for x in (x.strip() for x in paren(part).split("\n")):
        if x:   # 改行のところは、そのままつなぐ（建物の番号「（4）シティコープ…」の前だけ「・」）
            p += ("・" if p and re.match(r"（\d）\D", x) else "") + x
    if p == "全域":
        return town
    return town + ("　" if town.endswith("丁目") and not p.startswith("（") else "") + p


def town_only(town):
    """「清新町\\n1丁目」→「清新町」"""
    t = re.sub(r"\d+丁目$", "", re.sub(r"\s+", "", nfkc(town)))
    return FIX.get(t, t)


# ---------------- 年末年始 ----------------
def read_year_end(path, year):
    """年末年始の表 → {区分: {曜日の書き方（say と同じ）: (年内最終日, 年始開始日)}}"""
    t = Path(path).read_text(encoding="utf-8-sig")
    if f"令和{year - 2018}年" not in t:
        raise ValueError(f"年末年始のお知らせが令和{year - 2018}年度のものではありません")
    out = {}
    for tb in re.findall(r"<table.*?</table>", t, re.S):
        rows = table_rows(tb)
        if not rows or "年内収集作業最終日" not in "".join(rows[0]):
            continue
        for r in rows[1:]:
            if len(r) < 3:
                continue
            m1 = re.search(r"(\d+)月(\d+)日", nfkc(r[1]))
            m2 = re.search(r"(\d+)月(\d+)日", nfkc(r[2]))
            if not (m1 and m2):
                continue
            last = dt.date(year, int(m1[1]), int(m1[2])).isoformat()
            first = dt.date(year + 1, int(m2[1]), int(m2[2])).isoformat()
            w = re.sub(r"\s", "", nfkc(r[0])).replace("第2・第4", "第2・4").replace("第1・第3", "第1・3")
            if w.startswith("第"):
                c = "燃やさない"
            elif "・" in w:
                c = "燃やす"
            else:
                c = "資源"
            out.setdefault(c, {})[say(parse_rule(c, w if w.startswith("第") or "・" in w else w))] = (last, first)
    n = {c: len(v) for c, v in out.items()}
    if n != {"燃やす": 3, "資源": 6, "燃やさない": 12}:
        raise ValueError(f"年末年始の表が読めません（読めた数：{n}）")
    return out


# ---------------- 区のサイトから取ってくる ----------------
def download(year, dest, web, plan):
    page = web.text(web.get(PAGE))
    if "資源回収・ごみ収集地域別曜日表" not in page:
        plan.problem(f"{PAGE} の曜日表が見つかりません（ページがかわった？）")
    plan.add(PAGE, dest / "曜日表.html", page.encode("utf-8"))
    ye = web.text(web.get(YE_PAGE))
    if f"令和{year - 2018}年)度年末・年始" not in ye:
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
    rows, skipped = read_table(folder / "曜日表.html")
    ye = read_year_end(folder / "年末年始のお知らせ.html", year) if not tentative else {}
    problems, schedules, areas = [], {}, []
    used = {c: set() for c in CATS}
    for r in rows:
        rules = {c: parse_rule(c, r["vals"][c]) for c in CATS}
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
            for c in CATS:
                used[c].add(say(rules[c]))
                if ye:
                    dd = schedules[name]["days"]
                    last = max(x for x, cs in dd.items() if c in cs and x < off[0])
                    first = min(x for x, cs in dd.items() if c in cs and x > off[1])
                    want = ye[c].get(say(rules[c]))
                    if want != (last, first):
                        problems.append(f"{c} {say(rules[c])}：年末年始の表 {want}／曜日から {last, first}")
        n = area_name(r["town"], r["part"])
        town = town_only(r["town"])
        a = {"n": n, "s": name, "y": YOMI.get(town) or kana.yomi(town)}
        if r["office"]:
            a["d"] = OFFICE.get(r["office"], r["office"])
        areas.append(a)
    if ye:
        for c in CATS:
            extra = set(ye[c]) - used[c]
            if extra:
                print(f"  （年末年始の表にあって、曜日表で使っていない {c}：{'、'.join(sorted(extra))}）")
    names = [a["n"] for a in areas]
    dup = {x for x in names if names.count(x) > 1}
    if dup:
        problems.append(f"同じ名前の地区：{dup}")
    print(f"江戸川区：地区 {len(areas)}・収集日の組み合わせ {len(schedules)}・収集のない行 {skipped}")
    if problems:
        for p in problems:
            print("  ！", p)
        raise ValueError(f"区の表と合わないところが {len(problems)} あります")
    return {"year": year, "schedules": schedules, "areas": areas,
            "yearEnd": {"off": list(off), "tentative": tentative}}
