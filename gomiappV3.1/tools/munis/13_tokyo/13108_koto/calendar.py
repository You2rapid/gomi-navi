"""東京都 江東区（13108）：区の「地区別 資源回収・ごみ収集日一覧」（PDF）と年末年始のカレンダーから収集日データを作る。

このファイルのきまり（どの自治体も同じ形。tools/update_year.py・download_sources.py から使う）:
  NEED                       … 元データ/<県>/<自治体>/<年度>年度/ に置くファイルの名前
  download(year, dest, web, plan) … 区のサイトから NEED のファイルを探して plan に入れる（web は tools/lib/web.py）
  make_calendar(src, year)   … src（上のフォルダ）のファイルから収集日データ（dict）を作る。読めなければ例外で止める

江東区の収集日は、区を12の「地区」（地区番号1〜12）に分けて、地区ごとに曜日で決まる。
  資源（びん・缶・ペットボトル・古紙など）週1回・プラスチック 週1回・燃やすごみ 週2回・燃やさないごみ 隔週（2週に1回）。
  祝日も収集する。年末年始（12/31〜1/3）は休みで、燃やさないごみは地区によって臨時の収集日がある。
  ・地区と曜日：区の「令和8年度 資源回収・ごみ収集日一覧（地区別）」（PDF。文字のない画像なので、下の DISTRICTS に書き写した）。
    燃やさないごみは、表の4月の1回目の日から2週ごと（表のすべての日と合うことを画像で見た。年末年始の日は表にのっていない）。
  ・見くらべ：区のオープンデータ「資源回収・ごみ収集日一覧」（CSV、2024-11。町名ごとの地区番号と曜日）の曜日と、DISTRICTS の曜日が合うか。
    地区番号がちがう町（豊洲・塩浜。令和8年度の一覧で分かれ方が変わった）は、令和8年度の一覧のほうを使う（ODIFF に書く）。
  ・年末年始：区の「年末年始資源回収・ごみ収集のお知らせ」の地区別カレンダー（PDF、画像）を YEAR_END に書き写した。

フォルダ（元データ/13_東京都/13108_江東区/<年度>年度/）に置くもの:
  収集日一覧.html  … https://www.city.koto.lg.jp/388010/kurashi/gomi/kate/43735.html
  収集日一覧.pdf   … 上のページの「○年度（○年度）資源回収・ごみ収集日一覧（日本語）」（見くらべ用。画像）
  年末年始/        … https://www.city.koto.lg.jp/388010/kurashi/gomi/kaishu/nenmatunenshi2019.html の地区別カレンダー（見くらべ用。画像）
オープンデータ（元データ/13_東京都/13108_江東区/オープンデータ/）:
  131083_201_kotocity_waste_recycle_collectionday.csv … https://catalog.data.metro.tokyo.lg.jp/dataset/t131083d3100000009
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

SITE = "https://www.city.koto.lg.jp"
PAGE = SITE + "/388010/kurashi/gomi/kate/43735.html"
YE_PAGE = SITE + "/388010/kurashi/gomi/kaishu/nenmatunenshi2019.html"
OPENDATA = "131083_201_kotocity_waste_recycle_collectionday.csv"
NEED = ["収集日一覧.html", "収集日一覧.pdf"]
WD = "月火水木金土日"
CATS = ["燃やす", "プラ", "資源", "燃やさない"]

# 令和8年度 資源回収・ごみ収集日一覧（地区別）：地区 → (町名, 資源, プラスチック, 燃やすごみ, 燃やさないごみの4月の1回目)
DISTRICTS = {
    2026: {
        1: (["新砂", "東砂6〜8丁目", "南砂2〜4・6・7丁目"], "土", "木", "火・金", "04-06"),
        2: (["亀戸4〜9丁目"], "月", "金", "水・土", "04-07"),
        3: (["永代", "越中島", "清澄", "佐賀", "富岡", "深川1丁目", "福住", "古石場", "牡丹", "門前仲町"], "火", "土", "月・木", "04-08"),
        4: (["大島8・9丁目", "北砂6・7丁目", "東砂1〜5丁目"], "水", "月", "火・金", "04-09"),
        5: (["白河1〜3丁目", "新大橋", "高橋", "常盤", "平野1〜3丁目", "三好1〜3丁目", "森下1〜4丁目"], "木", "火", "水・土", "04-10"),
        6: (["青海", "有明", "東雲", "豊洲2・4〜6丁目", "海の森"], "金", "水", "月・木", "04-11"),
        7: (["北砂1〜5丁目", "南砂1・5丁目"], "土", "木", "火・金", "04-13"),
        8: (["大島1・2丁目", "亀戸1〜3丁目", "住吉", "毛利"], "月", "金", "水・土", "04-14"),
        9: (["木場", "東陽", "深川2丁目", "冬木"], "火", "土", "月・木", "04-01"),
        10: (["大島3〜7丁目"], "水", "月", "火・金", "04-02"),
        11: (["石島", "海辺", "扇橋", "白河4丁目", "猿江", "千石", "千田", "平野4丁目", "三好4丁目", "森下5丁目"], "木", "火", "水・土", "04-03"),
        12: (["枝川", "塩浜", "潮見", "新木場", "辰巳", "豊洲1・3丁目", "夢の島", "若洲"], "金", "水", "月・木", "04-04"),
    },
}
# オープンデータ（2024-11）と令和8年度の一覧で地区番号がちがう町（令和8年度の一覧を使う）
ODIFF = {"豊洲": "オープンデータは豊洲ぜんぶが6地区。令和8年度は1・3丁目が12地区、2・4〜6丁目が6地区",
         "塩浜1丁目": "オープンデータは6地区。令和8年度は塩浜ぜんぶが12地区"}

# 年末年始：off＝収集しない日（両端をふくむ）、extra＝地区ごとの燃やさないごみの臨時の収集日（区のカレンダーの「臨時」）
YEAR_END = {
    2026: {
        "off": ("2026-12-31", "2027-01-03"),
        "src": "区の「年末年始資源回収・ごみ収集のお知らせ」地区別カレンダー（令和8年度、PDF）。年末は12/30まで、年始は1/4から",
        # 2地区 12/29・3地区 12/30 も「臨時」と書いてあるが、ふだんの2週ごとの日と同じ（収集日一覧の表にはのっていない）
        "extra": {4: ["2026-12-24", "2027-01-07"], 5: ["2026-12-25", "2027-01-08"], 6: ["2026-12-26", "2027-01-09"]},
    },
}
DEFAULT_OFF = ("12-31", "01-03")

# 地区の読み（pykakasi では読みちがえる町名。郵便番号一覧の読みで確かめた）
YOMI = {
    "青海": "あおみ",
    "越中島": "えっちゅうじま",
    "大島": "おおじま",
    "新大橋": "しんおおはし",
    "千田": "せんだ",
    "高橋": "たかばし",
    "平野": "ひらの",
    "冬木": "ふゆき",
    "門前仲町": "もんぜんなかちょう",
}


def nfkc(s):
    return unicodedata.normalize("NFKC", s).replace("～", "〜").replace("~", "〜").replace("　", " ").strip()


def chome(s):
    """「東砂6〜8丁目」→ ("東砂", {6,7,8})、「新砂」→ ("新砂", None)"""
    m = re.match(r"(\D+?)([\d・〜]+)丁目$", nfkc(s))
    if not m:
        return nfkc(s), None
    out = set()
    for part in m[2].split("・"):
        a, _, b = part.partition("〜")
        out |= set(range(int(a), int(b or a) + 1))
    return m[1], out


def read_opendata(path):
    t = Path(path).read_bytes()
    for enc in ("utf-8-sig", "cp932"):
        try:
            t = t.decode(enc)
            break
        except UnicodeDecodeError:
            pass
    rows = list(csv.reader(io.StringIO(t)))
    if rows[0][:7] != ["じゅうしょ", "住所", "地区番号", "資源", "プラスチック", "燃やすごみ", "燃やさないごみ"]:
        raise ValueError(f"オープンデータの列がかわりました：{rows[0]}（calendar.py を直す）")
    return [[nfkc(c) for c in r] for r in rows[1:] if len(r) >= 7 and r[1].strip()]


# ---------------- 区のサイトから取ってくる ----------------
def download(year, dest, web, plan):
    raw = web.get(PAGE)
    page = web.text(raw)
    reiwa = year - 2018
    hit = [u for u, t in web.links(page, PAGE) if u.lower().endswith(".pdf") and f"{reiwa}年度（{year}年度）資源回収・ごみ収集日一覧（日本語）" in t]
    if not hit:
        plan.problem(f"{PAGE} に「{reiwa}年度（{year}年度）資源回収・ごみ収集日一覧（日本語）」の PDF がありません（まだ出ていない？）")
        return
    plan.add(PAGE, dest / "収集日一覧.html", raw)
    plan.add(hit[0], dest / "収集日一覧.pdf")


# ---------------- 収集日を作る ----------------
def make_calendar(folder, year):
    folder = Path(folder)
    if year not in DISTRICTS:
        raise ValueError(f"{year}年度の地区と曜日が calendar.py の DISTRICTS にありません（区の収集日一覧の PDF を見て書き写す）")
    ye = YEAR_END.get(year)
    if ye:
        off, extra, tentative = ye["off"], ye.get("extra", {}), False
    else:
        off, extra, tentative = (f"{year}-{DEFAULT_OFF[0]}", f"{year + 1}-{DEFAULT_OFF[1]}"), {}, True
        print(f"  ！ {year}年度の年末年始がまだ calendar.py の YEAR_END にありません。12/31〜1/3 を休みとして作り「未定」にします")
    problems, schedules, areas = [], {}, []
    for n, (towns, shigen, pla, moyasu, funen) in DISTRICTS[year].items():
        rule = {"燃やす": [WD.index(w) for w in moyasu.split("・")], "プラ": [WD.index(pla)], "資源": [WD.index(shigen)]}
        base = dt.date.fromisoformat(f"{year}-{funen}")
        days, moved = {}, {}
        d, end = dt.date(year, 4, 1), dt.date(year + 1, 3, 31)
        while d <= end:
            k = d.isoformat()
            cs = [c for c in CATS[:3] if d.weekday() in rule[c]]
            if (d - base).days >= 0 and (d - base).days % 14 == 0:
                cs.append("燃やさない")
            if off[0] <= k <= off[1]:
                cs = []
            if k in extra.get(n, []):
                cs.append("燃やさない")
                moved[k] = ["燃やさない"]
            if cs:
                days[k] = [c for c in CATS if c in cs]
            d += dt.timedelta(days=1)
        if base.month != 4 or base.day > 14:
            problems.append(f"{n}地区：燃やさないごみの4月の1回目の日がおかしい（{base}）")
        schedules[str(n)] = {"rules": {"燃やす": f"毎週{moyasu}曜日", "プラ": f"毎週{pla}曜日", "資源": f"毎週{shigen}曜日",
                                       "燃やさない": f"隔週{WD[base.weekday()]}曜日（2週に1回）"},
                             "days": days, "moved": moved}
        for t in towns:
            town = chome(t)[0]
            areas.append({"n": t, "s": str(n), "y": YOMI.get(town) or kana.yomi(town), "d": f"{n}地区"})
    # オープンデータの曜日・地区番号と見くらべる
    od = read_opendata(folder.parent / "オープンデータ" / OPENDATA)
    nod, ndiff = 0, []
    for yomi, name, num, shigen, pla, moyasu, funen in (r[:7] for r in od):
        town, ch = chome(name)
        hit = [(n, v) for n, v in DISTRICTS[year].items()
               if any(chome(t)[0] == town and (ch is None or chome(t)[1] is None or ch <= chome(t)[1] or ch & chome(t)[1]) for t in v[0])]
        if not hit:
            problems.append(f"オープンデータの「{name}」が令和{year - 2018}年度の一覧にない")
            continue
        for n, v in hit:
            if (shigen, pla, moyasu) != v[1:4] or funen != f"(隔週){WD[dt.date.fromisoformat(f'{year}-{v[4]}').weekday()]}":
                if (shigen, pla, moyasu) == v[1:4] and name in ODIFF or town in ODIFF:
                    continue
                problems.append(f"オープンデータの「{name}」（{num}地区）の曜日が {n}地区とちがう：{shigen}/{pla}/{moyasu}/{funen}")
        if str(num) not in [str(n) for n, _ in hit]:
            if name in ODIFF or town in ODIFF:
                ndiff.append(name)
            else:
                problems.append(f"オープンデータの「{name}」の地区番号 {num} が令和{year - 2018}年度の一覧（{[n for n, _ in hit]}）とちがう")
        nod += 1
    print(f"江東区：地区 {len(areas)}・日程 {len(schedules)}・オープンデータと見くらべた町 {nod}（地区番号が変わった町 {ndiff}）")
    if problems:
        for p in problems[:40]:
            print("  ！", p)
        raise ValueError(f"区の一覧と合わないところが {len(problems)} あります")
    return {"year": year, "schedules": schedules, "areas": areas,
            "yearEnd": {"off": list(off), "tentative": tentative}}
