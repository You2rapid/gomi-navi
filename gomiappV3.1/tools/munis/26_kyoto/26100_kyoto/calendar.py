"""京都府 京都市（26100）：区ごとの「町名別一覧表」PDF から収集日データを作る。

このファイルのきまり（どの自治体も同じ形。tools/update_year.py・download_sources.py から使う）:
  NEED                       … 元データ/<県>/<自治体>/<年度>年度/ に置くファイルの名前
  download(year, dest, web, plan) … 市のサイトから NEED のファイルを探して plan に入れる（web は tools/lib/web.py）
  make_calendar(src, year)   … src（上のフォルダ）のファイルから収集日データ（dict）を作る。読めなければ例外で止める

京都市の収集日は、町ごとに曜日で決まっている（毎年のカレンダーはない）。
  燃やすごみ 週2回（例：月・木）、缶・びん・ペットボトル 週1回、プラスチック類 週1回、
  小型金属類・スプレー缶 月1回（第○水曜日）、雑がみ 月2回（第○・○火曜日 か 水曜日）
祝日も収集する（年末年始だけ休み）。年末年始の休みは毎年10〜11月ごろに市が発表するので、YEAR_END に足す。
まだ発表がない年度は 12/31〜1/3 を休みとして作り、データに「仮」の印を付ける（状況一覧で注意が出る）。

町名別一覧表は区ごとの PDF（右京区の京北地域だけは別の PDF）。表の「〃」は、上の行と同じ町（または同じ頭の町名）。
「〃」で省かれた頭の部分は、e-Stat の町名（元データ/.../地図/）と照らし合わせて決める。
"""
import calendar as _cal
import datetime as dt
import re
import sys
import unicodedata
from collections import defaultdict
from pathlib import Path

import pymupdf

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "lib"))
import kana  # noqa: E402

# 区（アプリの「地域」）と PDF の名前
WARDS = [("北区", "kita"), ("上京区", "kamigyo"), ("左京区", "sakyo"), ("中京区", "nakagyo"), ("東山区", "higashiyama"),
         ("山科区", "yamashina"), ("下京区", "shimogyo"), ("南区", "minami"), ("右京区", "ukyo"), ("西京区", "nishikyo"),
         ("伏見区", "fushimi")]
NEED = [f"{s}.pdf" for _, s in WARDS] + ["keihoku.pdf"]
# 区の地方公共団体コード（e-Stat の地図のファイル名 r2ka<コード>.kml）
WARD_CODE = {"北区": 26101, "上京区": 26102, "左京区": 26103, "中京区": 26104, "東山区": 26105, "下京区": 26106,
             "南区": 26107, "右京区": 26108, "伏見区": 26109, "山科区": 26110, "西京区": 26111}
PAGE = "https://www.city.kyoto.lg.jp/kankyo/page/0000000509.html"
PERENNIAL = True   # 毎年のカレンダーはなく、曜日で決まる（状況一覧で「次の年度のカレンダー」を調べない）

# 京北地域（右京区）は地区ごとの表（keihoku.pdf）。雑がみの定期収集はない
KEIHOKU = [
    ("京北（黒田・宇津・山国・細野地区）", "くろだ・うつ・やまぐに・ほその", {"燃やす": "月・木", "缶びん": "水", "プラ": "水", "金属": 1}),
    ("京北（周山・弓削地区）", "しゅうざん・ゆげ", {"燃やす": "火・金", "缶びん": "水", "プラ": "水", "金属": 4}),
]

# 年末年始（市の発表）：off＝収集しない日（両端をふくむ）、skip＝その日だけ収集しない区分
YEAR_END = {
    2026: {"off": ("2026-12-30", "2027-01-03"), "skip": {"2026-12-29": ["雑がみ"]},
           "src": "https://www.city.kyoto.lg.jp/kankyo/page/0000358386.html"},
}
DEFAULT_OFF = ("12-31", "01-03")

# 「〃」で省かれた頭が自動で決まらないもの（区, 上の町）→ 頭。読み取りの注意.txt を見て足す
PREFIX_FIX = {("北区", "杉坂北尾"): "杉坂", ("左京区", "花背大布施町"): "花背"}

ORDER = ["燃やす", "缶びん", "プラ", "金属", "雑がみ"]
WD = "月火水木金土日"          # Python の weekday() の順
WD_JA = "日月火水木金土"
YEAR = 2026


# ---------------- PDF を読む ----------------
SKIP_LINE = re.compile(r"^(町\s*名|収集日|燃やす|ごみ|缶|ﾍﾟｯﾄ|ペット|ﾌﾟﾗ|プラ|小型|金属|雑がみ|備\s*考|週\d|月\d|第○|日第○|【.*】|\d+$)")


def nfkc(s):
    return unicodedata.normalize("NFKC", s)


def lines_of(pdf):
    """PDF の行（同じ高さの文字のかたまり）を、左から順の文字列のリストで返す"""
    for page in pymupdf.open(pdf):
        rows = []
        for w in sorted(page.get_text("words"), key=lambda w: ((w[1] + w[3]) / 2, w[0])):
            y = (w[1] + w[3]) / 2
            if rows and abs(rows[-1][0] - y) <= 4:
                rows[-1][1].append(w)
            else:
                rows.append([y, [w]])
        for _, ws in rows:
            yield [w[4] for w in sorted(ws, key=lambda w: w[0])]


WD1 = r"[月火水木金]"
WK2 = r"第\d[.・]\d" + WD1           # 第2・4水（月2回の週の曜日）
VAL = re.compile(
    r"^(?P<m>" + WD1 + "・" + WD1 + "|" + WD1 + ")"
    r"(?P<k>" + WK2 + "|" + WD1 + ")?"
    r"(?P<p>" + WK2 + "|" + WD1 + ")?"
    r"(?P<n>[1-5])?"
    r"(?P<z>[1-4]・[1-4][火水]曜)?"
    r"(?P<note>.*)$")


def wk(v):
    """「水」→ 水、「第2.4水」→ 第2・4水"""
    return v.replace(".", "・")


def parse_row(text):
    """1行（または、つないだ行）の文字 → (名前の文字, 収集日 dict / None（収集していません）/ False（値がない）, 備考)
    一部の区分だけ「収集していません」の町は、その区分を入れない"""
    t = nfkc(text).replace("　", " ")
    flat = re.sub(r"\s+", "", t)
    partial = "いません" in flat
    flat = re.sub(r"収集して|いません", "", flat)
    # 名前と値の境目：読みのかっこが閉じたところ（値より前にあるとき）。なければ最初の「曜日・曜日」か曜日
    mv = re.search(WD1 + "(・" + WD1 + ")?" + "(" + WD1 + "|第)", flat) or (re.search(WD1 + "・" + WD1, flat) if partial else None)
    mp = re.search(r"[)）]", flat)
    if mp and (not mv or mp.start() < mv.start()):
        name, rest = flat[:mp.end()], flat[mp.end():]
    elif mv:
        name, rest = flat[:mv.start()], flat[mv.start():]
    else:
        return (flat, None, "") if partial else (flat, False, "")
    v = VAL.match(rest)
    if not v or not (v["k"] or partial):
        return (name, None, rest) if partial else (name + rest, False, "")
    vals = {"燃やす": v["m"]}
    if v["k"]:
        vals["缶びん"] = wk(v["k"])
    if v["p"]:
        vals["プラ"] = wk(v["p"])
    if v["n"]:
        vals["金属"] = int(v["n"])
    if v["z"]:
        z = re.match(r"([1-4])・([1-4])([火水])", v["z"])
        vals["雑がみ"] = (int(z[1]), int(z[2]), z[3])
    return name, vals, v["note"]


def split_name(s):
    """「出雲路神楽町(いずもじかぐらちょう)」→ (出雲路神楽町, いずもじかぐらちょう)"""
    m = re.match(r"^(.*?)[（(](.*?)[）)]?$", s)
    kanji, yomi = (m.group(1), m.group(2)) if m else (s, "")
    return kanji, yomi.replace("〃", "")


def looks_like_name(s):
    """値のない行が、町名の始まり（読みが次の行に続く・町名だけの行）かどうか"""
    flat = re.sub(r"\s+", "", nfkc(s))
    if flat.startswith("〃"):
        return True
    m = re.search(r"[（(](.)", flat)
    if m:
        return bool(re.match(r"[ぁ-ん〃]", m.group(1)))   # かっこの中が読み（ひらがな）なら町名
    return bool(re.search(r"(町|丁目)$", flat))


def estat_names(folder, ward):
    """e-Stat の町名（学区などの頭を含む）。〃 の頭を決めるのに使う"""
    kml = Path(folder).parent / "地図" / f"r2ka{WARD_CODE[ward]}.kml"
    if not kml.exists():
        return []
    return re.findall(r'<SimpleData name="S_NAME">(.*?)</SimpleData>', kml.read_text(encoding="utf-8"))


def loose(s):
    """表記ゆれをそろえる（ヶ・ケ・が、峯・峰 など）"""
    return s.translate(str.maketrans({"ヶ": "ケ", "ｹ": "ケ", "峯": "峰", "之": "ノ", "の": "ノ"}))


def prefix_hits(parent, child, names):
    """〃 の頭の長さの候補：parent の頭の部分 p で、p+child が e-Stat の町名の終わりと合うもの"""
    ln = [loose(n) for n in names]
    return [k for k in range(1, len(parent)) if any(n.endswith(loose(parent[:k] + child)) for n in ln)]


def prefix_by_reading(parent, yomi):
    """上の町の読みが、頭を省いた読み（例：大北山鏡石町（かがみいしちょう））のとき、読みの長さから頭を決める。
    機械の読みは「町」を「まち」と読むなど少し短くなりやすいので、読みより0〜2文字短いもののうち、頭の長いほうをとる"""
    if not yomi or len(parent) < 3:
        return None
    if len(kana.yomi(parent)) <= len(yomi) + 1:
        return None          # 読みが名前ぜんぶの読み
    ks = [k for k in range(1, len(parent) - 1) if 0 <= len(yomi) - len(kana.yomi(parent[k:])) <= 2]
    return parent[:max(ks)] if ks else None


def read_ward(pdf, ward, folder, problems):
    names = estat_names(folder, ward)
    ln = [loose(n) for n in names]
    out, groups, last, buf = [], [], None, ""
    for tokens in lines_of(pdf):
        line = "".join(tokens).strip("　 ")
        if not line or SKIP_LINE.match(re.sub(r"\s+", "", line.replace("　", ""))):
            continue
        raw, vals, note = parse_row(buf + line)
        if vals is False:
            if buf or looks_like_name(line):
                buf += line          # 町名や読みが次の行に続く
            elif last:
                last["note"] = (last["note"] + re.sub(r"\s+", "", nfkc(line))).strip()   # 備考の続き
            else:
                problems.append(f"{ward}：読めない行「{line[:40]}」")
            if len(buf) > 120:
                problems.append(f"{ward}：読めない行「{buf[:50]}」")
                buf = ""
            continue
        buf = ""
        kanji, yomi = split_name(raw)
        row = {"base": kanji, "yomi": yomi, "vals": vals, "note": note}
        if kanji.startswith("〃") and kanji.endswith("側") and last:
            kanji, row["note"] = "〃", kanji.lstrip("〃") + note   # 「〃 河原町三条側」：同じ町の、通りの側ちがい
        if kanji in ("", "〃") and last:
            row["same"] = last           # 同じ町で、通りの東西などで分かれている
        elif kanji.startswith("〃") and groups:
            row["child"] = kanji.lstrip("〃")
            groups[-1]["children"].append(row)
        else:
            groups.append({"parent": kanji, "yomi": yomi, "children": []})
        out.append(row)
        last = row
    # 「〃」のまとまりごとに頭を決める：子の町名を e-Stat と照らし合わせて、いちばん多く合う頭の長さ。
    # 合わなければ、上の町の読みの長さ、丁目、e-Stat の町名の分かれ目の順で決める
    for g in groups:
        if not g["children"]:
            continue
        parent = g["parent"]
        if (ward, parent) in PREFIX_FIX:
            for c in g["children"]:
                c["base"] = PREFIX_FIX[(ward, parent)] + c["child"]
            continue
        votes = {}
        for c in g["children"]:
            for k in prefix_hits(parent, c["child"], names):
                votes[k] = votes.get(k, 0) + 1
        pre = parent[:max(votes, key=lambda k: (votes[k], k))] if votes else prefix_by_reading(parent, g["yomi"])
        if pre is None and all(re.search(r"[一二三四五六七八九十]+丁目$", c["child"]) for c in g["children"]):
            pre = re.sub(r"[一二三四五六七八九十]+丁目$", "", parent)
        if pre is None:
            ks = [k for k in range(1, len(parent) - 1) if any(loose(parent[:k]) in n and loose(parent[:k + 1]) not in n for n in ln)]
            pre = parent[:max(ks)] if ks else ""
            problems.append(f"{ward}：「〃{g['children'][0]['child']}」などの頭を、e-Stat の町名の分かれ目から「{pre}」にした（上の町：{parent}）")
        for c in g["children"]:
            c["base"] = pre + c["child"]
    for r in out:
        if "same" in r:
            r["base"] = r["same"]["base"]
    for r in out:
        r.pop("same", None)
        r.pop("child", None)
    return out


# ---------------- 収集日を作る ----------------
def sched_key(v):
    z = v.get("雑がみ")
    return "|".join([v["燃やす"], v.get("缶びん", ""), v.get("プラ", ""), str(v.get("金属", "")),
                     f"{z[0]}・{z[1]}{z[2]}" if z else ""])


def say(spec):
    """「月・木」→ 毎週月・木曜日、「第2・4水」→ 毎月第2・4水曜日"""
    return f"毎月{spec}曜日" if spec.startswith("第") else f"毎週{spec}曜日"


def hit(spec, w, nth):
    m = re.match(r"第(\d)・(\d)(.)", spec)
    return (w == m[3] and nth in (int(m[1]), int(m[2]))) if m else w in spec.split("・")


def rules(v):
    out = {c: say(v[c]) for c in ("燃やす", "缶びん", "プラ") if v.get(c)}
    if v.get("金属"):
        out["金属"] = f"毎月第{v['金属']}水曜日"
    if v.get("雑がみ"):
        z = v["雑がみ"]
        out["雑がみ"] = f"毎月第{z[0]}・{z[1]}{z[2]}曜日"
    return out


def days_of(v, year, ye):
    out = {}
    d, end = dt.date(year, 4, 1), dt.date(year + 1, 3, 31)
    while d <= end:
        k = d.isoformat()
        if not (ye["off"][0] <= k <= ye["off"][1]):
            w, nth = WD[d.weekday()], (d.day - 1) // 7 + 1
            cs = []
            for c in ("燃やす", "缶びん", "プラ"):
                if v.get(c) and hit(v[c], w, nth):
                    cs.append(c)
            if v.get("金属") and w == "水" and nth == v["金属"]:
                cs.append("金属")
            z = v.get("雑がみ")
            if z and w == z[2] and nth in (z[0], z[1]):
                cs.append("雑がみ")
            cs = [c for c in cs if c not in ye.get("skip", {}).get(k, [])]
            if cs:
                out[k] = cs
        d += dt.timedelta(days=1)
    return out


def download(year, dest, web, plan):
    page = web.text(web.get(PAGE))
    links = web.links(page, PAGE)
    for ward, fn in WARDS + [("京北", "keihoku")]:
        label = "収集日" if ward == "京北" else f"町名別一覧表（{ward}）"
        found = [u for u, l in links if u.endswith(".pdf") and l.startswith(label) and (ward != "京北" or "keihoku" in u)]
        if found:
            # ページのリンクは「/kankyo/page/cmsfiles/」になっているが、ファイルは「/kankyo/cmsfiles/」にある
            plan.add(found[0].replace("/kankyo/page/cmsfiles/", "/kankyo/cmsfiles/"), dest / f"{fn}.pdf")
        else:
            plan.problem(f"{label} の PDF が {PAGE} に見つかりません")


def make_calendar(folder, year):
    global YEAR
    YEAR = year
    folder = Path(folder)
    if year in YEAR_END:
        ye, tentative = YEAR_END[year], False
    else:
        ye = {"off": (f"{year}-{DEFAULT_OFF[0]}", f"{year + 1}-{DEFAULT_OFF[1]}"), "skip": {}}
        tentative = True
        print(f"  ！ {year}年度の年末年始の日程がまだ calendar.py の YEAR_END にありません。12/31〜1/3 を休みとして作ります（市の発表が出たら直す）")
    problems, areas, schedules = [], [], {}

    def add(ward, n, y, v, d=""):
        key = sched_key(v)
        if key not in schedules:
            schedules[key] = {"rules": rules(v), "days": days_of(v, year, ye), "moved": {}}
        areas.append({"r": ward, "n": n, "s": key, "y": y, **({"d": d} if d else {})})

    nocol = []
    for ward, fn in WARDS:
        rows = read_ward(folder / f"{fn}.pdf", ward, folder, problems)
        # 同じ区に同じ名前の町が2つ以上あるときは、備考（通りの東西など）を名前に足す
        cnt = defaultdict(int)
        for r in rows:
            cnt[r["base"]] += 1
        for r in rows:
            if r["vals"] is None:
                nocol.append(f"{ward}{r['base']}")
                continue
            n = r["base"] + (f"（{r['note']}）" if r["note"] and cnt[r["base"]] > 1 else "")
            add(ward, n, r["yomi"], r["vals"], r["note"] if r["note"] and cnt[r["base"]] == 1 else "")
    for n, y, v in KEIHOKU:
        add("右京区", n, y, v, "右京区京北地域")
    # 同じ区・同じ名前で、収集日も同じものは1つにまとめる
    seen, uniq = set(), []
    for a in areas:
        k = (a["r"], a["n"], a["s"])
        if k not in seen:
            seen.add(k)
            uniq.append(a)
    dup = defaultdict(list)
    for a in uniq:
        dup[(a["r"], a["n"])].append(a)
    for (r, n), lst in dup.items():
        if len(lst) > 1:
            for i, a in enumerate(lst, 1):
                a["n"] = f"{n}（{i}）"
                a.setdefault("d", "同じ名前の町が区の中に複数あります。市の町名別一覧表で確かめてください")
            problems.append(f"{r}{n}：同じ名前で収集日がちがう町が {len(lst)} つ")
    res = {"year": year, "schedules": schedules, "areas": uniq,
           "yearEnd": {"off": list(ye["off"]), "tentative": tentative}}
    print(f"京都市：地区 {len(uniq)}・収集日の組み合わせ {len(schedules)}・収集していない町 {len(nocol)}")
    for p in problems:
        print("  ？", p)
    # 読み取りで気になったところを、元データに書いておく（手で確かめる用）
    (folder / "読み取りの注意.txt").write_text(
        f"京都市 {year}年度：町名別一覧表の読み取りで、確かめたほうがよいところ（{len(problems)}件）\n"
        "「頭を…にした」は、〃 で省かれた町名の頭を推測したもの。「読めない行」は、その町がアプリに入っていない。\n\n"
        + "\n".join(problems) + "\n", encoding="utf-8")
    return res
