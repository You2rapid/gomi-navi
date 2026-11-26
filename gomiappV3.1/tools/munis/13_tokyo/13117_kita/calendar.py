"""東京都 北区（13117）：区のページ「ごみ・資源の収集日」（町名・地区ごとの曜日の HTML の表）から収集日データを作る。

このファイルのきまり（どの自治体も同じ形。tools/update_year.py・download_sources.py から使う）:
  NEED                       … 元データ/<県>/<自治体>/<年度>年度/ に置くファイルの名前
  download(year, dest, web, plan) … 区のサイトから NEED のファイルを探して plan に入れる（web は tools/lib/web.py）
  make_calendar(src, year)   … src（上のフォルダ）のファイルから収集日データ（dict）を作る。読めなければ例外で止める

北区の収集日は、町名・丁目（一部は番地・団地）ごとに曜日で決まる。
  可燃ごみ 週2回・不燃ごみ（金属資源もいっしょ）月2回（第1・第3 か 第2・第4 の曜日）・古紙・プラスチック 週1回（同じ日）・
  びん・缶・ペットボトル 週1回（ステーション）。月〜土に収集し、祝日も収集する。日曜日と年末年始（12/31〜1/3）は休み。
  ・曜日：区のページ「ごみ・資源の収集日」の表（赤羽地区・王子地区・滝野川地区。町ごとに表が分かれる）。
    区の冊子「令和8年度版 家庭ごみ・資源の分け方出し方」p.1〜3 の収集曜日一覧表と同じであることを見た（README）。
  ・3つの団地（都市機構赤羽北二丁目団地・王子五丁目団地・豊島五丁目団地）は、一部の区分が「集積所の表示板に記載」で、
    曜日が公表されていない。その区分は日を入れず、rules に「集積所の表示板で確かめる」と書く（決まり A1。推測しない）。
    王子五丁目団地の古紙は「集団回収」なので、古紙・プラスチックの日（火曜日）はプラスチックだけ。
  ・年末年始：区のお知らせ「年末年始のごみ・資源の収集」（毎年11月ごろ）の「○月○日（○曜日）まで曜日どおり」「○月○日（○曜日）から曜日どおり」を
    ページから読む（曜日も合っているか確かめる）。その年度のお知らせがまだなければ、12/31〜1/3 を「未定」にして日を入れない。

フォルダ（元データ/13_東京都/13117_北区/<年度>年度/）に置くもの:
  収集日.html   … https://www.city.kita.lg.jp/living/bins/1002013/1002014.html
  年末年始.html … https://www.city.kita.lg.jp/living/bins/1018220/1024916.html （ページ番号はかわることがある。お知らせの一覧から探す）
"""
import datetime as dt
import html
import re
import sys
import unicodedata
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "lib"))
import kana  # noqa: E402

SITE = "https://www.city.kita.lg.jp"
DAYS_PAGE = SITE + "/living/bins/1002013/1002014.html"
NEWS_PAGE = SITE + "/living/bins/1018220/index.html"     # ごみ・リサイクルに関するお知らせ（年末年始のページがここにある）
NEED = ["収集日.html", "年末年始.html"]
WD = "月火水木金土日"
CATS = ["可燃", "不燃", "古紙プラ", "びん缶ペット"]
HEAD = ["町名", "地区", "可燃ごみ", "不燃ごみ", "古紙・プラスチック", "びん・缶・ペットボトル"]
REGIONS = ["赤羽", "王子", "滝野川"]
BOARD = "集積所の表示板に記載"
# 年末年始のお知らせの区分の名前 → アプリの区分
YE_CAT = {"可燃ごみ": "可燃", "不燃ごみ": "不燃", "古紙・プラスチック": "古紙プラ", "びん・缶・ペットボトル": "びん缶ペット"}
TENTATIVE = ("12-31", "01-03")   # お知らせがまだのとき「未定」にする期間（区のページ：年末年始（12月31日から1月3日）は収集していません）

# 地区の読み（pykakasi では読みちがえる町名。郵便番号一覧の読みで確かめた）
YOMI = {
    "上中里": "かみなかざと", "上十条": "かみじゅうじょう", "岸町": "きしまち", "昭和町": "しょうわまち", "東田端": "ひがしたばた",
    "栄町": "さかえちょう", "桐ケ丘": "きりがおか", "西ケ原": "にしがはら", "豊島": "としま",
}


def nfkc(s):
    return unicodedata.normalize("NFKC", s).replace("～", "〜").replace("~", "〜").replace("　", " ").strip()


def cell(s):
    return re.sub(r"\s+", "", nfkc(html.unescape(re.sub(r"<[^>]+>", "", s))))


def read_table(path):
    """収集日の HTML → [{"region", "town", "chiku", 可燃…}]"""
    t = Path(path).read_text(encoding="utf-8")
    t = re.search(r"<main.*?</main>", t, re.S)[0]
    out, region = [], None
    for m in re.finditer(r"<h2[^>]*>(.*?)</h2>|<table.*?</table>", t, re.S):
        if m[1] is not None:
            h = cell(m[1])
            region = h[:-2] if h.endswith("地区") and h[:-2] in REGIONS else None
            continue
        if region is None:
            raise ValueError(f"{path}：地区（赤羽・王子・滝野川）の見出しの外に表があります（ページの形がかわった？）")
        rows = [[cell(c) for c in re.findall(r"<t[hd][^>]*>(.*?)</t[hd]>", tr, re.S)]
                for tr in re.findall(r"<tr.*?</tr>", m[0], re.S)]
        head = ["びん・缶・ペットボトル" if h == "びん・缶・ペットボト" else h for h in rows[0]]
        if re.search(r"rowspan|colspan", m[0]) or head != HEAD:     # 7つの表の見出しは「ペットボト」（区のページの書きまちがい）
            raise ValueError(f"{path} の表の形がかわりました：{rows[0]}（calendar.py を直す）")
        for r in rows[1:]:
            if len(r) != len(HEAD):
                raise ValueError(f"{path} の行の形がおかしい：{r}")
            out.append({"region": region, "town": r[0], "chiku": r[1], **dict(zip(CATS, r[2:]))})
    return out


def parse_rule(cat, s):
    """「月曜日・木曜日」→ {(0, None), (3, None)}、「第1・第3土曜日」→ {(5, 1), (5, 3)}。
    「集積所の表示板に記載」→ None（曜日が公表されていない）。王子五丁目団地の「集団回収(古紙)火曜日(プラスチック)」→ プラスチックの曜日"""
    if s == BOARD:
        return None
    m = re.fullmatch(r"集団回収\(古紙\)([月火水木金土])曜日\(プラスチック\)", s)
    if m and cat == "古紙プラ":
        return frozenset({(WD.index(m[1]), None)})
    m = re.fullmatch(r"第(\d)・第(\d)([月火水木金土])曜日", s)
    if m:
        if cat != "不燃":
            raise ValueError(f"{cat}の曜日の形がいつもとちがう：{s}")
        return frozenset({(WD.index(m[3]), int(m[1])), (WD.index(m[3]), int(m[2]))})
    out = set()
    for part in s.split("・"):
        m = re.fullmatch(r"([月火水木金土])曜日", part)
        if not m:
            raise ValueError(f"{cat}の曜日が読めない：{s}")
        out.add((WD.index(m[1]), None))
    if cat == "不燃":
        raise ValueError(f"不燃ごみの曜日の形がいつもとちがう：{s}")
    return frozenset(out)


def say(rule):
    """{(5,1),(5,3)} →「第1・3土」、{(0,None),(3,None)} →「月・木」"""
    if rule is None:
        return "表示板"
    ks = sorted(k for _, k in rule if k)
    ws = sorted({w for w, _ in rule})
    return (f"第{'・'.join(map(str, ks))}" if ks else "") + "・".join(WD[w] for w in ws)


def say_long(cat, rule, raw):
    if rule is None:
        return "曜日は集積所の表示板で確かめてください"
    if raw.startswith("集団回収"):
        return f"毎週{say(rule)}曜日（プラスチックだけ。古紙は集団回収）"
    if cat == "不燃":
        return f"{say(rule)}曜日（月2回）"
    return f"毎週{say(rule)}曜日"


def hits(rule, d):
    return any(d.weekday() == w and (k is None or (d.day - 1) // 7 + 1 == k) for w, k in rule)


def read_year_end(path, year):
    """年末年始のお知らせのページ → {区分: ("12月の最後の日", "1月の最初の日")}。その年度のお知らせでなければ None"""
    p = Path(path)
    if not p.exists():
        return None
    t = cell(re.search(r"<main.*?</main>", p.read_text(encoding="utf-8"), re.S)[0])
    out = {}
    for name, cat in YE_CAT.items():
        m = re.search(re.escape(name) + r"の年末の(?:収集|回収)作業については、(\d+)月(\d+)日\((.)曜日\)まで曜日どおり", t)
        n = re.search(re.escape(name) + r"の年始の(?:収集|回収)作業については、(\d+)月(\d+)日\((.)曜日\)から曜日どおり", t)
        if not (m and n):
            raise ValueError(f"{p}：{name}の年末・年始の日が読めません（ページの書き方がかわった？ calendar.py を直す）")
        last, first = dt.date(year, int(m[1]), int(m[2])), dt.date(year + 1, int(n[1]), int(n[2]))
        if WD[last.weekday()] != m[3] or WD[first.weekday()] != n[3]:
            return None     # 曜日が合わない＝ほかの年度のお知らせ
        out[cat] = (last.isoformat(), first.isoformat())
    return out


def town_base(town):
    return re.sub(r"[一二三四五六七八九十]+丁目$", "", town)


def area_name(r):
    if r["chiku"] == "全域":
        return r["town"]
    return f"{r['town']}（{r['chiku']}）"     # 「(1〜3番・10番)の一部」のかっこは、意味がかわるので残す


# ---------------- 区のサイトから取ってくる ----------------
def download(year, dest, web, plan):
    plan.add(DAYS_PAGE, dest / "収集日.html")
    page = web.text(web.get(NEWS_PAGE))
    found = [u for u, t in web.links(page, NEWS_PAGE) if "年末年始" in t and "収集" in t]
    if found:
        plan.add(found[0], dest / "年末年始.html")
    else:
        plan.problem(f"{NEWS_PAGE} に年末年始の収集のお知らせがありません（11月ごろに出る。出るまでは 12/31〜1/3 が「未定」）")


# ---------------- 収集日を作る ----------------
def make_calendar(folder, year):
    folder = Path(folder)
    table = read_year_end(folder / "年末年始.html", year)
    tentative = table is None
    if tentative:
        print(f"  ！ {year}年度の年末年始のお知らせ（年末年始.html）がありません。{TENTATIVE[0]}〜{TENTATIVE[1]} を「未定」にして作ります")
    off = (f"{year}-{TENTATIVE[0]}", f"{year + 1}-{TENTATIVE[1]}")     # 区の休み（お知らせが出たら、その前後の日も表で決める）
    rows = read_table(folder / "収集日.html")
    problems, schedules, areas = [], {}, []
    for r in rows:
        rules = {c: parse_rule(c, r[c]) for c in CATS}
        name = "／".join(f"{c}:{say(rules[c])}" for c in CATS)
        if r["古紙プラ"].startswith("集団回収"):
            name += "（プラだけ）"
        if name not in schedules:
            days = {}
            d, end = dt.date(year, 4, 1), dt.date(year + 1, 3, 31)
            while d <= end:
                k = d.isoformat()
                cs = [c for c in CATS if rules[c] is not None and d.weekday() != 6 and hits(rules[c], d)]
                if tentative and off[0] <= k <= off[1]:
                    cs = []
                elif not tentative:
                    cs = [c for c in cs if not (table[c][0] < k < table[c][1])]
                if cs:
                    days[k] = cs
                d += dt.timedelta(days=1)
            # 年末年始のお知らせと見くらべる：12月の最後の日は「まで」の日より後でない、1月の最初の日は「から」の日より前でない、
            # 区の休み（12/31〜1/3）に日がない
            for k in days:
                if f"{year}-12-31" <= k <= f"{year + 1}-01-03":
                    problems.append(f"{name}：区の休みの日 {k} に収集日があります")
            if not tentative:
                for c in CATS:
                    if rules[c] is None:
                        continue
                    last = max((x for x, cs in days.items() if c in cs and x < f"{year + 1}-01-01"), default="")
                    first = min((x for x, cs in days.items() if c in cs and x > f"{year}-12-31"), default="")
                    if last > table[c][0] or first < table[c][1] or (first, last) == ("", ""):
                        problems.append(f"{name} {c}：お知らせ {table[c]}／作った日 {(last, first)}")
            schedules[name] = {"rules": {c: say_long(c, rules[c], r[c]) for c in CATS}, "days": days, "moved": {}}
        a = {"n": area_name(r), "r": r["region"], "s": name,
             "y": YOMI.get(town_base(r["town"])) or kana.yomi(town_base(r["town"]))}
        unknown = [c for c in CATS if rules[c] is None]
        if unknown:
            long = {"可燃": "可燃ごみ", "不燃": "不燃ごみ"}
            a["d"] = "・".join(long[c] for c in unknown) + "の曜日は、集積所の表示板で確かめてください"
            if r["古紙プラ"].startswith("集団回収"):
                a["d"] += "。古紙は集団回収（区の古紙の回収はありません）"
        areas.append(a)
    names = [a["n"] for a in areas]
    dup = {x for x in names if names.count(x) > 1}
    if dup:
        problems.append(f"同じ名前の地区：{dup}")
    print(f"北区：地区 {len(areas)}・収集日の組み合わせ {len(schedules)}・年末年始 {'未定' if tentative else '発表ずみ'}（{off[0]}〜{off[1]}）")
    if problems:
        for p in problems[:40]:
            print("  ！", p)
        raise ValueError(f"区の表と合わないところが {len(problems)} あります")
    return {"year": year, "schedules": schedules, "areas": areas,
            "yearEnd": {"off": list(off), "tentative": tentative}}
