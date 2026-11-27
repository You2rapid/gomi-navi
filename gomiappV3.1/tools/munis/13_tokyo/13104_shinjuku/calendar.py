"""東京都 新宿区（13104）：区のページ「資源回収・ごみ収集日」（町名・地番ごとの曜日の HTML の表）から収集日データを作る。

このファイルのきまり（どの自治体も同じ形。tools/update_year.py・download_sources.py から使う）:
  NEED                       … 元データ/<県>/<自治体>/<年度>年度/ に置くファイルの名前
  download(year, dest, web, plan) … 区のサイトから NEED のファイルを探して plan に入れる（web は tools/lib/web.py）
  make_calendar(src, year)   … src（上のフォルダ）のファイルから収集日データ（dict）を作る。読めなければ例外で止める

新宿区の収集日は、町名・丁目（一部は地番）ごとに曜日で決まる。
  資源（古紙・資源プラスチック・びん・缶・ペットボトル・スプレー缶・カセットボンベ・乾電池）週1回・燃やすごみ 週2回・
  金属・陶器・ガラスごみ 月2回（「1・3番目」か「2・4番目」の曜日。5番目はなし）。祝日も収集する。日曜日と年末年始は休み。
  ・曜日：区のページ「資源回収・ごみ収集日（令和○年度）」の表（町名の頭文字・集積所の住所・資源・燃やすごみ・金属・陶器・ガラスごみ・管轄・カレンダー）。
  ・見くらべ：表の各行にある、日程ごとの「資源回収・ごみ収集日カレンダー」（PDF。1か月1ページ。日付のマスの色：
    緑＝資源、赤＝燃やすごみ、青＝金属・陶器・ガラスごみ）を全部読み、作った日と1日ずつくらべる（年末年始もカレンダーのとおりか見る）。
  ・「*」の欄（歌舞伎町1・2丁目・新宿3丁目・新宿4丁目・新宿5丁目（17番、18番）・西新宿1丁目）は、区が「管轄の清掃センターに問い合わせて」としている。
    どの区分も「*」の地区（新宿4丁目のほかの4つ）は、収集日が1日もないので地区に入れない。新宿4丁目は資源（金曜日）だけ入れ、
    ほかの区分は rules に「清掃センターに問い合わせ」と書く（決まり A1。推測しない）。
  ・年末年始：区のお知らせ「年末年始の資源・ごみ収集」の「令和○年12月31日（○曜日）から令和○年1月3日（○曜日）まで、資源・ごみの収集をお休みします」を読む
    （曜日がその年の日付と合うか確かめる。合わなければ前の年度のお知らせとみて「未定」にする）。休みの前後は曜日どおり（区のお知らせのチラシ）。

フォルダ（元データ/13_東京都/13104_新宿区/<年度>年度/）に置くもの:
  収集日.html        … https://www.city.shinjuku.lg.jp/seikatsu/file09_01_00001.html
  カレンダー/<番号>.pdf … 上のページの表の「カレンダー[PDF]」（28枚）
  年末年始.html      … https://www.city.shinjuku.lg.jp/seikatsu/seiso01_001002_00005.html
"""
import datetime as dt
import html
import re
import sys
import unicodedata
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "lib"))
import kana  # noqa: E402

SITE = "https://www.city.shinjuku.lg.jp"
DAYS_PAGE = SITE + "/seikatsu/file09_01_00001.html"
YE_PAGE = SITE + "/seikatsu/seiso01_001002_00005.html"
NEED = ["収集日.html", "年末年始.html"]
WD = "月火水木金土日"
CATS = ["資源", "燃やす", "金属"]
HEAD = ["町名の頭文字", "集積所の住所", "資源の回収日", "燃やすごみの収集日", "金属・陶器・ガラスごみの収集日", "管轄", "カレンダー"]
OFFICE = {"新": "新宿清掃事務所", "東": "新宿東清掃センター", "歌": "歌舞伎町清掃センター"}
TEL = {"新": "03-3950-2923", "東": "03-3353-9471", "歌": "03-3200-5339"}
COLOR = {(0, 176, 80): "資源", (255, 0, 0): "燃やす", (0, 112, 192): "金属"}     # カレンダー PDF のマスの色
TENTATIVE = ("12-31", "01-03")

# 地区の読み（pykakasi では読みちがえる町名。郵便番号一覧の読みで確かめて足す）
YOMI = {
    "下宮比町": "しもみやびちょう", "中町": "なかちょう", "中里町": "なかざとちょう", "二十騎町": "にじゅっきまち", "信濃町": "しなのまち",
    "北山伏町": "きたやまぶしちょう", "南山伏町": "みなみやまぶしちょう", "南榎町": "みなみえのきちょう", "南町": "みなみちょう", "喜久井町": "きくいちょう",
    "四谷本塩町": "よつやほんしおちょう", "天神町": "てんじんちょう", "富久町": "とみひさちょう", "岩戸町": "いわとちょう", "市谷八幡町": "いちがやはちまんちょう",
    "市谷加賀町": "いちがやかがちょう", "市谷山伏町": "いちがややまぶしちょう", "市谷本村町": "いちがやほんむらちょう", "市谷柳町": "いちがややなぎちょう", "市谷甲良町": "いちがやこうらちょう",
    "市谷砂土原町": "いちがやさどはらちょう", "市谷船河原町": "いちがやふながわらまち", "市谷薬王寺町": "いちがややくおうじまち", "市谷長延寺町": "いちがやちょうえんじまち", "弁天町": "べんてんちょう",
    "愛住町": "あいずみちょう", "戸塚町": "とつかまち", "払方町": "はらいかたまち", "揚場町": "あげばちょう", "改代町": "かいたいちょう",
    "新小川町": "しんおがわまち", "早稲田南町": "わせだみなみちょう", "東榎町": "ひがしえのきちょう", "榎町": "えのきちょう", "河田町": "かわだちょう",
    "津久戸町": "つくどちょう", "白銀町": "しろがねちょう", "矢来町": "やらいちょう", "筑土八幡町": "つくどはちまんちょう", "西五軒町": "にしごけんちょう",
    "霞ヶ丘町": "かすみがおかまち", "馬場下町": "ばばしたちょう",
}


def nfkc(s):
    return unicodedata.normalize("NFKC", s).replace("～", "〜").replace("~", "〜").strip()


def cell(s):
    return re.sub(r"\s+", "", nfkc(html.unescape(re.sub(r"<[^>]+>", "", s))))


def read_table(path):
    """収集日の HTML → [{"name", "資源", "燃やす", "金属", "office", "pdf"}]"""
    t = Path(path).read_text(encoding="utf-8")
    out = []
    for tb in re.findall(r"<table.*?</table>", t, re.S):
        trs = re.findall(r"<tr.*?</tr>", tb, re.S)
        head = [cell(c) for c in re.findall(r"<t[hd][^>]*>(.*?)</t[hd]>", trs[0], re.S)]
        if head[0] != "町名の頭文字":
            continue        # 問い合わせ先の表など
        if head != HEAD or re.search(r"rowspan|colspan", tb):
            raise ValueError(f"{path} の表の形がかわりました：{head}（calendar.py を直す）")
        for tr in trs[1:]:
            r = [cell(c) for c in re.findall(r"<t[hd][^>]*>(.*?)</t[hd]>", tr, re.S)]
            if len(r) != len(HEAD) or r[5] not in OFFICE:
                raise ValueError(f"{path} の行の形がおかしい：{r}")
            pdf = re.findall(r'href="([^"]+\.pdf)"', tr)
            out.append({"name": r[1], "資源": r[2], "燃やす": r[3], "金属": r[4], "office": r[5],
                        "pdf": pdf[0].rsplit("/", 1)[-1] if pdf else ""})
    if len(out) < 150:
        raise ValueError(f"{path} の表が {len(out)} 行しか読めません（ページの形がかわった？）")
    return out


def parse_rule(cat, s):
    """「月曜日・木曜日」→ {(0, None), (3, None)}、「1・3番目の土曜日」→ {(5, 1), (5, 3)}、「*」→ None"""
    if s == "*":
        return None
    m = re.fullmatch(r"(\d)・(\d)番目の([月火水木金土])曜日", s)
    if m:
        if cat != "金属" or (m[1], m[2]) not in (("1", "3"), ("2", "4")):
            raise ValueError(f"{cat}の曜日の形がいつもとちがう：{s}")
        return frozenset({(WD.index(m[3]), int(m[1])), (WD.index(m[3]), int(m[2]))})
    out = set()
    for part in s.split("・"):
        m = re.fullmatch(r"([月火水木金土])曜日", part)
        if not m:
            raise ValueError(f"{cat}の曜日が読めない：{s}")
        out.add((WD.index(m[1]), None))
    if cat == "金属" or len(out) != (2 if cat == "燃やす" else 1):
        raise ValueError(f"{cat}の曜日の形がいつもとちがう：{s}")
    return frozenset(out)


def say(rule):
    if rule is None:
        return "問合せ"
    ks = sorted(k for _, k in rule if k)
    ws = sorted({w for w, _ in rule})
    return (f"第{'・'.join(map(str, ks))}" if ks else "") + "・".join(WD[w] for w in ws)


def say_long(cat, rule, office):
    if rule is None:
        return f"収集日は{OFFICE[office]}（{TEL[office]}）に問い合わせてください"
    if cat == "金属":
        return f"{say(rule)}曜日（月2回）"
    return f"毎週{say(rule)}曜日"


def hits(rule, d):
    return any(d.weekday() == w and (k is None or (d.day - 1) // 7 + 1 == k) for w, k in rule)


def read_year_end(path, year):
    """年末年始のお知らせ → (休みの最初の日, 最後の日)。その年度のお知らせでなければ None"""
    p = Path(path)
    if not p.exists():
        return None
    t = cell(p.read_text(encoding="utf-8"))
    m = re.search(r"令和(\d+)年12月(\d+)日\((.)曜日\)から令和(\d+)年1月(\d+)日\((.)曜日\)まで、資源・ごみの収集をお休みします", t)
    if not m:
        raise ValueError(f"{p}：年末年始の休みの文が読めません（ページの書き方がかわった？ calendar.py を直す）")
    if int(m[1]) + 2018 != year:
        return None
    a, b = dt.date(year, 12, int(m[2])), dt.date(year + 1, 1, int(m[5]))
    if WD[a.weekday()] != m[3] or WD[b.weekday()] != m[6]:
        raise ValueError(f"{p}：年末年始の日と曜日が合いません（{m[0]}）")
    return a.isoformat(), b.isoformat()


def read_pdf(pdf, year):
    """日程のカレンダー（1か月1ページ）→ {日付: [区分]}（その年度の日だけ）"""
    import pymupdf
    out, months = {}, set()
    for page in pymupdf.open(pdf):
        m = re.search(r"(\d{4})年(\d+)月", page.get_text())
        y, mo = int(m[1]), int(m[2])
        if not (dt.date(year, 4, 1) <= dt.date(y, mo, 1) <= dt.date(year + 1, 3, 1)):
            continue        # 前の年度の3月のページ
        months.add((y, mo))
        cells = []
        for dr in page.get_drawings():
            f, r = dr.get("fill"), dr["rect"]
            if f and 100 < r.width < 120 and 40 < r.height < 100:     # 月曜の列が広いページ・2週ぶんが1つのマスもある
                c = COLOR.get(tuple(round(v * 255) for v in f))
                if c:
                    cells.append((r, c))
        for w in page.get_text("words"):
            if not re.fullmatch(r"\d{1,2}", w[4]) or w[1] < 100:
                continue
            cx, cy = (w[0] + w[2]) / 2, (w[1] + w[3]) / 2
            cs = [c for r, c in cells if r.x0 <= cx <= r.x1 and r.y0 <= cy <= r.y1]
            if cs:
                out[dt.date(y, mo, int(w[4])).isoformat()] = sorted(set(cs), key=CATS.index)
    if len(months) != 12:
        raise ValueError(f"{Path(pdf).name}：{year}年度の月が {len(months)} か月しかありません（新しい年度のカレンダー？）")
    return out


def area_name(r):
    return r["name"].replace("(", "（").replace(")", "）")


def town_of(name):
    """「荒木町（21から23番地）」→「荒木町」、「新宿3丁目」→「新宿」"""
    t = re.sub(r"（.*$", "", name)
    return re.sub(r"[\d・から]+丁目$", "", t)


# ---------------- 区のサイトから取ってくる ----------------
def download(year, dest, web, plan):
    raw = web.get(DAYS_PAGE)
    plan.add(DAYS_PAGE, dest / "収集日.html", raw)
    seen = set()
    for u in re.findall(r'href="([^"]+\.pdf)"', web.text(raw)):
        if u not in seen:
            seen.add(u)
            plan.add(SITE + u if u.startswith("/") else u, dest / "カレンダー" / u.rsplit("/", 1)[-1])
    plan.add(YE_PAGE, dest / "年末年始.html")


# ---------------- 収集日を作る ----------------
def make_calendar(folder, year):
    folder = Path(folder)
    ye = read_year_end(folder / "年末年始.html", year)
    tentative = ye is None
    off = ye or (f"{year}-{TENTATIVE[0]}", f"{year + 1}-{TENTATIVE[1]}")
    if tentative:
        print(f"  ！ {year}年度の年末年始のお知らせ（年末年始.html）がありません。{off[0]}〜{off[1]} を「未定」にして作ります")
    rows = read_table(folder / "収集日.html")
    problems, schedules, areas, pdf_of = [], {}, [], {}
    skipped = []
    for r in rows:
        rules = {c: parse_rule(c, r[c]) for c in CATS}
        if all(v is None for v in rules.values()):
            skipped.append(r["name"])       # どの区分も「*」：区が収集日を公表していないので、地区に入れない（決まり A1）
            continue
        key ="／".join(f"{c}:{say(rules[c])}" for c in CATS)
        if any(v is None for v in rules.values()):
            key += f"／{r['office']}"
        if key not in schedules:
            days = {}
            d, end = dt.date(year, 4, 1), dt.date(year + 1, 3, 31)
            while d <= end:
                k = d.isoformat()
                cs = [c for c in CATS if rules[c] is not None and d.weekday() != 6 and hits(rules[c], d)]
                if off[0] <= k <= off[1]:
                    cs = []
                if cs:
                    days[k] = cs
                d += dt.timedelta(days=1)
            schedules[key] = {"rules": {c: say_long(c, rules[c], r["office"]) for c in CATS}, "days": days, "moved": {}}
        town = town_of(area_name(r))
        a = {"n": area_name(r), "s": key, "y": YOMI.get(town) or kana.yomi(town), "d": f"{OFFICE[r['office']]}"}
        unknown = [c for c in CATS if rules[c] is None]
        if unknown or "一部" in r["name"]:
            a["d"] += f"。{'一部の地番' if not unknown else '収集日'}は清掃センターに確かめてください（{TEL[r['office']]}）"
        areas.append(a)
        if r["pdf"]:
            pdf_of.setdefault(r["pdf"], set()).add(key)
        elif not unknown:
            problems.append(f"{r['name']}：カレンダー PDF がない")
    # カレンダー PDF と見くらべる（年度の全日。年末年始も）
    checked = 0
    for name, keys in sorted(pdf_of.items()):
        if len(keys) != 1:
            problems.append(f"{name}：1つのカレンダーに、ちがう曜日の地区がある（{keys}）")
            continue
        pdf = folder / "カレンダー" / name
        if not pdf.exists():
            problems.append(f"{name} がありません（download_sources.py で取る）")
            continue
        got, want = read_pdf(pdf, year), schedules[next(iter(keys))]["days"]
        for k in sorted(set(got) | set(want)):
            if tentative and off[0] <= k <= off[1]:
                continue
            if got.get(k, []) != want.get(k, []):
                problems.append(f"{name} {k}：カレンダー {got.get(k)}／作った日 {want.get(k)}")
        checked += 1
    names = [a["n"] for a in areas]
    dup = {x for x in names if names.count(x) > 1}
    if dup:
        problems.append(f"同じ名前の地区：{dup}")
    print(f"新宿区：地区 {len(areas)}・収集日の組み合わせ {len(schedules)}・見くらべたカレンダー {checked}枚・"
          f"年末年始 {'未定' if tentative else '発表ずみ'}（{off[0]}〜{off[1]}）")
    print(f"  どの区分も「*」で入れなかった地区 {len(skipped)}：{'・'.join(skipped)}")
    if problems:
        for p in problems[:40]:
            print("  ！", p)
        raise ValueError(f"区の表・カレンダーと合わないところが {len(problems)} あります")
    return {"year": year, "schedules": schedules, "areas": areas,
            "yearEnd": {"off": list(off), "tentative": tentative}}
