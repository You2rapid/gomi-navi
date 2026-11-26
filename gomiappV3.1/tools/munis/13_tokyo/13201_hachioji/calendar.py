"""東京都 八王子市（13201）：市の「家庭用ごみ・資源物収集カレンダー＆出し方」（収集地区1〜20の PDF）から収集日データを作る。

このファイルのきまり（どの自治体も同じ形。tools/update_year.py・download_sources.py から使う）:
  NEED                       … 元データ/<県>/<自治体>/<年度>年度/ に置くファイルの名前
  download(year, dest, web, plan) … 市のサイトから NEED のファイルを探して plan に入れる（web は tools/lib/web.py）
  make_calendar(src, year)   … src（上のフォルダ）のファイルから収集日データ（dict）を作る。読めなければ例外で止める

八王子市の収集日は、市を20の「収集地区」に分けた、収集地区ごとの年度のカレンダー（PDF、1か月1ページ）で決まる。
  ・地区：市のページ「【町名から探す】町名一覧」の行（町名・丁目・番地や団地で分かれた行。約150）。行ごとに収集地区の番号がある。
    「【収集地区番号から探す】収集地区一覧」（収集地区ごとの町名）と、カレンダー PDF の表紙の町名とも見くらべる。
  ・収集日：カレンダー PDF の日付のマスにある区分の名前（文字）を、マスの位置で日付に結びつける。
    可燃ごみ・不燃ごみの袋の絵の中の文字（「可燃ごみ 専用」）と、お知らせの囲みの文字（大きい字）は数えない。
    月の終わりの「23/30」「24/31」のように2つの日が1つのマス（斜めの線で分けたマス）は、区分の文字の数と、
    その区分のふだんの間かく（毎週・隔週・4週ごと）で、どちらの日かを決める（決まらなければ止まる）。
  ・祝日も収集する。年末年始の休み（12/31〜1/3）もカレンダーに入っている（カレンダーのとおりに作る）。

フォルダ（元データ/13_東京都/13201_八王子市/<年度>年度/）に置くもの:
  町名一覧.html          … https://www.city.hachioji.tokyo.jp/kurashi/gomi/kateigomi/shushubi/p029891.html
  収集地区一覧.html      … https://www.city.hachioji.tokyo.jp/kurashi/gomi/kateigomi/shushubi/p038263.html
  カレンダー/<番号>.pdf  … 収集地区ごとのページの「地区○(カレンダー部分)」PDF（1〜20）
"""
import collections
import datetime as dt
import html
import re
import statistics
import sys
import unicodedata
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "lib"))
import kana  # noqa: E402

SITE = "https://www.city.hachioji.tokyo.jp"
BASE = SITE + "/kurashi/gomi/kateigomi/shushubi/"
TOWNS_PAGE = BASE + "p029891.html"
AREAS_PAGE = BASE + "p038263.html"
N_AREAS = 20
NEED = ["町名一覧.html", "収集地区一覧.html"] + [f"カレンダー/{i}.pdf" for i in range(1, N_AREAS + 1)]
WD = "月火水木金土日"

# カレンダーのマスの文字 → アプリの区分（city.js の cats の名前）
LABEL = {
    "可燃ごみ": "可燃", "不燃ごみ": "不燃", "有害ごみ": "有害",
    "容器包装プラスチック": "プラ", "容器包装": "プラ",          # 「容器包装／プラスチック」と2行に分かれたマスがある
    "缶": "缶", "びん": "びん", "ペットボトル": "ペット",
    "新聞": "新聞", "雑誌・雑紙": "雑誌", "ダンボール": "ダンボール", "紙パック": "ダンボール",
    "古着・古布": "古着",
}
CATS = ["可燃", "プラ", "缶", "びん", "有害", "ペット", "新聞", "雑誌", "ダンボール", "古着", "不燃"]
KANJI = {"一": 1, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9}

# 地区の読み（pykakasi では読みちがえる町名。郵便番号一覧の読みで確かめた）
YOMI = {
    "暁町": "あかつきちょう",
    "旭町": "あさひちょう",
    "東町": "あずまちょう",
    "石川町": "いしかわまち",
    "宇津木町": "うつきまち",
    "宇津貫町": "うつぬきまち",
    "大船町": "おおふねまち",
    "大谷町": "おおやまち",
    "大和田町": "おおわだまち",
    "尾崎町": "おさきまち",
    "小津町": "おつまち",
    "片倉町": "かたくらまち",
    "叶谷町": "かのうやまち",
    "上壱分方町": "かみいちぶかたまち",
    "絹ケ丘": "きぬがおか",
    "清川町": "きよかわちょう",
    "久保山町": "くぼやまちょう",
    "小比企町": "こびきまち",
    "左入町": "さにゅうまち",
    "散田町": "さんだまち",
    "新町": "しんちょう",
    "千人町": "せんにんちょう",
    "滝山町": "たきやままち",
    "丹木町": "たんぎまち",
    "天神町": "てんじんちょう",
    "廿里町": "とどりまち",
    "戸吹町": "とぶきまち",
    "中町": "なかちょう",
    "中野上町": "なかのかみちょう",
    "長房町": "ながぶさまち",
    "七国": "ななくに",
    "並木町": "なみきちょう",
    "西寺方町": "にしてらかたまち",
    "弐分方町": "にぶかたまち",
    "八幡町": "はちまんちょう",
    "初沢町": "はつざわまち",
    "兵衛": "ひょうえ",
    "平岡町": "ひらおかちょう",
    "本郷町": "ほんごうちょう",
    "松が谷": "まつがや",
    "松木": "まつぎ",
    "緑町": "みどりちょう",
    "南新町": "みなみしんちょう",
    "南町": "みなみちょう",
    "美山町": "みやまちょう",
    "元八王子町": "もとはちおうじまち",
    "元本郷町": "もとほんごうちょう",
    "谷野町": "やのまち",
    "山田町": "やまたまち",
    "万町": "よろずちょう",
}
# 町名を直したもの（決まり A3）：市の町名一覧は「絹ヶ丘」、収集地区一覧・冊子・郵便番号一覧は「絹ケ丘」
FIXNAME = {"絹ヶ丘": "絹ケ丘"}


def nfkc(s):
    return unicodedata.normalize("NFKC", s).replace("～", "〜").replace("~", "〜").strip()


# ---------------- 市のページを読む ----------------
def read_towns(path):
    """町名一覧 → [(町名の行, 収集地区の番号)]"""
    t = Path(path).read_text(encoding="utf-8")
    out = []
    for a in re.findall(r"<a [^>]*>(.*?)</a>", t, flags=re.S):
        s = nfkc(html.unescape(re.sub(r"<[^>]+>", "", a)))
        m = re.fullmatch(r"(.+?)\s*\(収集地区(\d+)\)", s)
        if m:
            out.append((m[1].strip(), int(m[2])))
    if len(out) < 100:
        raise ValueError(f"町名一覧が {len(out)} 行しか読めません（ページの形がかわった？）")
    return out


def read_area_list(path):
    """収集地区一覧 → {番号: [町名, …]}"""
    t = Path(path).read_text(encoding="utf-8")
    out = {}
    for n, body in re.findall(r'name="(\d+)">収集地区\d+</a></h2>\s*<div>(.*?)</div>', t, flags=re.S):
        out[int(n)] = [nfkc(x) for x in re.split(r"、(?![^()]*\))", nfkc(html.unescape(re.sub(r"<[^>]+>", "", body))))]
    if len(out) != N_AREAS:
        raise ValueError(f"収集地区一覧の地区が {len(out)}（{N_AREAS} のはず）")
    return out


def chome_set(spec):
    """「1〜3」「1・3・4」「1、3〜4」→ {1, 2, 3} など"""
    out = set()
    for part in re.split(r"[・、]", spec):
        a, _, b = part.partition("〜")
        out |= set(range(int(a), int(b or a) + 1))
    return out


def split_name(s):
    """「子安町1、3〜4丁目」→ ("子安町", {1,3,4}, "")、「北野町(1653〜1654番地を除く)」→ ("北野町", None, "1653〜1654番地を除く")"""
    s = nfkc(s)
    note = ""
    m = re.match(r"(.+?)\((.+)\)$", s)
    if m:
        s, note = m[1].strip(), m[2]
    m = re.match(r"(\D+?)([\d・、〜]+)丁目$", s)
    if m:
        return m[1], chome_set(m[2]), note
    m = re.match(r"(\D+?)(\d[\d・、〜番地-]*)番地$", s)       # 「長沼町1508番地、1515〜1520番地」の形（町名一覧にはない）
    if m:
        return m[1], None, m[2] + "番地"
    return s, None, note


# ---------------- カレンダー PDF を読む ----------------
def lines_of(blocks):
    """ページの文字の行 → [(文字, 大きさ, 字体, bbox)]（同じ行の文字はつなぐ）"""
    out = []
    for b in blocks:
        for ln in b.get("lines", []):
            sp = [s for s in ln["spans"] if s["text"].strip()]
            if sp:
                out.append(("".join(s["text"] for s in sp).strip(), max(s["size"] for s in sp), sp[0]["font"], tuple(ln["bbox"])))
    return out


def read_pdf(pdf, year):
    """収集地区のカレンダー → ({日付: {区分}}, {(日付1, 日付2): Counter(区分)}（2つの日が1つのマス）, 数えなかった区分の文字)"""
    import pymupdf
    doc = pymupdf.open(pdf)
    if f"{year}年度版" not in nfkc(doc[0].get_text()).replace(" ", "").replace("\n", ""):
        raise ValueError(f"{Path(pdf).name} は {year}年度版のカレンダーではありません")
    days_out, split_out, skipped = {}, {}, []
    months = set()
    for page in doc:
        blocks = page.get_text("dict")["blocks"]
        ls = lines_of(blocks)
        spans = [(s["text"].strip(), s["size"]) for b in blocks for ln in b.get("lines", []) for s in ln["spans"]]
        mo = [int(t) for t, sz in spans if sz >= 39 and t.isdigit()]
        yr = [int(t) for t, sz in spans if sz >= 24 and re.fullmatch(r"20\d\d", t)]
        if len(mo) != 1 or len(yr) != 1:
            continue
        y, m = yr[0], mo[0]
        first = dt.date(y, m, 1)
        if not dt.date(year, 4, 1) <= first <= dt.date(year + 1, 3, 1):
            continue
        months.add((y, m))
        nums = [(int(t), b) for t, sz, f, b in ls if 17.5 < sz < 19.5 and t.isdigit() and b[1] > 60
                and f in ("GothicMB101Pro-Bold", "ShinGoPro-Bold")]
        ndays = ((first.replace(day=28) + dt.timedelta(days=4)).replace(day=1) - first).days
        if sorted(d for d, _ in nums) != list(range(1, ndays + 1)):
            raise ValueError(f"{Path(pdf).name} {y}年{m}月：日付の数字が読めません（{sorted(d for d, _ in nums)}）")
        pos = dict(nums)
        roww = statistics.median(pos[d + 7][1] - pos[d][1] for d in pos if d + 7 in pos and pos[d + 7][1] > pos[d][1] + 30)
        colw = statistics.median(pos[d + 1][0] - pos[d][0] for d in pos if d + 1 in pos and abs(pos[d + 1][1] - pos[d][1]) < 3)
        # 2つの日が1つのマス：d+7 の数字が d と同じマスの中（右下）にある
        pair = {}
        for d in pos:
            if d + 7 in pos and 0 < pos[d + 7][1] - pos[d][1] < roww * 0.8:
                pair[d] = pair[d + 7] = (d, d + 7)
        # 袋の絵の中の「可燃ごみ」「不燃ごみ」（すぐ下に「専用」がある）
        senyo = [b for t, sz, f, b in ls if t == "専用"]

        def in_bag(b):
            return any(0 < s[1] - b[1] < (b[3] - b[1]) * 1.6 and s[0] < b[2] and b[0] < s[2] for s in senyo)
        got = collections.defaultdict(collections.Counter)
        for t, sz, f, b in ls:
            t = re.sub(r"(有害ごみ)\s*（小型充電式電池等）$", r"\1", t)      # 1行につながっているマスがある
            if t not in LABEL:
                continue
            if sz > 10.5 or (t in ("可燃ごみ", "不燃ごみ") and in_bag(b)):
                continue
            # 2つの日が1つのマスは、マスの左上（はじめの日の数字）を基準にする
            cand = [((b[1] - nb[1]) + (b[0] - nb[0]), d) for d, nb in ((d, pos[pair[d][0]] if d in pair else nb) for d, nb in nums)
                    if -6 <= b[0] - nb[0] < colw * 0.95 and 0 <= b[1] - nb[1] < roww]
            if not cand:
                skipped.append(f"{m}月 {t}")
                continue
            d = min(cand)[1]
            got[pair.get(d, d)][LABEL[t]] += 1
        for k, c in got.items():
            if isinstance(k, tuple):
                split_out[tuple(dt.date(y, m, x) for x in k)] = c
            else:
                days_out[dt.date(y, m, k)] = set(c)
    if len(months) != 12:
        raise ValueError(f"{Path(pdf).name}：月のページが {len(months)}（12 のはず）")
    return days_out, split_out, skipped


def cycle(days, cat):
    """区分のふだんの間かく：{曜日: (週の間かく, 基準の日)}（年末年始の前後はのぞいて数える）"""
    out = {}
    by_w = collections.defaultdict(list)
    for d in sorted(days):
        if cat in days[d]:
            by_w[d.weekday()].append(d)
    for w, ds in by_w.items():
        gaps = [(b - a).days // 7 for a, b in zip(ds, ds[1:])]
        if gaps:
            out[w] = (collections.Counter(gaps).most_common(1)[0][0], ds[0])
    return out


def resolve_split(days, split, problems, name):
    """2つの日が1つのマス → どちらの日の区分か（文字が2つ＝両方の日）"""
    for (d1, d2), cnt in split.items():
        for cat, n in cnt.items():
            if n >= 2:
                hit = [d1, d2]
            else:
                # 同じ曜日のその前の2回の間かくで、次の日を見こむ（隔週の組み合わせが年の途中で入れかわるため、近くの日で見る）
                prev = sorted(d for d in days if cat in days[d] and d.weekday() == d1.weekday() and d < d1)
                nxt = prev[-1] + (prev[-1] - prev[-2]) if len(prev) >= 2 else None
                hit = [d for d in (d1, d2) if d == nxt]
                if nxt == d1 and (d1 - prev[-1]).days == 7:
                    hit = []        # 毎週の区分で文字が1つだけ：どちらの日か分からない
                if len(hit) != 1:
                    problems.append(f"{name} {d1}/{d2.day} の {cat}：どちらの日か決まりません（{hit}）")
                    continue
            for d in hit:
                days.setdefault(d, set()).add(cat)


def say_rules(days):
    """収集日の決まりの説明（例：「毎週月・木曜日」「隔週火曜日」「4週ごとの火曜日」）"""
    words = {1: "毎週", 2: "隔週", 4: "4週ごとの"}
    out = {}
    for cat in CATS:
        cyc = cycle(days, cat)
        if not cyc:
            continue
        groups = collections.defaultdict(list)
        for w in sorted(cyc):
            groups[cyc[w][0]].append(WD[w])
        txt = "・".join(f"{words.get(k, f'{k}週ごとの')}{'・'.join(ws)}曜日" for k, ws in sorted(groups.items()))
        if cat == "ペット":
            summer = [d for d in days if cat in days[d] and d.month in (7, 8, 9)]
            if summer and min(b - a for a, b in zip(sorted(summer), sorted(summer)[1:])).days == 7:
                txt += "（7〜9月は毎週）"
        out[cat] = txt
    return out


def odd_days(days, cat):
    """ふだんの間かくからはずれた日（年末年始の休みなど）：(なかった日, 足された日)"""
    cyc = cycle(days, cat)
    want = set()
    for w, (k, base) in cyc.items():
        d = base
        while d <= max(days):
            want.add(d)
            d += dt.timedelta(days=7 * k)
    have = {d for d in days if cat in days[d]}
    return sorted(want - have), sorted(have - want)


# ---------------- 市のサイトから取ってくる ----------------
def download(year, dest, web, plan):
    raw = web.get(AREAS_PAGE)
    page = web.text(raw)
    if f"{year}年度版" not in page:
        plan.problem(f"{AREAS_PAGE} は {year}年度版ではありません（まだ出ていない？）")
        return
    plan.add(AREAS_PAGE, dest / "収集地区一覧.html", raw)
    plan.add(TOWNS_PAGE, dest / "町名一覧.html")
    links = {int(n): u for u, n in re.findall(r'href="([^"]+)" name="(\d+)">収集地区\d+</a>', page)}
    for n in range(1, N_AREAS + 1):
        if n not in links:
            plan.problem(f"収集地区{n} のページが {AREAS_PAGE} にありません")
            continue
        url = SITE + links[n] if links[n].startswith("/") else links[n]
        sub = web.text(web.get(url))
        pdf = [u for u, t in web.links(sub, url) if u.lower().endswith(".pdf") and "カレンダー" in t]
        if pdf:
            plan.add(pdf[0], dest / "カレンダー" / f"{n}.pdf")
        else:
            plan.problem(f"{url} にカレンダーの PDF がありません")


# ---------------- 収集日を作る ----------------
def make_calendar(folder, year):
    folder = Path(folder)
    towns = read_towns(folder / "町名一覧.html")
    alist = read_area_list(folder / "収集地区一覧.html")
    problems = []
    # 町名一覧と収集地区一覧が同じか（「子安町1、3〜4丁目」と「子安町1・3・4丁目」のような書き方のちがいは、町・丁目・かっこの中でくらべる）
    def key(s):
        town, ch, note = split_name(s)
        # 「293-12番地〜293-45番地」→「293-12〜45番地」
        note = re.sub(r"([0-9]+)-([0-9]+)番地〜([0-9]+)-([0-9]+)番地",
                      lambda m: f"{m[1]}-{m[2]}〜{m[4]}番地" if m[1] == m[3] else m[0], note)
        return town.replace("ケ", "ヶ"), frozenset(ch or ()), re.sub(r"番地?", "", note).replace("-", "")
    a = collections.Counter((key(t), n) for t, n in towns)
    b = collections.Counter((key(t), n) for n, ts in alist.items() for t in ts)
    if a != b:
        problems.append(f"町名一覧と収集地区一覧がちがう：町名一覧だけ {sorted(a - b)}／収集地区一覧だけ {sorted(b - a)}")
    schedules, irregular, nskip, nsplit = {}, [], 0, 0
    for n in range(1, N_AREAS + 1):
        pdf = folder / "カレンダー" / f"{n}.pdf"
        days, split, skipped = read_pdf(pdf, year)
        nskip += len(skipped)
        nsplit += sum(1 for k in split if dt.date(year, 4, 1) <= k[0])
        for d, cs in days.items():
            if ("有害" in cs) != ("びん" in cs):
                problems.append(f"収集地区{n} {d}：びんと有害ごみが同じ日ではない（{cs}）")
        resolve_split(days, split, problems, f"収集地区{n}")
        days = {d: cs for d, cs in days.items() if dt.date(year, 4, 1) <= d <= dt.date(year + 1, 3, 31)}
        for cat in CATS:
            miss, extra = odd_days(days, cat)
            for d in miss:
                if not (dt.date(year, 12, 29) <= d <= dt.date(year + 1, 1, 4)):
                    irregular.append(f"収集地区{n} {cat}：{d} がない")
            for d in extra:
                irregular.append(f"収集地区{n} {cat}：{d} がある")
        schedules[str(n)] = {"rules": say_rules(days),
                             "days": {d.isoformat(): [c for c in CATS if c in days[d]] for d in sorted(days)},
                             "moved": {}}
    areas = []
    for t, n in towns:
        for a, b in FIXNAME.items():
            t = t.replace(a, b)
        town = split_name(t)[0]
        areas.append({"n": t, "s": str(n), "y": YOMI.get(town) or kana.yomi(town), "d": f"収集地区{n}"})
    off = sorted(d for d in (dt.date(year, 12, 31) + dt.timedelta(days=i) for i in range(4))
                 if all(d.isoformat() not in s["days"] for s in schedules.values()))
    print(f"八王子市：地区 {len(areas)}・収集地区 {len(schedules)}・2つの日が1つのマス {nsplit}・"
          f"お知らせなどで数えなかった区分の文字 {nskip}・ふだんの間かくからはずれた日（年末年始のぞく） {len(irregular)}")
    if "-v" in sys.argv:
        for s in irregular:
            print("  ・", s)
    if problems:
        for p in problems[:40]:
            print("  ！", p)
        raise ValueError(f"読めないところが {len(problems)} あります")
    return {"year": year, "schedules": schedules, "areas": areas,
            "yearEnd": {"off": [off[0].isoformat(), off[-1].isoformat()] if off else [], "tentative": False}}
