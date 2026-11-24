"""山口県 宇部市（35202）：市のサイトの「○○地区のごみ収集カレンダー」のページ（24地区）から収集日データを作る。

このファイルのきまり（どの自治体も同じ形。tools/update_year.py・download_sources.py から使う）:
  NEED                       … 元データ/<県>/<自治体>/<年度>年度/ に置くファイルの名前
  download(year, dest, web, plan) … 市のサイトから NEED のファイルを探して plan に入れる（web は tools/lib/web.py）
  make_calendar(src, year)   … src（上のフォルダ）のファイルから収集日データ（dict）を作る。読めなければ例外で止める

宇部市の家庭ごみ（市の「家庭ごみの収集日程表」）:
  ・月・水・金の燃やせるごみ … 全地区 毎週 月・水・金曜日
  ・プラスチック製容器包装   … 地区ごとに 毎週 火曜日 か 木曜日
  ・燃やせないごみの日       … 月1回（びん・缶／ペットボトル／燃やせないごみ／月1回収集の燃やせるごみ／危険ごみ）
  ・古紙の日                 … 月1回（新聞紙／雑誌・雑がみ／段ボール／紙製容器包装）
月1回の日は、地区のページの表（「令和8年」「令和9年」の1〜12月）に書いてある。市の日程表は暦年（1〜12月）なので、
年度（4月〜3月）は2つの年の表から作る。毎週の収集は祝日も収集し、年末年始だけ変わる（市が毎年11月ごろに
「年末年始のごみ収集日程」のページで発表する）。年末年始は YEAR_END に足す。まだ足していない年度は
12/31〜1/3 を休みとして作り、データに「仮」の印を付ける（状況一覧で注意が出る）。

オープンデータ「【宇部市】ごみ収集」の「各地区のごみ収集日」（CSV・暦年。元データ/…/オープンデータ/garbage_collection.csv）
と同じ年の月は、地区のページと見くらべ、ちがえば止める。
"""
import csv
import datetime as dt
import html as H
import io
import re
from pathlib import Path

PAGE = "https://www.city.ube.yamaguchi.jp/kurashi/gomi/dashikata/1001977/1014196/1001979/index.html"
# 地区（市のページの順）と読み
DISTRICTS = [("東岐波", "ひがしきわ"), ("西岐波", "にしきわ"), ("常盤", "ときわ"), ("恩田", "おんだ"), ("岬", "みさき"),
             ("見初", "みぞめ"), ("神原", "かんばら"), ("琴芝", "ことしば"), ("上宇部", "かみうべ"), ("川上", "かわかみ"),
             ("小羽山", "おばやま"), ("新川", "しんかわ"), ("鵜の島", "うのしま"), ("藤山", "ふじやま"), ("西宇部", "にしうべ"),
             ("黒石", "くろいし"), ("厚南", "こうなん"), ("原", "はら"), ("厚東", "ことう"), ("二俣瀬", "ふたまたせ"),
             ("小野", "おの"), ("船木", "ふなき"), ("万倉", "まぐら"), ("吉部", "きべ")]
NAMES = [n for n, _ in DISTRICTS]
NEED = ["ごみ収集日カレンダー.html", "年末年始.html"] + [f"地区のページ/{n}.html" for n in NAMES]
OPENDATA_CSV = Path(__file__).resolve().parents[5] / "元データ" / "35_山口県" / "35202_宇部市" / "オープンデータ" / "garbage_collection.csv"

# 月1回の日に出せるもの（アプリの区分）
FUNEN_DAY = ["びん缶", "ペット", "不燃", "月1可燃", "危険"]
KOSHI_DAY = ["古紙", "紙容器"]
WD = "月火水木金土日"     # Python の weekday() の順

# 年末年始（市の「年末年始のごみ収集日程・施設等の開場状況」のページ）。
# 毎週の区分ごとに、地区のまとまりの「年末の最後の日（last）」と「年始の最初の日（first）」、臨時の日（extra）。
# last と first のあいだの日は収集しない。title は保存したページの見出しにある文字（ちがう年のページなら止める）
_A = ["東岐波", "西岐波", "常盤", "恩田", "岬", "見初", "神原", "琴芝", "上宇部", "川上", "船木"]
_THU = ["東岐波", "西岐波", "常盤", "恩田", "岬", "見初", "神原", "琴芝", "上宇部", "川上"]
YEAR_END = {
    2026: {
        "src": "https://www.city.ube.yamaguchi.jp/kurashi/gomi/dashikata/1001977/1014196/1001980.html",
        "title": "令和8年12月から令和9年1月",
        "rules": [
            # 燃やせるごみ：12/30（水）まで。年始は1/4（月）と1/5（火）に分けて収集（1/5 は臨時収集。その地区は1/4 の収集はない）
            {"cat": "燃やせる", "areas": _A, "last": "2026-12-30", "first": "2027-01-06", "extra": ["2027-01-05"]},
            {"cat": "燃やせる", "areas": [n for n in NAMES if n not in _A], "last": "2026-12-30", "first": "2027-01-04"},
            # プラスチック製容器包装：木曜日の地区は 12/24 まで・1/7 から、火曜日の地区は 12/29 まで・1/12 から
            {"cat": "プラ", "areas": _THU, "last": "2026-12-24", "first": "2027-01-07"},
            {"cat": "プラ", "areas": [n for n in NAMES if n not in _THU], "last": "2026-12-29", "first": "2027-01-12"},
        ],
    },
}
DEFAULT_OFF = ("12-31", "01-03")


def reiwa(y):
    return y - 2018


# ---------------- ダウンロード ----------------
def download(year, dest, web, plan):
    page = web.get(PAGE)
    plan.add(PAGE, dest / "ごみ収集日カレンダー.html", page)
    links = web.links(web.text(page), PAGE)
    for n in NAMES:
        u = [u for u, label in links if label == f"{n}地区のごみ収集カレンダー"]
        if u:
            plan.add(u[0], dest / "地区のページ" / f"{n}.html")
        else:
            plan.problem(f"「{n}地区のごみ収集カレンダー」が {PAGE} に見つかりません")
    u = [u for u, label in links if "年末年始のごみ収集日程" in label]
    if u:
        plan.add(u[0], dest / "年末年始.html")
    else:
        plan.problem(f"「年末年始のごみ収集日程」のページが {PAGE} に見つかりません")
    # 見くらべる用の、全地区分の日程表（PDF）。年度は2つの年にまたがる
    for r in (reiwa(year), reiwa(year) + 1):
        u = [u for u, label in links if f"全地区分家庭ごみ収集日程表（令和{r}年）日本語" in label]
        if u:
            plan.add(u[0], dest / f"家庭ごみ収集日程表_令和{r}年.pdf")
        else:
            plan.problem(f"「全地区分家庭ごみ収集日程表（令和{r}年）」が {PAGE} に見つかりません（なくても収集日は作れる）")


# ---------------- 地区のページを読む ----------------
def plain(s):
    return re.sub(r"\s+", "", H.unescape(re.sub(r"<[^>]+>", "", s)))


def read_district(path):
    """地区のページ → (プラの曜日, {令和の年: {"不燃": [12か月のセル], "古紙": [...]}})"""
    t = Path(path).read_text(encoding="utf-8")
    weekly = re.search(r"毎週収集するごみ</h3>(.*?)</table>", t, re.S)
    if not weekly:
        raise SystemExit(f"{path.name}：「毎週収集するごみ」の表がありません")
    w = plain(weekly.group(1))
    if "燃やせるごみ月曜日、水曜日、金曜日" not in w:
        raise SystemExit(f"{path.name}：燃やせるごみが「月曜日、水曜日、金曜日」ではありません：{w}")
    m = re.search(r"プラスチック製容器包装([月火水木金])曜日の収集", w)
    if not m:
        raise SystemExit(f"{path.name}：プラスチック製容器包装の曜日が読めません：{w}")
    tables = {}
    for cap, body in re.findall(r"<caption>\s*令和(\d+)年\s*</caption>(.*?)</table>", t, re.S):
        rows = {}
        for tr in re.findall(r"<tr>(.*?)</tr>", body, re.S):
            th = plain("".join(re.findall(r"<th[^>]*>(.*?)</th>", tr, re.S)))
            tds = [plain(x) for x in re.findall(r"<td[^>]*>(.*?)</td>", tr, re.S)]
            if not tds:
                continue
            if len(tds) != 12:
                raise SystemExit(f"{path.name}：令和{cap}年の「{th}」が12か月ありません（{len(tds)}）")
            if th.startswith("燃やせないごみ"):
                rows["不燃"] = tds
            elif th.startswith("古紙"):
                rows["古紙"] = tds
            else:
                raise SystemExit(f"{path.name}：令和{cap}年の表に知らない行があります：{th}")
        if set(rows) != {"不燃", "古紙"}:
            raise SystemExit(f"{path.name}：令和{cap}年の表に「燃やせないごみ」「古紙」の行がそろっていません")
        tables[int(cap)] = rows
    return m.group(1), tables


def cell_days(cell, y, m, where):
    """「13日」「2・30日」「2日30日」（月に2回）→ [日付]、「-」「－」「―」→ []"""
    if re.fullmatch(r"[-－―ー‐]?", cell):
        return []
    if not re.fullmatch(r"(\d+日?[・、]?)+", cell) or not cell.endswith("日"):
        raise SystemExit(f"{where} {y}年{m}月：日付が読めません「{cell}」")
    out = [dt.date(y, m, int(d)) for d in re.findall(r"\d+", cell)]
    for d in out:
        if d.weekday() not in (1, 3):
            print(f"  ！ {where} {d}（{WD[d.weekday()]}）：月1回の日がいつもの火・木曜日ではありません（市のページのとおりにする）")
    return out


def monthly(tables, year, name):
    """年度（4月〜3月）の、月1回の日 → {"不燃": [日付], "古紙": [日付]}"""
    out = {"不燃": [], "古紙": []}
    for cy, months in ((year, range(4, 13)), (year + 1, range(1, 4))):
        r = reiwa(cy)
        if r not in tables:
            raise SystemExit(f"{name}地区のページに 令和{r}年（{cy}年）の表がありません（{year}年度には {cy}年{months[0]}月〜の日がいる）。"
                             "市がまだ出していなければ、出てから作り直してください")
        for k in out:
            for m in months:
                out[k] += cell_days(tables[r][k][m - 1], cy, m, f"{name}地区 {k}")
    return out


# ---------------- オープンデータの CSV と見くらべる ----------------
def opendata_check(found, year):
    """オープンデータの「各地区のごみ収集日」（暦年）と、地区のページの日を、その年度に入る月だけ見くらべる"""
    if not OPENDATA_CSV.exists():
        print(f"  （オープンデータの CSV がないので見くらべない：{OPENDATA_CSV}）")
        return
    raw = OPENDATA_CSV.read_bytes()
    text = raw.decode("utf-8-sig") if raw[:3] == b"\xef\xbb\xbf" else raw.decode("cp932", "replace")
    bad, n_checked, cy_seen = [], 0, set()
    start, end = dt.date(year, 4, 1), dt.date(year + 1, 3, 31)
    for r in csv.DictReader(io.StringIO(text)):
        name = r["地名"].strip()
        if name not in found:
            bad.append(f"CSV に知らない地区：{name}")
            continue
        plastic, mon = found[name]
        p = re.match(r"([月火水木金])", r["プラスチック製容器包装"].strip())
        if not p or p.group(1) != plastic:
            bad.append(f"{name} プラの曜日：CSV {r['プラスチック製容器包装']} ／ 市のページ {plastic}")
        for col, k in (("燃やせないごみ", "不燃"), ("古紙・紙製容器包装", "古紙")):
            ds = [dt.datetime.strptime(x, "%Y%m%d").date() for x in re.findall(r"\b(20\d{6})\b", r[col])]
            cys = {d.year for d in ds}
            cy_seen |= cys
            csv_in = sorted(d for d in ds if start <= d <= end)
            page_in = sorted(d for d in mon[k] if d.year in cys)
            if csv_in != page_in:
                bad.append(f"{name} {k}：CSV {[d.isoformat() for d in csv_in]} ／ 市のページ {[d.isoformat() for d in page_in]}")
            n_checked += len(csv_in)
    if bad:
        raise SystemExit("オープンデータの CSV と市のページで、ちがうところがあります（どちらが正しいか市の日程表 PDF で確かめる）：\n  "
                         + "\n  ".join(bad))
    print(f"  オープンデータの CSV（{'・'.join(map(str, sorted(cy_seen)))}年）と見くらべて合っていた：月1回の日 {n_checked}日・プラの曜日 {len(found)}地区")


# ---------------- 収集日を作る ----------------
def year_end(year, folder, name, cat, days, moved):
    """毎週の区分の年末年始の休み・臨時の日を入れる。(off, tentative) を返す"""
    ye = YEAR_END.get(year)
    if not ye:
        a, b = dt.date.fromisoformat(f"{year}-{DEFAULT_OFF[0]}"), dt.date.fromisoformat(f"{year + 1}-{DEFAULT_OFF[1]}")
        for k in [k for k in days if a.isoformat() <= k <= b.isoformat()]:
            days[k] = [c for c in days[k] if c != cat]
        return True
    rules = [r for r in ye["rules"] if r["cat"] == cat and name in r["areas"]]
    if len(rules) != 1:
        raise SystemExit(f"YEAR_END[{year}]：{name}地区の「{cat}」の決まりが {len(rules)} 個あります（1つにする）")
    r = rules[0]
    for k in [k for k in days if r["last"] < k < r["first"]]:
        days[k] = [c for c in days[k] if c != cat]
    for k in r.get("extra", []):
        days.setdefault(k, []).append(cat)
        moved.setdefault(k, []).append(cat)
    return False


def make_calendar(folder, year):
    folder = Path(folder)
    ye = YEAR_END.get(year)
    if ye:
        page = plain((folder / "年末年始.html").read_text(encoding="utf-8"))
        if ye["title"] not in page:
            raise SystemExit(f"年末年始.html が「{ye['title']}」のページではありません。市のページ（{ye['src']}）を保存し直すか、YEAR_END を直す")
    else:
        print(f"  ！ {year}年度の年末年始（YEAR_END）がまだありません。12/31〜1/3 を休みとして作ります（仮）。"
              "市の「年末年始のごみ収集日程」が出たら YEAR_END に足して作り直す")
    res = {"year": year, "schedules": {}, "areas": []}
    found, tentative = {}, False
    for name, yomi in DISTRICTS:
        plastic, tables = read_district(folder / "地区のページ" / f"{name}.html")
        mon = monthly(tables, year, name)
        found[name] = (plastic, mon)
        days, moved = {}, {}
        d = dt.date(year, 4, 1)
        while d <= dt.date(year + 1, 3, 31):
            cs = []
            if d.weekday() in (0, 2, 4):
                cs.append("燃やせる")
            if WD[d.weekday()] == plastic:
                cs.append("プラ")
            if cs:
                days[d.isoformat()] = cs
            d += dt.timedelta(days=1)
        for cat in ("燃やせる", "プラ"):
            tentative |= year_end(year, folder, name, cat, days, moved)
        for k, cats in (("不燃", FUNEN_DAY), ("古紙", KOSHI_DAY)):
            for x in mon[k]:
                days.setdefault(x.isoformat(), []).extend(cats)
        order = ["燃やせる", "プラ"] + FUNEN_DAY + KOSHI_DAY
        days = {k: sorted(set(v), key=order.index) for k, v in sorted(days.items()) if v}
        wd_f = sorted({x.weekday() for x in mon["不燃"]})
        wd_k = sorted({x.weekday() for x in mon["古紙"]})
        rule_f = f"月1回（{'・'.join(WD[w] for w in wd_f)}曜日。日はカレンダーで確認）"
        rule_k = f"月1回（{'・'.join(WD[w] for w in wd_k)}曜日。日はカレンダーで確認）"
        res["schedules"][name] = {
            "rules": {"燃やせる": "毎週月・水・金曜日", "プラ": f"毎週{plastic}曜日",
                      **{c: rule_f for c in FUNEN_DAY}, **{c: rule_k for c in KOSHI_DAY}},
            "days": days,
            "moved": moved,
        }
        res["areas"].append({"r": "", "n": name, "s": name, "y": yomi, "d": ""})
    opendata_check(found, year)
    off = (f"{year}-{DEFAULT_OFF[0]}", f"{year + 1}-{DEFAULT_OFF[1]}")
    res["yearEnd"] = {"off": list(off), "tentative": tentative}
    for name, sc in res["schedules"].items():
        print(f"  {name}：{len(sc['days'])}日 プラ {sc['rules']['プラ']}・燃やせないごみの日 "
              f"{sum('不燃' in v for v in sc['days'].values())}回・古紙の日 {sum('古紙' in v for v in sc['days'].values())}回")
    return res
