"""東京都 品川区（13109）：区の「収集曜日一覧」（町名の行ごとの HTML の表 7ページ）から収集日データを作る。

このファイルのきまり（どの自治体も同じ形。tools/update_year.py・download_sources.py から使う）:
  NEED                       … 元データ/<県>/<自治体>/<年度>年度/ に置くファイルの名前
  download(year, dest, web, plan) … 区のサイトから NEED のファイルを探して plan に入れる（web は tools/lib/web.py）
  make_calendar(src, year)   … src（上のフォルダ）のファイルから収集日データ（dict）を作る。読めなければ例外で止める

品川区の収集日は、町名・丁目（一部は番地・号棟）ごとに曜日で決まる。
  燃やすごみ 週2回（一部 週3回）・陶器・ガラス・金属ごみ 月2回（第1・第3 か 第2・第4 の曜日）・資源 週1回。
  祝日も収集する（令和7年度の年末年始のお知らせで、成人の日 1/12 も「第2・4月曜」の収集日になっている）。
  ・曜日：区のページ「ごみ・資源収集日」の【あ行】〜【や行】の収集曜日一覧（HTML の表。町名・丁目・番地・号・燃やすごみ・陶器・ガラス・金属・資源）。
    区の「令和8年版ごみ・リサイクルカレンダー」（PDF、画像）p.13〜15 の収集曜日一覧と同じであることを画像で見た。
  ・年末年始：区のお知らせ「令和○年度 年末年始の資源・ごみ収集」（PDF、画像）の、区分・曜日ごとの「12月終わりの収集日」「1月始めの収集日」を
    YEAR_END の "table" に書き写す。八潮5丁目・大森駅前住宅（南大井6丁目18番）はお知らせが別なので "special" に書く。
    書くまでは、その年の年末年始（TENTATIVE の期間）を「未定」にして、日を入れない（決まり A1。推測しない）。

フォルダ（元データ/13_東京都/13109_品川区/<年度>年度/）に置くもの:
  収集日.html        … https://www.city.shinagawa.tokyo.jp/kurashi/gomi/1009407/1003963/index.html
  曜日/<ページ番号>.html … 上のページの【あ行】〜【や行】収集曜日一覧（1003964〜1003970）
  （見くらべ用に、カレンダー.pdf（ごみ・リサイクルカレンダー）・年末年始/（お知らせの PDF）も置いた）
"""
import datetime as dt
import html
import re
import sys
import unicodedata
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "lib"))
import kana  # noqa: E402

SITE = "https://www.city.shinagawa.tokyo.jp"
LIST_PAGE = SITE + "/kurashi/gomi/1009407/1003963/index.html"
PAGES = ["1003964", "1003965", "1003966", "1003967", "1003968", "1003969", "1003970"]
NEED = ["収集日.html"] + [f"曜日/{p}.html" for p in PAGES]
WD = "月火水木金土日"
CATS = ["燃やす", "資源", "陶器"]
HEAD = {"燃やすごみ": "燃やす", "陶器・ガラス・金属": "陶器", "資源": "資源"}

# 年末年始。tentative＝区がまだ発表していない（その期間は「未定」）。
# 発表されたら、お知らせの表を書き写す："table" {区分: {"月・木" や "第1・3月" や "月": ("12月の最後の日", "1月の最初の日")}}、
#   "special" {地区名の一部: {区分: {曜日: (最後, 最初)}}}（八潮5丁目・大森駅前住宅のお知らせ）。
#   収集日は、ふだんの曜日の日から「最後の日」より後・「最初の日」より前の日をのぞいたもの。
YEAR_END = {
    2026: {"tentative": True, "off": ("2026-12-28", "2027-01-04"),
           "src": "令和8年度の年末年始のお知らせは、まだ出ていない（2026-11-27。区のページは令和7年度のまま）"},
}
TENTATIVE = ("12-28", "01-04")   # YEAR_END にない年度の「未定」の期間（令和7年度は、ふだんとちがったのが 12/28〜1/4 の間だけ）

# 地区の読み（pykakasi では読みちがえる町名。郵便番号一覧の読みで確かめた）
YOMI = {
    "荏原": "えばら",
    "勝島": "かつしま",
    "小山": "こやま",
    "戸越": "とごし",
    "中延": "なかのぶ",
    "西中延": "にしなかのぶ",
    "東中延": "ひがしなかのぶ",
}


def nfkc(s):
    return unicodedata.normalize("NFKC", s).replace("～", "〜").replace("~", "〜").replace("　", " ").strip()


def cell(s):
    return nfkc(html.unescape(re.sub(r"<[^>]+>", "", s)))


def read_table(path):
    """収集曜日一覧の HTML → [{"town", "chome", "note", "燃やす", "陶器", "資源"}]"""
    t = Path(path).read_text(encoding="utf-8")
    tabs = re.findall(r"<table.*?</table>", t, re.S)
    if len(tabs) != 1:
        raise ValueError(f"{path} の表が {len(tabs)} こ（1こではない）")
    rows = [[cell(c) for c in re.findall(r"<t[hd][^>]*>(.*?)</t[hd]>", tr, re.S)]
            for tr in re.findall(r"<tr.*?</tr>", tabs[0], re.S)]
    head, out = rows[0], []
    want = ["町名", "丁目"] + (["番地・号"] if "番地・号" in head else []) + list(HEAD)
    if head != want:
        raise ValueError(f"{path} の表の見出しがかわりました：{head}（calendar.py を直す）")
    for r in rows[1:]:
        if "rowspan" in r or len(r) != len(head):
            raise ValueError(f"{path} の行の形がおかしい：{r}")
        d = dict(zip(head, r))
        note = d.get("番地・号", "")
        out.append({"town": d["町名"], "chome": d["丁目"], "note": "" if note in ("", "(空欄)") else note,
                    **{HEAD[k]: d[k] for k in HEAD}})
    return out


def parse_rule(cat, s):
    """「月曜日、木曜日」→ {(0, None), (3, None)}、「第1土曜日、第3土曜日」→ {(5, 1), (5, 3)}"""
    out = set()
    for part in s.split("、"):
        m = re.fullmatch(r"(?:第(\d))?([月火水木金土日])曜日", part.strip())
        if not m:
            raise ValueError(f"{cat}の曜日が読めない：{s}")
        out.add((WD.index(m[2]), int(m[1]) if m[1] else None))
    if cat == "陶器" and any(k is None for _, k in out) or cat != "陶器" and any(k for _, k in out):
        raise ValueError(f"{cat}の曜日の形がいつもとちがう：{s}")
    return frozenset(out)


def say(rule):
    """{(5,1),(5,3)} →「第1・3土」、{(0,None),(3,None)} →「月・木」（年末年始のお知らせの書き方）"""
    ks = sorted(k for _, k in rule if k)
    ws = sorted({w for w, _ in rule})
    return (f"第{'・'.join(map(str, ks))}" if ks else "") + "・".join(WD[w] for w in ws)


def say_long(cat, rule):
    if cat == "陶器":
        return f"{say(rule)}曜日（月2回）"
    return f"毎週{say(rule)}曜日"


def hits(rule, d):
    return any(d.weekday() == w and (k is None or (d.day - 1) // 7 + 1 == k) for w, k in rule)


def chome_text(s):
    """「2丁目、3丁目、4丁目」→「2〜4丁目」、「1丁目、2丁目、4丁目」→「1・2・4丁目」（区のカレンダーの書き方）"""
    ns = [int(x) for x in re.findall(r"(\d+)丁目", s)]
    if not ns or len(ns) != s.count("丁目"):
        raise ValueError(f"丁目が読めない：{s}")
    if len(ns) >= 3 and ns == list(range(ns[0], ns[-1] + 1)):
        return f"{ns[0]}〜{ns[-1]}丁目"
    return "・".join(map(str, ns)) + "丁目"


def note_text(note, prev):
    """番地・号の説明。「上記以外」「1番以外」は、何以外かがわかる書き方にする"""
    note = note.replace("から", "〜")
    note = re.sub(r"\((.*?)\)", lambda m: "・" + m.group(1), note)     # 「18番(大森駅前住宅)」→「18番・大森駅前住宅」
    if note == "上記以外":
        return f"{prev}以外"
    return note


# ---------------- 区のサイトから取ってくる ----------------
def download(year, dest, web, plan):
    raw = web.get(LIST_PAGE)
    page = web.text(raw)
    plan.add(LIST_PAGE, dest / "収集日.html", raw)
    found = {u.rsplit("/", 1)[-1].replace(".html", ""): u for u, t in web.links(page, LIST_PAGE) if "収集曜日一覧" in t}
    for p in PAGES:
        if p in found:
            plan.add(found[p], dest / "曜日" / f"{p}.html")
        else:
            plan.problem(f"{LIST_PAGE} に収集曜日一覧のページ {p} がありません（ページが変わった？ calendar.py の PAGES を直す）")


# ---------------- 収集日を作る ----------------
def make_calendar(folder, year):
    folder = Path(folder)
    ye = YEAR_END.get(year)
    if ye is None:
        ye = {"tentative": True, "off": (f"{year}-{TENTATIVE[0]}", f"{year + 1}-{TENTATIVE[1]}")}
        print(f"  ！ {year}年度の年末年始がまだ calendar.py の YEAR_END にありません。{TENTATIVE[0]}〜{TENTATIVE[1]} を「未定」にして作ります")
    off, tentative = ye["off"], ye.get("tentative", False)
    rows = []
    for p in PAGES:
        rows += read_table(folder / "曜日" / f"{p}.html")
    problems, schedules, areas = [], {}, []
    prev = {}
    for r in rows:
        rules = {c: parse_rule(c, r[c]) for c in CATS}
        name = "／".join(f"{c}:{say(rules[c])}" for c in CATS)
        special = next((k for k in ye.get("special", {}) if k in r["town"] + chome_text(r["chome"]) + r["note"]), None)
        if special:
            name += f"／{special}"
        if name not in schedules:
            table = ye.get("special", {}).get(special) if special else ye.get("table")
            days = {}
            d, end = dt.date(year, 4, 1), dt.date(year + 1, 3, 31)
            while d <= end:
                k = d.isoformat()
                cs = [c for c in CATS if hits(rules[c], d)]
                if off[0] <= k <= off[1]:
                    if tentative:
                        cs = []
                    else:
                        cs = [c for c in cs if not (table[c][say(rules[c])][0] < k < table[c][say(rules[c])][1])]
                if cs:
                    days[k] = cs
                d += dt.timedelta(days=1)
            if not tentative:
                for c in CATS:
                    last = max((x for x, cs in days.items() if c in cs and x < f"{year + 1}-01-01"), default=None)
                    first = min((x for x, cs in days.items() if c in cs and x > f"{year}-12-31"), default=None)
                    if (last, first) != tuple(table[c][say(rules[c])]):
                        problems.append(f"{name} {c}：年末年始の表 {table[c][say(rules[c])]}／作った日 {(last, first)}")
            schedules[name] = {"rules": {c: say_long(c, rules[c]) for c in CATS}, "days": days, "moved": {}}
        key = (r["town"], r["chome"])
        n = r["town"] + chome_text(r["chome"])
        if r["note"]:
            n += f"（{note_text(r['note'], prev.get(key, ''))}）"
            prev[key] = note_text(r["note"], "")
        areas.append({"n": n, "s": name, "y": YOMI.get(r["town"]) or kana.yomi(r["town"])})
    names = [a["n"] for a in areas]
    dup = {x for x in names if names.count(x) > 1}
    if dup:
        problems.append(f"同じ名前の地区：{dup}")
    print(f"品川区：地区 {len(areas)}・収集日の組み合わせ {len(schedules)}・年末年始 {'未定' if tentative else '発表ずみ'}（{off[0]}〜{off[1]}）")
    if problems:
        for p in problems[:40]:
            print("  ！", p)
        raise ValueError(f"区の表と合わないところが {len(problems)} あります")
    return {"year": year, "schedules": schedules, "areas": areas,
            "yearEnd": {"off": list(off), "tentative": tentative}}
