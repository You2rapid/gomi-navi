"""京都府 長岡京市（26209）：「ごみ減量のしおり」（令和8年度）の家庭ごみの収集地区と「分別収集日程表」から収集日を作る。

このファイルのきまり（どの自治体も同じ形。tools/update_year.py・download_sources.py から使う）:
  NEED                       … 元データ/<県>/<自治体>/<年度>年度/ に置くファイルの名前
  download(year, dest, web, plan) … 市のサイトから NEED のファイルを探して plan に入れる（web は tools/lib/web.py）
  make_calendar(src, year)   … src（上のフォルダ）のファイルから収集日データ（dict）を作る。読めなければ例外で止める

長岡京市の収集日は2つの決まりの組み合わせ：
  家庭ごみ（可燃） … 週2回。町ごとに「月・木曜日」か「火・金曜日」（しおり1ページ・市のページ「長岡京市のごみの出し方」の収集地区の表）。
                      祝日・振替休日も収集する。年末年始は広報長岡京（12月号予定）・アプリ・ホームページで知らせる。
  資源物（分別）   … A類（空きカン・ペットボトル・スプレー缶・ガスボンベ・その他不燃物）とB類（空きビン・筒型乾電池・蛍光灯）を、それぞれ月2回。
                      その他プラスチックは A類・B類どちらの日にも出せる（AB共通）。
                      地域は8つ（しおり5ページ「令和8年度 分別収集日程表」）。日程表に、月ごとの収集日（日付）が書いてある。
しおりの PDF と日程表の PDF は画像だけ（文字が入っていない）なので、日程表の日付を目で読んで、下の SORT_DAYS に書き写した。
書き写しがまちがっていないか、日付の曜日と「第○週」を調べる（合わない日は MOVED に書いた日だけ。ほかは止まる）。
毎年、新しいしおりが出たら（例年3月、広報紙3月号と同時に配布）、SORT_DAYS と AREAS を書き直す。

フォルダ（元データ/26_京都府/26209_長岡京市/<年度>年度/）に置くもの:
  ごみの出し方.html        … 「長岡京市のごみの出し方」のページ（家庭ごみの収集地区の表は文字で入っている）
  ごみ減量のしおり.pdf      … 「令和○年度ごみ減量のしおり」（画像）
  分別収集の日程表.pdf      … 「令和○年4月以降のごみ収集日程」のページの PDF（画像。しおり4・5ページと同じ）
"""
import datetime as dt
import html as H
import re
import unicodedata
from pathlib import Path

SITE = "https://www.city.nagaokakyo.lg.jp"
PAGE = SITE + "/0000011246.html"        # 長岡京市のごみの出し方（しおりの PDF へのリンク）
NITTEI = SITE + "/0000014052.html"      # 令和○年4月以降のごみ収集日程（日程表の PDF へのリンク）
NEED = ["ごみの出し方.html", "ごみ減量のしおり.pdf", "分別収集の日程表.pdf"]
WD = "月火水木金土日"

# ---- 分別収集日程表（令和8年度）の日付。{決まり: {月: [日, …]}}。「－」は書いていない ----
SORT_YEAR = 2026
SORT_DAYS = {
    "第1・3火": {4: [7, 21], 5: [19], 6: [2, 16], 7: [7, 21], 8: [4, 18], 9: [1, 15], 10: [6, 20], 11: [3, 17], 12: [1, 15], 1: [5, 19], 2: [2, 16], 3: [2, 16]},
    "第1・3水": {4: [1, 15], 5: [20], 6: [3, 17], 7: [1, 15], 8: [5, 19], 9: [2, 16], 10: [7, 21], 11: [4, 18], 12: [2, 16], 1: [6, 20], 2: [3, 17], 3: [3, 17]},
    "第1・3木": {4: [2, 16], 5: [7, 21], 6: [4, 18], 7: [2, 16], 8: [6, 20], 9: [3, 17], 10: [1, 15], 11: [5, 19], 12: [3, 17], 1: [7, 21], 2: [4, 18], 3: [4, 18]},
    "第1・3金": {4: [3, 17], 5: [1, 15], 6: [5, 19], 7: [3, 17], 8: [7, 21], 9: [4, 18], 10: [2, 16], 11: [6, 20], 12: [4, 18], 1: [15], 2: [5, 19], 3: [5, 19]},
    "第2・4火": {4: [14, 28], 5: [12, 26], 6: [9, 23], 7: [14, 28], 8: [11, 25], 9: [8, 29], 10: [13, 27], 11: [10, 24], 12: [8, 22], 1: [12, 26], 2: [9, 23], 3: [9, 23]},
    "第2・4水": {4: [8, 22], 5: [13, 27], 6: [10, 24], 7: [8, 22], 8: [12, 26], 9: [9, 30], 10: [14, 28], 11: [11, 25], 12: [9, 23], 1: [13, 27], 2: [10, 24], 3: [10, 24]},
    "第2・4木": {4: [9, 23], 5: [14, 28], 6: [11, 25], 7: [9, 23], 8: [13, 27], 9: [10, 24], 10: [8, 22], 11: [12, 26], 12: [10, 24], 1: [14, 28], 2: [11, 25], 3: [11, 25]},
    "第2・4金": {4: [10, 24], 5: [8, 22], 6: [12, 26], 7: [10, 24], 8: [14, 28], 9: [11, 25], 10: [9, 23], 11: [13, 27], 12: [11, 25], 1: [8, 22], 2: [12, 26], 3: [12, 26]},
}
# 「第○週」の決まりと合わないが、日程表にそう書いてある日（シルバーウィークの祝日の代わりの日。日程表で赤丸）
MOVED = {"2026-09-29": "第2・4火", "2026-09-30": "第2・4水"}
# 日程表の8つの地域：A類の決まり → B類の決まり（同じ行）
ROWS = {1: ("第1・3火", "第2・4火"), 2: ("第1・3水", "第2・4水"), 3: ("第1・3木", "第2・4木"), 4: ("第1・3金", "第2・4金"),
        5: ("第2・4火", "第1・3火"), 6: ("第2・4水", "第1・3水"), 7: ("第2・4木", "第1・3木"), 8: ("第2・4金", "第1・3金")}

# ---- 地区（町）。(地区名, 読み, 家庭ごみの曜日, 分別収集日程表の行) ----
# 地区名は分別収集日程表の地域の書き方。家庭ごみの曜日は、しおり・市のページの収集地区の表（下の check_burn で確かめる）。
# None：市の資料に書いていない（南浦・舞塚は家庭ごみの表にない。浄土谷・調子3丁目は分別収集日程表にない）
AREAS = [
    ("馬場", "ばんば", "月・木", 1), ("神足", "こうたり", "月・木", 1), ("古市（在）", "ふるいち", "月・木", 1),
    ("東神足1・2丁目", "ひがしこうたり", "月・木", 1), ("勝竜寺", "しょうりゅうじ", "月・木", 1), ("南浦", "みなみうら", None, 1),
    ("東和苑", "とうわえん", "月・木", 1), ("城の里", "しろのさと", "月・木", 1),
    ("馬場1・2丁目", "ばんば", "月・木", 2), ("開田1丁目", "かいでん", "月・木", 2), ("神足1丁目", "こうたり", "月・木", 2),
    ("一里塚", "いちりづか", "月・木", 2), ("野添1・2丁目", "のぞえ", "火・金", 2), ("一文橋1・2丁目", "いちもんばし", "月・木", 2),
    ("長岡1〜3丁目", "ながおか", "火・金", 3), ("天神2丁目", "てんじん", "月・木", 3), ("天神4・5丁目", "てんじん", "火・金", 3),
    ("八条が丘", "はちじょうがおか", "火・金", 3), ("舞塚", "まいづか", None, 3),
    ("今里（更ノ町・評町・北ノ町・川原）", "いまざと", "月・木", 4), ("今里3・4丁目", "いまざと", "月・木", 4), ("あかね台", "あかねだい", "月・木", 4),
    ("西の京", "にしのきょう", "月・木", 4), ("柴の里", "しばのさと", "月・木", 4), ("小畑町", "おばたちょう", "月・木", 4),
    ("滝ノ町1・2丁目", "たきのちょう", "火・金", 4),
    ("今里1・2・5丁目", "いまざと", "月・木", 5), ("井ノ内", "いのうち", "月・木", 5), ("今里（南平尾）", "いまざと みなみひらお", "月・木", 5),
    ("長法寺", "ちょうほうじ", "月・木", 5), ("光風台", "こうふうだい", "月・木", 5), ("粟生", "あお", "月・木", 5), ("畑ケ田", "はたけだ", "月・木", 5),
    ("田内", "たうち", "月・木", 5), ("薬師堂", "やくしどう", "月・木", 5), ("うぐいす台", "うぐいすだい", "月・木", 5), ("彦林", "ひこばやし", "月・木", 5),
    ("天神3丁目", "てんじん", "火・金", 6), ("奥海印寺", "おくかいいんじ", "火・金", 6), ("東山", "ひがしやま", "火・金", 6),
    ("太鼓山", "たいこやま", "火・金", 6), ("谷田", "たにだ", "火・金", 6), ("こがねが丘", "こがねがおか", "火・金", 6),
    ("高台1〜4丁目", "たかだい", "火・金", 6), ("高台西", "たかだいにし", "火・金", 6), ("金ケ原", "かながはら", "火・金", 6),
    ("河陽が丘1・2丁目", "かようがおか", "火・金", 6),
    ("天神1丁目", "てんじん", "月・木", 7), ("花山", "はなやま", "火・金", 7), ("梅が丘", "うめがおか", "火・金", 7), ("森ノ下", "もりのした", "火・金", 7),
    ("下海印寺", "しもかいいんじ", "火・金", 7), ("泉が丘", "いずみがおか", "火・金", 7), ("友岡", "ともおか", "火・金", 7),
    ("友岡4丁目", "ともおか", "火・金", 7), ("調子1・2丁目", "ちょうし", "火・金", 7), ("久貝1〜3丁目", "くがい", "火・金", 7),
    ("神足2・3丁目", "こうたり", "月・木", 8), ("開田2〜4丁目", "かいでん", "月・木", 8), ("竹の台", "たけのだい", "月・木", 8),
    ("緑が丘", "みどりがおか", "火・金", 8), ("友岡1〜3丁目", "ともおか", "火・金", 8),
    ("浄土谷", "じょうどだに", "火・金", None), ("調子3丁目", "ちょうし", "火・金", None),
]

# 年末年始の家庭ごみ。広報長岡京（12月号予定）・ホームページで知らせたら、ここに足す。
#   {年度: {"off": ("休みのはじめ", "休みのおわり"), "add": {"2026-12-31": ["月・木"], …}}}（"add"：休みの期間の中で収集する日と、家庭ごみの曜日）
YEAR_END = {}


def clean(t):
    return re.sub(r"[\s　]+", "", unicodedata.normalize("NFKC", t))


def nth_rule(d):
    """日付 → 「第1・3火」のどちらの組か（第1・3 か 第2・4）。第5週は None"""
    n = (d.day - 1) // 7 + 1
    if n == 5:
        return None
    return f"第{'1・3' if n in (1, 3) else '2・4'}{WD[d.weekday()]}"


def sort_dates(year):
    """分別収集日程表 → {決まり: [日付, …]}。曜日・第○週が合わない日は止まる（MOVED の日だけ通す）"""
    if year != SORT_YEAR:
        raise ValueError(f"SORT_DAYS は {SORT_YEAR}年度の日程表です。{year}年度のしおりの日程表を書き写してください")
    out = {}
    for rule, months in SORT_DAYS.items():
        if sorted(months) != list(range(1, 13)):
            raise ValueError(f"{rule}：12か月そろっていません")
        ds = []
        for mo, days in months.items():
            for day in days:
                d = dt.date(year if mo >= 4 else year + 1, mo, day)
                if nth_rule(d) != rule and MOVED.get(d.isoformat()) != rule:
                    raise ValueError(f"{rule} の {d}（{WD[d.weekday()]}曜日）が決まりと合いません。書き写しをまちがえていないか、日程表を見てください")
                ds.append(d)
        out[rule] = sorted(ds)
    return out


def burn_table(path):
    """「長岡京市のごみの出し方」のページの家庭ごみの収集地区の表 → {"月・木": [町名, …], "火・金": [町名, …]}"""
    s = Path(path).read_text(encoding="utf-8", errors="replace")
    t = H.unescape(re.sub(r"<[^>]+>", "\n", s))
    lines = [clean(x) for x in t.split("\n") if clean(x)]
    i = lines.index("収集地区")
    if lines[i + 1:i + 3] != ["月・木曜日", "火・金曜日"]:
        raise ValueError(f"{path}：家庭ごみの収集地区の表が読めません（{lines[i:i + 3]}）")
    return {"月・木": lines[i + 3].split("、"), "火・金": lines[i + 4].split("、")}


def town_parts(name):
    """「長岡1〜3丁目」→ ["長岡1丁目", "長岡2丁目", "長岡3丁目"]、「東神足1・2丁目」→ […1丁目, …2丁目]、ほかはそのまま"""
    n = clean(name).replace("〜", "~").replace("～", "~")
    m = re.fullmatch(r"(.+?)([\d・~]+)丁目", n)
    if not m:
        return [n]
    nums = []
    for part in m[2].split("・"):
        if "~" in part:
            a, b = map(int, part.split("~"))
            nums += list(range(a, b + 1))
        else:
            nums.append(int(part))
    return [f"{m[1]}{k}丁目" for k in nums]


def check_burn(path):
    """AREAS の家庭ごみの曜日が、市のページの収集地区の表と合っているか（合わなければ止まる）"""
    tab = burn_table(path)
    have = {}
    for day, towns in tab.items():
        for t in towns:
            for p in town_parts(t):
                have[p.replace("ヶ", "ケ")] = day
    for name, _, day, _ in AREAS:
        for p in town_parts(name):
            base = re.sub(r"[（(].*?[）)]", "", p).replace("ヶ", "ケ")
            got = have.get(p.replace("ヶ", "ケ")) or have.get(base)
            if day is None:
                if got:
                    raise ValueError(f"「{name}」は家庭ごみの表に {got} とあります（AREAS を直す）")
            elif got != day:
                raise ValueError(f"「{name}」の家庭ごみの曜日が、市の表（{got}）と合いません（AREAS は {day}）")
    return tab


# ---------- ダウンロード ----------
def download(year, dest, web, plan):
    dest = Path(dest)
    raw = web.get(PAGE)
    plan.add(PAGE, dest / "ごみの出し方.html", raw)
    r = year - 2018
    pdf = next((u for u, l in web.links(web.text(raw), PAGE) if u.endswith(".pdf") and f"令和{r}年度ごみ減量のしおり" in clean(l)), None)
    if pdf:
        plan.add(pdf, dest / "ごみ減量のしおり.pdf")
    else:
        plan.problem(f"「令和{r}年度ごみ減量のしおり」が {PAGE} にありません（例年3月）")
    nittei = web.text(web.get(NITTEI))
    if f"令和{r}年4月以降" in nittei:
        pdf = next((u for u, l in web.links(nittei, NITTEI) if u.endswith(".pdf") and "日程表" in clean(l)), None)
        if pdf:
            plan.add(pdf, dest / "分別収集の日程表.pdf")
    else:
        plan.problem(f"「令和{r}年4月以降のごみ収集日程」のページがまだありません（{NITTEI}）")


# ---------- 収集日を作る ----------
def make_calendar(folder, year):
    folder = Path(folder)
    sort = sort_dates(year)
    check_burn(folder / "ごみの出し方.html")
    ye = YEAR_END.get(year)
    tentative = ye is None
    off = (dt.date(year, 12, 31), dt.date(year + 1, 1, 3)) if tentative else tuple(dt.date.fromisoformat(x) for x in ye["off"])
    if tentative:
        print(f"  ！ {year}年度の家庭ごみの年末年始は、まだ市の発表がないので {off[0]}〜{off[1]} を仮に休みにします（YEAR_END に足す）")
    schedules, areas = {}, []
    for name, yomi, burn, row in AREAS:
        key = f"{burn or '家庭ごみ不明'}／{'地域' + str(row) if row else '分別不明'}"
        if key not in schedules:
            days, rules = {}, {}
            if burn:
                wds = [WD.index(w) for w in burn.split("・")]
                d = dt.date(year, 4, 1)
                while d <= dt.date(year + 1, 3, 31):
                    if d.weekday() in wds and not (off[0] <= d <= off[1]):
                        days.setdefault(d.isoformat(), []).append("可燃")
                    d += dt.timedelta(days=1)
                if ye:
                    for k, ws in ye.get("add", {}).items():
                        if burn in ws:
                            days.setdefault(k, []).append("可燃")
                rules["可燃"] = f"毎週{burn}曜日"
            if row:
                a, b = ROWS[row]
                for d in sort[a]:
                    days.setdefault(d.isoformat(), []).extend(["A類", "プラ"])
                for d in sort[b]:
                    days.setdefault(d.isoformat(), []).extend(["B類", "プラ"])
                rules["A類"] = f"{a}曜日"
                rules["B類"] = f"{b}曜日"
                rules["プラ"] = f"第1〜4{a[-1]}曜日（A類・B類の日）"
            order = ["可燃", "A類", "B類", "プラ"]
            schedules[key] = {"rules": rules, "days": {k: sorted(set(v), key=order.index) for k, v in sorted(days.items())}, "moved": {}}
        note = []
        if not burn:
            note.append("家庭ごみ（可燃）の曜日は、市のしおりの収集地区の表にのっていません（市の環境業務課へ）")
        if not row:
            note.append("資源物（分別）の日は、市のしおりの分別収集日程表にのっていません（市の環境業務課へ）")
        areas.append({"n": name, "s": key, "y": yomi, "d": "。".join(note)})
    print(f"長岡京市：地区 {len(areas)}・日程 {len(schedules)}（{'、'.join(schedules)}）")
    return {"year": year, "schedules": schedules, "areas": areas,
            "yearEnd": {"off": [off[0].isoformat(), off[1].isoformat()], "tentative": tentative}}
