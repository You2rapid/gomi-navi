"""山口県 岩国市（35208）：地区ごとの「岩国市ごみ収集カレンダー」PDF から収集日を取り出す。

このファイルのきまり（どの自治体も同じ形。tools/update_year.py・download_sources.py から使う）:
  NEED                       … 元データ/<県>/<自治体>/<年度>年度/ に置くファイルの名前
  download(year, dest, web, plan) … 市のサイトから NEED のファイルを探して plan に入れる（web は tools/lib/web.py）
  make_calendar(src, year)   … src（上のフォルダ）のファイルから収集日データ（dict）を作る。読めなければ例外で止める

市のサイトのつくり（令和8年度）:
  「ごみ・リサイクル」のページ → 「岩国市ごみ収集カレンダー［令和8（2026）年4月～令和9（2027）年3月］」
  → 地域（岩国・由宇・周東・玖珂・錦・美川・美和・本郷）ごとのページ → 地区（町名・字・自治会名）ごとの PDF（約220）。
  PDF は1冊28ページの冊子で、表紙に日程の記号（例：C2）と、その日程の町名が書いてある。
  2〜7ページが収集日のカレンダー（1ページに2か月。左が先の月）。収集の札は文字（焼却ごみ・プラスチック など）。

フォルダ（元データ/35_山口県/35208_岩国市/<年度>年度/）に置くもの:
  地区一覧.json       … 地域のページから作った、地区の名前と PDF の一覧（download が作る）
  地域ページ/*.html   … 地域のページ（地区の名前の元）
  地区のカレンダー/<番号>.pdf … 地区ごとの PDF（番号は市のサイトのファイルの番号）
同じ日程の地区の PDF は中身が同じはずなので、すべて読んで、同じ日程の記号なら収集日も同じか確かめる。
"""
import collections
import datetime as dt
import html
import json
import re
import unicodedata
from pathlib import Path

import pymupdf

SITE = "https://www.city.iwakuni.lg.jp"
TOP = SITE + "/life/1/13/91/"     # ごみ・リサイクル
REGIONS = ["岩国", "由宇", "周東", "玖珂", "錦", "美川", "美和", "本郷"]
NEED = ["地区一覧.json"]

# カレンダーの札の文字 → アプリの区分（city.js の cats）
LABELS = {"焼却ごみ": "焼却", "プラスチック": "プラ", "ペットボトル": "ペット", "びん": "びん", "かん": "かん", "資源品": "資源",
          "金属破砕": "金属", "陶磁器ガラス": "陶磁器", "全品目": "全品目",
          "粗大ごみ戸別有料収集日": "粗大", "粗大ごみ申込締切日": "粗大締切"}
ORDER = ["焼却", "プラ", "ペット", "びん", "かん", "資源", "金属", "陶磁器", "全品目", "粗大", "粗大締切"]
WD = "日月火水木金土"
CODE = r"[A-Z][0-9]?(?:-[0-9])?"   # 日程の記号（C2・F・A4-1 など）
# 札と同じマスに入っている、収集の札でない文字（祝日の名前・お知らせ）
NOT_LABEL = re.compile(r"^(◎|.*の日|.*記念日|元旦|振替休日|国民の休日|天皇誕生日|.*収集、施設は|休み。|★.*|.*ページ参照。?|「.*|〔.*|.*しましょう。?|.*ください。?)$")


def clean(t):
    return re.sub(r"[\s\u3000\u200b\x01]+", "", t)   # 空白・全角空白・見えない文字


# ---------- ダウンロード ----------
def _body_links(web, url):
    page = web.text(web.get(url))
    m = re.search(r"掲載日.*?このページに関するお問い合わせ先", page, re.S)
    return page, (m.group(0) if m else page)


def area_list(region, body):
    """地域のページ → [{"r", "g"（まとめの名前）, "n"（地区名）, "url"}]。
    「南岩国町」「北 [※]」「下久原 [※]」「広瀬 [※]」のように、リンクのない見出しの下に地区が並ぶところは g に見出しを入れる"""
    # 表（<table>）の行ごとに見る。見出しのマスは rowspan（何行ぶんか）で、その下の地区にかかる
    out, group, left = [], "", 0
    for row in re.findall(r"<tr[^>]*>(.*?)</tr>", body, re.S):
        for attrs, cell in re.findall(r"<td([^>]*)>(.*?)</td>", row, re.S):
            links = re.findall(r'<a[^>]+href="([^"]*?/uploaded/attachment/\d+\.pdf)"[^>]*>(.*?)</a>', cell, re.S)
            if links:
                for href, label in links:
                    n = clean(re.sub(r"<[^>]+>", "", html.unescape(label)))
                    if n.count("〔") > n.count("〕") and "〕" in cell:
                        n += "〕"   # 「北門〔釜ヶ原」の「〕」がリンクの外にある
                    out.append({"r": region, "g": group if left > 0 else "", "n": n,
                                "url": href if href.startswith("http") else SITE + href})
                continue
            text = clean(re.sub(r"<[^>]+>", "", html.unescape(cell)))
            text = re.sub(r"\[※\d?\]|【※\d】", "", text)
            # 50音の1文字（あ・か…）・表の見出し・リンク先のない地区（柱島など）は、まとめの見出しでない
            if not text or re.fullmatch(r"[ぁ-ん]|50音|地区名|お住まいの.*", text) or "【※" in cell:
                continue
            m = re.search(r'rowspan="(\d+)"', attrs)
            group, left = text, int(m.group(1)) if m else 1
        left -= 1
    # 表の外のリンク（玖珂地域は「玖珂町全域」の1つだけで、表がない）
    seen = {a["url"] for a in out}
    for href, label in re.findall(r'<a[^>]+href="([^"]*?/uploaded/attachment/\d+\.pdf)"[^>]*>(.*?)</a>', body, re.S):
        url = href if href.startswith("http") else SITE + href
        if url not in seen:
            seen.add(url)
            out.append({"r": region, "g": "", "n": clean(re.sub(r"<[^>]+>", "", html.unescape(label))), "url": url})
    return out


def download(year, dest, web, plan):
    reiwa = year - 2018
    _, body = _body_links(web, TOP)
    cal = [u for u, t in web.links(body, TOP) if f"令和{reiwa}（{year}）年4月" in t.replace("(", "（").replace(")", "）") and "収集カレンダー" in t]
    if not cal:
        plan.problem(f"「岩国市ごみ収集カレンダー［令和{reiwa}（{year}）年4月～］」のページが {TOP} に見つかりません")
        return
    _, cbody = _body_links(web, cal[0])
    region_pages = {t.strip(): u for u, t in web.links(cbody, cal[0]) if t.strip() in REGIONS}
    lack = [r for r in REGIONS if r not in region_pages]
    if lack:
        plan.problem(f"地域のページが見つかりません：{'・'.join(lack)}（{cal[0]}）")
        return
    areas = []
    for r in REGIONS:
        page, body = _body_links(web, region_pages[r])
        plan.add(region_pages[r], dest / "地域ページ" / f"{r}.html", page.encode("utf-8"))
        for a in area_list(r, body):
            a["file"] = "地区のカレンダー/" + a["url"].rsplit("/", 1)[-1]
            areas.append(a)
    for u in sorted({a["url"] for a in areas}):
        plan.add(u, dest / "地区のカレンダー" / u.rsplit("/", 1)[-1])
    index = {"year": year, "page": cal[0], "regions": region_pages, "areas": areas}
    plan.add(cal[0], dest / "地区一覧.json", json.dumps(index, ensure_ascii=False, indent=1).encode("utf-8"))


# ---------- PDF の読み取り ----------
def spans(page):
    for b in page.get_text("dict")["blocks"]:
        for ln in b.get("lines", []):
            for sp in ln["spans"]:
                t = sp["text"].strip()
                if t:
                    yield sp["bbox"], sp["size"], t


def cover(doc):
    """表紙 → (地域, 日程の記号, 町名の文)。日程の記号は表紙の左下の大きな文字（例：C2・E2・Ⅰ1・A4-1）"""
    sp = [(b, s, unicodedata.normalize("NFKC", t)) for b, s, t in spans(doc[0])]   # 「Ⅰ1」（ローマ数字のⅠ）→「I1」
    region = next((t for b, s, t in sp if 20 < s < 24 and t.endswith("地域")), "")
    codes = [(b, t.split()[0]) for b, s, t in sp if s > 28 and b[1] > 400 and re.fullmatch(CODE, t.split()[0])]
    if not codes:
        # 表紙の文字が少ない PDF（行波（荒瀬谷）など）は、表紙の文字だけで書いてある
        codes = [(b, t) for b, s, t in sp if re.fullmatch(CODE, t)]
    if not codes:
        raise SystemExit("表紙に日程の記号（C2 など）が見つかりません")
    cb, code = codes[0]
    towns = [t for b, s, t in sp if b[1] >= cb[1] - 30 and b[0] > cb[0] and s > 16 and t != code and "地域" not in t]
    towns = [t[len(code):].strip() if t.startswith(code + " ") else t for t in towns]
    return region.replace("地域", ""), code, " ".join(t.strip() for t in towns if t.strip())


def grid(page, half, yy, mm):
    """カレンダーのマス：曜日の列の左はし（7つ）と、日付の数字の位置 [(bbox, 列, 日付)]。数字が文字でない PDF は None"""
    W = page.rect.width
    x0, x1 = half * W / 2, half * W / 2 + W / 2
    sp = [x for x in spans(page) if x0 <= x[0][0] < x1]
    heads = sorted([b for b, s, t in sp if s > 25 and t in WD], key=lambda b: b[0])
    if not heads:
        return None
    if len(heads) != 7:
        raise SystemExit(f"{yy}年{mm}月：曜日の見出しが {len(heads)} 個（7個のはず）")
    cx = [b[0] - 12 for b in heads]   # 列の左はし
    dates = []
    for b, s, t in sp:
        if 16 < s < 18.5 and re.fullmatch(r"\d{1,2}", t) and b[1] > 130:
            c = col_of(cx, b[0])
            d = dt.date(yy, mm, int(t))
            if (d.weekday() + 1) % 7 != c:
                raise SystemExit(f"{d} の曜日が列と合いません（列 {c}）")
            dates.append((b, c, d))
    last = (dt.date(yy + (mm == 12), mm % 12 + 1, 1) - dt.timedelta(days=1)).day
    got = sorted(d.day for _, _, d in dates)
    if got != list(range(1, last + 1)):
        raise SystemExit(f"{yy}年{mm}月：日付がそろいません {got}")
    return cx, dates


def col_of(cx, x):
    cs = [i for i in range(7) if x >= cx[i]]
    return cs[-1] if cs else None


def _lines(vals, gap=1.5):
    """黒い線の位置（ピクセルの並び）を、となりどうしでまとめて真ん中の位置にする"""
    g = []
    for v in vals:
        if g and v - g[-1][-1] <= gap:
            g[-1].append(v)
        else:
            g.append([v])
    return [sum(x) / len(x) for x in g]


def image_grid(page, half, yy, mm):
    """曜日や日付が絵（スキャンした画像）の PDF（行波（荒瀬谷）など）：絵の中の黒い罫線からマスの位置を出す。
    マスは 7列 × 5段（6週ある月は、5段目に2つの日付が入る）"""
    z = 2
    pm = page.get_pixmap(matrix=pymupdf.Matrix(z, z), colorspace=pymupdf.csGRAY)
    W, smp = pm.width, pm.samples
    xa, xb = int((40 + half * 410) * z), int((390 + half * 410) * z)
    hs = []
    for y in range(int(130 * z), int(470 * z)):
        row = smp[y * W + xa:y * W + xb]
        if sum(1 for v in row if v < 110) > len(row) * 0.8:
            hs.append(y / z)
    hs = [y for y in _lines(hs) if y < 430]
    if len(hs) < 3:
        raise SystemExit(f"{yy}年{mm}月：マスの横線が見つかりません")
    k = round((hs[-1] - hs[0]) / 52)
    h = (hs[-1] - hs[0]) / k
    top = hs[0] - h * round((hs[0] - 160) / h)       # 1段目の上の線（だいたい 160 のところ）
    if not 150 < top < 172 or any(abs((y - top) / h - round((y - top) / h)) > 0.08 for y in hs):
        raise SystemExit(f"{yy}年{mm}月：マスの横線の間がそろいません {hs}")
    vs = []
    for x in range(int((half * 410 + 10) * z), int((half * 410 + 410) * z)):
        col = [smp[y * W + x] for y in range(int((top + 5) * z), int((top + 5 * h - 5) * z), 2)]
        if sum(1 for v in col if v < 110) > len(col) * 0.8:
            vs.append(x / z)
    vs = _lines(vs)
    # 外がわの太い線（左はし・右はし）から、7列に等しく分ける（中の線は、字がかぶって見つからないことがある）
    if len(vs) < 2 or not 360 < vs[-1] - vs[0] < 400:
        raise SystemExit(f"{yy}年{mm}月：マスの左右の線が見つかりません {vs}")
    w = (vs[-1] - vs[0]) / 7
    if any(abs((v - vs[0]) / w - round((v - vs[0]) / w)) > 0.08 for v in vs):
        raise SystemExit(f"{yy}年{mm}月：マスの縦線の間がそろいません {vs}")
    cx = [vs[0] + w * i for i in range(7)]
    first = dt.date(yy, mm, 1)
    off = (first.weekday() + 1) % 7
    dates = []
    last = (dt.date(yy + (mm == 12), mm % 12 + 1, 1) - dt.timedelta(days=1)).day
    six = (off + last + 6) // 7 == 6
    for day in range(1, last + 1):
        d = dt.date(yy, mm, day)
        c, r = (off + day - 1) % 7, (off + day - 1) // 7
        y0 = top + h * min(r, 4) + (h / 2 if r == 5 else 0)
        y1 = top + h * (min(r, 4) + 1) - (h / 2 if six and r == 4 and day + 7 <= last else 0)
        dates.append(((cx[c], y0 + 6, cx[c] + 50, y1, "絵"), c, d))   # 5つ目の「絵」：下はしまでがマス
    return cx, dates


def month_days(page, half, yy, mm):
    """1ページの左（half=0）か右（half=1）の月 → {日付: [区分]}"""
    g = grid(page, half, yy, mm) or image_grid(page, half, yy, mm)
    cx, dates = g
    W = page.rect.width
    x0, x1 = half * W / 2, half * W / 2 + W / 2
    words = collections.defaultdict(list)
    for b, s, t in spans(page):
        if not (x0 <= b[0] < x1) or b[1] < 135 or not 4 <= s < 12:
            continue
        c = col_of(cx, b[0])
        # その列で、札の上はしより上にある日付のうち、いちばん下のもの（マスの高さは約62。絵の PDF はマスの下はしまで）
        cand = [(db, d) for db, dc, d in dates if dc == c and db[1] - 6 <= b[1] <= (db[3] if len(db) == 5 else db[1] + 62)]
        if cand:
            words[max(cand, key=lambda x: x[0][1])[1]].append((round(b[1]), clean(t)))
    out, unknown = {}, []
    for d, wl in words.items():
        # 1文字ずつの文字（「び」「ん」「資」「源」「品」）は、同じ行どうしをつなぐ
        ws = []
        for i, (y, w) in enumerate(wl):
            if len(w) == 1 and i and len(wl[i - 1][1]) == 1 and abs(wl[i - 1][0] - y) < 2 and ws:
                ws[-1] += w
            else:
                ws.append(w)
        ks, i = [], 0
        while i < len(ws):
            w = ws[i]
            nxt = ws[i + 1] if i + 1 < len(ws) else ""
            if w in ("金属", "陶磁器", "粗大ごみ") and nxt in ("破砕", "ガラス") or w == "粗大ごみ" and re.fullmatch(r"戸別有料[収取]集日|申込締切日", nxt):
                w, i = w + nxt, i + 1
            w = w.replace("取集日", "収集日")   # PDF の書きまちがい（取集日）
            if w in LABELS:
                ks.append(LABELS[w])
            elif not NOT_LABEL.match(w):
                unknown.append(f"{d} {w}")
            i += 1
        if ks:
            out[d] = sorted(set(ks), key=ORDER.index)
    if unknown:
        raise SystemExit("知らない札があります（LABELS か NOT_LABEL に足す）：" + "、".join(unknown))
    return out


def read_pdf(path, year):
    doc = pymupdf.open(path)
    ms = [(year, m) for m in range(4, 13)] + [(year + 1, m) for m in range(1, 4)]
    days = {}
    for i in range(6):
        for half in range(2):
            yy, mm = ms[2 * i + half]
            days.update(month_days(doc[i + 1], half, yy, mm))
    return cover(doc), days


def rules_of(days):
    # 区分ごとに「毎週◯曜日」「毎月第◯◯曜日」などにまとめる（光市と同じ考え方）
    occ = collections.defaultdict(list)
    for d, ks in days.items():
        for c in ks:
            occ[c].append(d)
    rules, moved = {}, collections.defaultdict(list)
    for c in ORDER:
        ds = occ.get(c)
        if not ds:
            continue
        wds = collections.Counter((d.weekday() + 1) % 7 for d in ds)
        main = sorted(w for w, n in wds.items() if n >= len(ds) * 0.25)
        for d in ds:
            if (d.weekday() + 1) % 7 not in main:
                moved[d.isoformat()].append(c)
        wtxt = "・".join(WD[w] for w in main)
        per = sum(wds[w] for w in main) / len(main)
        nth = collections.Counter((d.day - 1) // 7 + 1 for d in ds if (d.weekday() + 1) % 7 in main)
        if per >= 40:
            rules[c] = f"毎週{wtxt}曜日"
        elif len(main) == 1 and len(nth) <= 2 and all(n >= 10 for n in nth.values()):
            rules[c] = f"毎月第{'・'.join(map(str, sorted(nth)))}{wtxt}曜日"
        else:
            rules[c] = f"月{max(1, round(len(ds) / 12))}回 {wtxt}曜日" if len(ds) >= 10 else f"年{len(ds)}回（日はカレンダーで確認）"
    return rules, {k: sorted(v, key=ORDER.index) for k, v in sorted(moved.items())}


def area_name(a):
    """地区一覧の1行 → アプリの地区名（まとめの見出しがあれば「見出し（地区）」、南岩国町は「南岩国町一丁目1～23番」）"""
    n, g = a["n"], a["g"]
    if not g:
        return n
    if re.match(r"^[一二三四五六七八九]丁目", n):
        return g + n
    return f"{g}（{n}）"


def yomi_of(n):
    """地区名のよみ（ひらがな）。【JR岩徳線より北】や番地（1～23番など）はよみに入れない"""
    import kana   # tools/lib（update_year.py から呼ばれるときは読み込める）
    n = re.sub(r"【.*?】|[（(]?[0-9０-９].*$", "", n)
    return kana.yomi(re.sub(r"[（）()]", " ", n)).strip()


def make_calendar(folder, year):
    folder = Path(folder)
    index = json.loads((folder / "地区一覧.json").read_text(encoding="utf-8"))
    if index["year"] != year:
        raise SystemExit(f"地区一覧.json の年度が {index['year']} です")
    by_code, covers = {}, {}
    for f in sorted({a["file"] for a in index["areas"]}):
        p = folder / f
        if not p.exists():
            raise SystemExit(f"PDF がありません：{p}（download_sources.py で保存する）")
        (region, code, towns), days = read_pdf(p, year)
        covers[f] = (region, code, towns)
        if code not in by_code:
            by_code[code] = (f, days)
        elif days != by_code[code][1]:
            # 同じ日程の記号なのに収集日がちがう（記号の読みまちがいか、市の PDF のまちがい）
            raise SystemExit(f"同じ日程 {code} なのに収集日がちがう PDF があります：{f} と {by_code[code][0]}")
    res = {"year": year, "schedules": {}, "areas": []}
    for code in sorted(by_code):
        f, days = by_code[code]
        rules, moved = rules_of(days)
        res["schedules"][code] = {"rules": rules, "days": {d.isoformat(): ks for d, ks in sorted(days.items())}, "moved": moved}
        print(code, f, len(days), "日", rules)
    names = collections.Counter()
    for a in index["areas"]:
        region, code, towns = covers[a["file"]]
        if region and region != a["r"]:
            raise SystemExit(f"{a['n']}：地域のページは {a['r']}、PDF の表紙は {region}")
        n = area_name(a)
        names[(a["r"], n)] += 1
        res["areas"].append({"r": a["r"], "n": n, "s": code, "y": yomi_of(n)})
    dup = [n for n, c in names.items() if c > 1]
    if dup:
        raise SystemExit(f"同じ地域に同じ名前の地区があります：{dup}")
    print("地区", len(res["areas"]), "日程", len(res["schedules"]))
    return res
