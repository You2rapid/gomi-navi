"""高知県 高知市（39201）：市のホームページの「高知市のごみ収集日」と「休日のごみ収集計画」から収集日を作る。

このファイルのきまり（どの自治体も同じ形。tools/update_year.py・download_sources.py から使う）:
  NEED                       … 元データ/<県>/<自治体>/<年度>年度/ に置くファイルの名前
  download(year, dest, web, plan) … 市のサイトから NEED のファイルを探して plan に入れる（web は tools/lib/web.py）
  make_calendar(src, year)   … src（上のフォルダ）のファイルから収集日データ（dict）を作る。読めなければ例外で止める

高知市には毎年のカレンダー（日付の表）がない。収集日は曜日で決まっている（京都市と同じ形）。
  可燃ごみ               … 週2回。大街（地区）ごとに「月・木曜日」か「火・金曜日」（市のページ「高知市のごみ収集日」の表）
  プラスチック製容器包装 … 毎週水曜日（全地区）
  資源物・不燃ごみ       … 月1回。第1月曜日〜第4金曜日の20地区に分けて収集するが、**どの町が何曜日かは市が公表していない**。
                            なので、アプリのカレンダーには入れない（区分の説明と品目検索にだけ出す）。
祝日も収集する。休みの日は、毎年2月ごろに市が出す「令和○年度 高知市の休日のごみ収集計画」の表のとおり
（「休み」と書かれた日、年末年始の「○月○日から○月○日までは、ごみの収集はありません」）。

地区（アプリの地区）は、収集日の表の「大街・地区名等」の書き方のまま（例：南街（弘化台を除く）、弘化台）。
大街に入る町は、市の「高知市大街別町名一覧」PDF（地区の説明と、町名で探す・今いる場所から探すに使う）。

フォルダ（元データ/39_高知県/39201_高知市/<年度>年度/）に置くもの:
  高知市のごみ収集日.html   … https://www.city.kochi.kochi.jp/soshiki/64/collection-kochi2.html
  休日のごみ収集計画.html   … 「令和○年度（…）高知市の休日のごみ収集計画」のページ（環境業務課のページから探す）
  大街別町名一覧.pdf        … 上の「高知市のごみ収集日」のページの「高知市大街別町名一覧」
"""
import datetime as dt
import html as H
import re
import sys
import unicodedata
from pathlib import Path

import pymupdf

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "lib"))
import munis as M  # noqa: E402

SITE = "https://www.city.kochi.kochi.jp"
COLLECT = SITE + "/soshiki/64/collection-kochi2.html"
LIST = SITE + "/life/1/168/1421/"          # 「ごみの出し方・収集日」の一覧（休日の収集計画のページへのリンクがある）
NEED = ["高知市のごみ収集日.html", "休日のごみ収集計画.html", "大街別町名一覧.pdf"]
PERENNIAL = True    # 毎年のカレンダーはなく、曜日で決まる（状況一覧で「次の年度のカレンダー」を調べない）

WD = "月火水木金土日"     # Python の weekday() の順
# 可燃ごみの曜日 → 日程の名前
SCHED = {"月・木": "月・木", "火・金": "火・金"}
# 大街・地区の読み（市の資料に読みがないので、地名の読み。機械の読みでは読めないものがあるため）
YOMI = {
    "朝倉": "あさくら", "鴨田": "かもだ", "旭街": "あさひまち", "初月": "はつき", "上街": "かみまち", "高知街": "こうちまち",
    "北街": "きたまち", "南街": "みなみまち", "潮江": "うしおえ", "鏡": "かがみ", "春野": "はるの", "小高坂": "こたかさ",
    "江ノ口": "えのくち", "秦": "はた", "一宮": "いっく", "下知": "しもじ", "布師田": "ぬのしだ", "高須": "たかす",
    "大津": "おおつ", "介良": "けら", "五台山": "ごだいさん", "三里": "さんり", "長浜": "ながはま", "御畳瀬": "みませ",
    "浦戸": "うらど", "弘化台": "こうかだい", "孕東町": "はらみひがしまち", "土佐山": "とさやま",
}


def clean(t):
    return re.sub(r"[\s　​]+", "", unicodedata.normalize("NFKC", t))


def page_text(path):
    """HTML の本文を文字にする。表の1行は「セル|セル|…」の1行にする（セルの中の改行はつなぐ）。かっこは半角になる"""
    s = Path(path).read_text(encoding="utf-8", errors="replace")
    m = re.search(r'id="main_body"(.*?)このページに関するお問い合わせ先', s, re.S)
    s = m.group(1) if m else s

    def row(mt):
        cells = re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", mt.group(0), re.S)
        return "\n" + "|".join(clean(H.unescape(re.sub(r"<[^>]+>", "", c))) for c in cells) + "\n"
    s = re.sub(r"<tr[^>]*>.*?</tr>", row, s, flags=re.S)
    s = re.sub(r"<br\s*/?>|</p>|</h\d>|</li>|</div>", "\n", s)
    s = H.unescape(re.sub(r"<[^>]+>", "", s))
    return "\n".join(clean(x) for x in s.splitlines() if clean(x))


# ---------- 大街別町名一覧 ----------
def read_daigai(pdf):
    """大街別町名一覧 → {大街: [町名, …]}（市の書き方のまま）。
    表は左の列が大街、右の列が町名（何行かに折り返す）。町名の行は、上下の位置がいちばん近い大街に入れる。
    「春野町弘岡中.春野町弘岡下」の「.」は「，」の打ちまちがいとして分ける"""
    heads, rows = [], []
    for page in pymupdf.open(pdf):
        for b in page.get_text("dict")["blocks"]:
            for ln in b.get("lines", []):
                t = clean("".join(sp["text"] for sp in ln["spans"]))
                y = (ln["bbox"][1] + ln["bbox"][3]) / 2
                if not t or t in ("大街", "町名"):
                    continue
                (heads if ln["bbox"][0] < 120 else rows).append((y, t))
    out = {h: "" for _, h in heads}
    for y, t in sorted(rows):
        h = min(heads, key=lambda x: abs(x[0] - y))[1]
        out[h] += t
    out = {h: [x for x in re.split(r"[,，.]", v) if x] for h, v in out.items()}
    for k, v in out.items():
        if not v:
            raise ValueError(f"大街別町名一覧：「{k}」の町名が読めません")
    return out


# ---------- 収集日の表 ----------
def split_top(s):
    """「A・B（x、y）・C」を、かっこの外の「・」で分ける"""
    out, depth, buf = [], 0, ""
    for ch in s:
        if ch in "(（":
            depth += 1
        elif ch in ")）":
            depth -= 1
        if ch == "・" and depth == 0:
            out.append(buf)
            buf = ""
        else:
            buf += ch
    return out + [buf] if buf else out


def read_collect(path):
    """「高知市のごみ収集日」の表 → [(曜日「月・木」, 地区の書き方), …]、プラの曜日、資源物の説明"""
    t = page_text(path)
    rows = [r.split("|") for r in re.findall(r"^.*\|.*$", t, re.M)]
    burn, pla, res = [], None, None
    kind = None
    for r in rows:
        r = [c for c in r if c]
        if not r:
            continue
        if r[0] in ("可燃ごみ", "プラスチック製容器包装", "資源物・不燃ごみ"):
            kind, r = r[0], r[1:]
        if len(r) < 2:
            continue
        day = r[0].replace("曜日", "")
        if kind == "可燃ごみ":
            if day not in SCHED:
                raise ValueError(f"可燃ごみの曜日が読めません：{r}")
            burn += [(day, a) for a in split_top(r[1])]
        elif kind == "プラスチック製容器包装":
            pla = (day, r[1])
        elif kind == "資源物・不燃ごみ":
            res = "".join(r)
    if not burn or not pla:
        raise ValueError(f"{path} の表が読めません（可燃ごみ {len(burn)}・プラ {pla}）")
    if pla[1] != "全地区" or pla[0] not in WD:
        raise ValueError(f"プラスチック製容器包装が「全地区・1つの曜日」ではありません：{pla}")
    return burn, pla[0], res


# ---------- 休日の収集計画 ----------
def md(s, year):
    m = re.match(r"(\d+)月(\d+)日", s)
    if not m:
        return None
    mo, d = int(m[1]), int(m[2])
    return dt.date(year if mo >= 4 else year + 1, mo, d)


def read_holiday(path, year):
    """休日のごみ収集計画 → {日付: [休みになる日程・区分]}、年末年始の休み (はじめ, おわり)"""
    t = page_text(path)
    if f"令和{year - 2018}年度" not in t:
        raise ValueError(f"{path} は令和{year - 2018}年度の休日のごみ収集計画ではありません")
    first = t.rsplit("「資源物・不燃ごみ等」", 1)[0]      # 可燃ごみ・プラの表（資源物・不燃ごみの表はカレンダーに使わない）
    off = {}
    n = 0
    for r in re.findall(r"^(\d+月\d+日.*?)$", first, re.M):
        c = r.split("|")
        d = md(c[0], year)
        if not d or len(c) < 4:
            continue
        n += 1
        vals = c[1:4]                       # 月・木の可燃｜火・金の可燃｜プラ（水曜）
        for v, what in zip(vals, [("月・木", "可燃"), ("火・金", "可燃"), (None, "プラ")]):
            if v == "休み":
                off.setdefault(d.isoformat(), []).append(what)
            elif v not in ("収集", "ー", "-", "－", ""):
                raise ValueError(f"休日の収集計画の {c[0]} が読めません：{v}")
    m = re.search(r"(\d+月\d+日)\(.曜日\)から(\d+月\d+日)\(.曜日\)までは、ごみの収集はありません", t)
    if not m or n < 10:
        raise ValueError(f"{path}：休日の表（{n}行）か、年末年始の休み（○月○日から○月○日まで）が読めません")
    return off, (md(m[1], year), md(m[2], year))


def check_holidays(year, off, listed):
    """祝日なのに休日の収集計画の表にない日（収集の曜日のもの）があれば止める（表の読みもらし・新しい祝日）"""
    csv = M.holiday_csv(year)
    if not csv.exists():
        print(f"  ！ 祝日の CSV がないので、休日の表に抜けがないかは調べていません（{csv}）")
        return
    for line in csv.read_text(encoding="cp932", errors="replace").splitlines()[1:]:
        k = line.split(",")[0].replace("/", "-")
        try:
            d = dt.date(*map(int, k.split("-")))
        except ValueError:
            continue
        if dt.date(year, 4, 1) <= d <= dt.date(year + 1, 3, 31) and d.weekday() < 5 and d not in listed:
            raise ValueError(f"祝日 {d} が休日のごみ収集計画の表にありません（収集するか休みか分からない）")


# ---------- ダウンロード ----------
def download(year, dest, web, plan):
    dest = Path(dest)
    raw = web.get(COLLECT)
    plan.add(COLLECT, dest / "高知市のごみ収集日.html", raw)
    pdf = next((u for u, label in web.links(web.text(raw), COLLECT) if "大街別町名一覧" in label and u.endswith(".pdf")), None)
    if pdf:
        plan.add(pdf, dest / "大街別町名一覧.pdf")
    else:
        plan.problem(f"「高知市大街別町名一覧」の PDF が {COLLECT} にありません")
    title = f"令和{year - 2018}年度"
    hol = next((u for u, label in web.links(web.text(web.get(LIST)), LIST) if title in clean(label) and "休日のごみ収集計画" in clean(label)), None)
    if hol:
        plan.add(hol, dest / "休日のごみ収集計画.html")
    else:
        plan.problem(f"「{title}…高知市の休日のごみ収集計画」のページが {LIST} にありません（例年2月ごろに出る）")


# ---------- 収集日を作る ----------
def make_calendar(folder, year):
    folder = Path(folder)
    daigai = read_daigai(folder / "大街別町名一覧.pdf")
    burn, pla_wd, res = read_collect(folder / "高知市のごみ収集日.html")
    off, (ye0, ye1) = read_holiday(folder / "休日のごみ収集計画.html", year)
    # 表にある祝日（収集する日も）を集める
    t = page_text(folder / "休日のごみ収集計画.html")
    listed = {md(x, year) for x in re.findall(r"^(\d+月\d+日)", t, re.M)}
    check_holidays(year, off, listed)

    schedules = {}
    for s, wds in SCHED.items():
        days = {}
        d = dt.date(year, 4, 1)
        while d <= dt.date(year + 1, 3, 31):
            k, w = d.isoformat(), WD[d.weekday()]
            cs = []
            if not (ye0 <= d <= ye1):
                if w in wds.split("・") and (s, "可燃") not in off.get(k, []):
                    cs.append("可燃")
                if w == pla_wd and (None, "プラ") not in off.get(k, []):
                    cs.append("プラ")
            if cs:
                days[k] = cs
            d += dt.timedelta(days=1)
        schedules[s] = {"rules": {"可燃": f"毎週{wds}曜日", "プラ": f"毎週{pla_wd}曜日"}, "days": days, "moved": {}}

    # 地区：収集日の表の書き方のまま。説明（d）に、その地区の町名（大街別町名一覧）を入れる
    areas, used = [], set()
    for wds, a in burn:
        m = re.match(r"^(.+?)\((.+)\)$", a)
        base, inner = (m[1], m[2]) if m else (a, "")
        if base in daigai:
            towns = daigai[base]
            used.add(base)
            if inner.endswith("を除く"):
                ex = inner[:-3]
                towns = [x for x in towns if x != ex]
                if len(towns) == len(daigai[base]):
                    raise ValueError(f"「{a}」の除く町「{ex}」が大街別町名一覧の{base}にありません")
                n, d = a, "、".join(towns)
            elif inner:
                # 春野：（弘岡上、弘岡中…）は春野町のうちの地区
                parts = re.split(r"[、,，]", inner)
                towns = [x for x in towns if any(x.endswith(p) for p in parts)]
                n, d = f"{base}（{'・'.join(parts)}）", "、".join(towns)
            else:
                n, d = a, "、".join(towns)
        else:
            own = [b for b, ts in daigai.items() if a in ts]
            if not own:
                raise ValueError(f"収集日の表の「{a}」が、大街別町名一覧の大街にも町名にもありません")
            n, d = a, f"{own[0]}のうち{a}"
        n = n.replace("(", "（").replace(")", "）")
        areas.append({"n": n, "s": SCHED[wds], "y": YOMI.get(base, ""), "d": d})
    lack = [b for b in daigai if b not in used]
    if lack:
        raise ValueError(f"大街別町名一覧の大街が、収集日の表にありません：{'・'.join(lack)}")
    choice = resource_choice(folder / "休日のごみ収集計画.html", year, (ye0, ye1))
    print(f"高知市：地区 {len(areas)}・日程 {len(schedules)}（可燃ごみ {'・'.join(SCHED)}、プラ {pla_wd}曜日）")
    print(f"  資源物・不燃ごみ：{res} → 使う人がえらぶ {len(choice['options'])} 通り（休日の変更 {sum(len(o['moved']) for o in choice['options'].values())} 日）")
    return {"year": year, "schedules": schedules, "areas": areas, "choice": choice,
            "yearEnd": {"off": [ye0.isoformat(), ye1.isoformat()], "tentative": False}}


# ---------- 資源物・不燃ごみ（使う人がえらぶ） ----------
# 市は、町ごとの資源物・不燃ごみの日を公表していない（「第1月曜日から第4金曜日までの20地区」とだけある）。
# そこで、使う人が町内会の回覧などで知っている「第○○曜日」をえらぶと、その日がカレンダーに出るようにする。
# 祝日・年末年始の変更は、市の「休日のごみ収集計画」の「資源物・不燃ごみ等」の表のとおり（推測しない）。
RES_CAT = "資源不燃"


def resource_choice(path, year, year_end):
    t = page_text(path)
    if "「資源物・不燃ごみ等」" not in t:
        raise ValueError(f"{path} に「資源物・不燃ごみ等」の表がありません")
    tab = t.rsplit("「資源物・不燃ごみ等」", 1)[1]
    change = {}       # 休みになる日 → 変更して収集する日
    ok_days = set()   # 祝日でも当日分を収集する日
    for r in re.findall(r"^(\d+月\d+日.*?)$", tab, re.M):
        c = r.split("|")
        d = md(c[0], year)
        if not d or len(c) < 2:
            continue
        v = c[1]
        m = re.match(r"休み(\d+月\d+日)\(.曜日\)に変更して収集", v)
        if m:
            change[d] = md(m[1], year)
        elif v.startswith("当日分"):
            ok_days.add(d)
        elif not re.search(r"の資源物・不燃ごみ収集地区\(第\d.曜日地区\)を収集", v):
            raise ValueError(f"休日の収集計画（資源物・不燃ごみ等）の {c[0]} が読めません：{v}")
    if len(change) + len(ok_days) < 5:
        raise ValueError(f"{path}：資源物・不燃ごみ等の表が読めません")
    options = {}
    for n in range(1, 5):
        for wi, w in enumerate("月火水木金"):
            days, moved = [], []
            for mo in list(range(4, 13)) + [1, 2, 3]:
                y = year if mo >= 4 else year + 1
                d = dt.date(y, mo, 1)
                d += dt.timedelta(days=(wi - d.weekday()) % 7 + 7 * (n - 1))
                if d in change:
                    days.append(change[d].isoformat())
                    moved.append(change[d].isoformat())
                elif year_end[0] <= d <= year_end[1]:
                    raise ValueError(f"第{n}{w}曜日の {d} が年末年始の休みで、休日の表に変更の日がありません")
                else:
                    days.append(d.isoformat())
            options[f"第{n}{w}曜日"] = {"days": days, "moved": moved}
    return {"label": "資源物・不燃ごみの日", "cat": RES_CAT, "rule": "毎月{o}（月1回）",
            "ask": "資源物・不燃ごみの日をえらんでください",
            "help": "高知市は、資源物・不燃ごみの日（第1月曜日〜第4金曜日の20通り）を町ごとに公表していません。"
                    "町内会の回覧や、ごみステーションの看板で確かめてえらんでください。分からないときは環境業務課（088-856-5374）へ。"
                    "一部のごみステーションは、同じ地区でも日がちがうことがあります。",
            "options": options}
