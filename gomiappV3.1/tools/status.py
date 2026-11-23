"""自治体ごとのデータの状況を1枚の表（状況一覧）にする。

使い方（gomi フォルダで実行）:
  python gomiappV3.1/tools/status.py          ← 元データ/状況一覧.html を作る（ブラウザで開いて見る）
  python gomiappV3.1/tools/status.py --web    ← あわせて、市のサイトに次の年度のカレンダーが出ているかも調べる（少し時間がかかる）
  python gomiappV3.1/tools/status.py --date=2027-04-10   ← その日に見たらどうなるかを試す

表に出すもの:
  収集日（何年度か・地区の数・祝日のデータと年度が合っているか）、品目（件数・区分の書きまちがい）、
  設定（区分・色）、今いる場所から探す（町の数・地区が決まらない町の数）、
  元データ（今の年度と次の年度のファイルがそろっているか・分別の冊子・地図）、道具（calendar.py・geo.py・README）、
  商用利用（license.json：使っている資料の利用条件・許可が必要か・確かめた日）と、オープンデータを使っているか・古くなっていないか、
  住所（郵便番号一覧の正式な町名とくらべて、収集日の地区が見つからない町・収集日の町名が正式な町名に無いもの・PDF の読み取りで気になったところ）
"""
import datetime as dt
import html
import json
import re
import sys
import unicodedata
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)
sys.path.insert(0, str(Path(__file__).resolve().parent / "lib"))
import munis as M  # noqa: E402

OK, WARN, BAD = "ok", "warn", "bad"
INFO = "info"   # 知っておくこと（数えない）


def fiscal_year(d):
    return d.year if d.month >= 4 else d.year - 1


def reiwa(y):
    return f"令和{y - 2018}年度"


def check_muni(m, now_fy, holidays_year, geo_cities, web=None, today=None, zips=None):
    """1つの自治体を調べて、(列ごとの [状態, 表示, くわしく]) と、気をつけることの一覧を返す"""
    notes, row = [], {}
    today = today or dt.date.today()

    def note(level, text, how=None, key=None):
        """how：クリックで開く「どうすればよいか」（HTML）。なければ自治体の README.md を案内する"""
        notes.append((level, text, how or f"<p>くわしくは <code>gomiappV3.1/tools/munis/{h(m.path)}/README.md</code> を見てください。</p>", key))

    # ---- 設定（city.js）----
    try:
        city = m.read("city")
        cats = city["cats"]
        bad_order = [c for c in city.get("order", []) if c not in cats] + [c for c in city.get("calOrder", []) if c not in cats]
        no_color = [k for k, c in cats.items() if not c.get("color")]
        lv = BAD if bad_order or no_color else OK
        if bad_order:
            note(BAD, f"city.js：order・calOrder に、cats にない区分があります（{'・'.join(bad_order)}）")
        if no_color:
            note(BAD, f"city.js：色のない区分があります（{'・'.join(no_color)}）")
        row["city"] = (lv, f"区分 {len(cats)}", f"出す時刻 {city['cut'][0]}:{city['cut'][1]:02d}")
    except Exception as e:
        city, cats = None, {}
        row["city"] = (BAD, "読めません", str(e))
        note(BAD, f"city.js が読めません：{e}")

    # ---- 収集日（calendar.js）----
    try:
        cal = m.read("calendar")
        y = cal["year"]
        days = sum(len(s["days"]) for s in cal["schedules"].values())
        unknown = sorted({c for s in cal["schedules"].values() for ks in s["days"].values() for c in ks if c not in cats})
        lv = OK
        detail = f"地区 {len(cal['areas'])}・日程 {len(cal['schedules'])}"
        if y < now_fy:
            lv = BAD
            note(BAD, f"収集日が {reiwa(y)} のままです（今は {reiwa(now_fy)}）",
                 steps(f"市のサイトから新しいカレンダーを保存：<code>python gomiappV3.1/tools/download_sources.py {now_fy}</code>",
                       f"収集日を作り直す：<code>python gomiappV3.1/tools/update_year.py {now_fy}</code>",
                       "アプリをブラウザで開いて、いくつかの地区を市のカレンダーと見くらべる",
                       "GitHub Desktop で Commit → Push origin"))
        if y != holidays_year:
            lv = max(lv, WARN, key=[OK, WARN, BAD].index)
            note(WARN, f"収集日（{reiwa(y)}）と祝日のデータ（{reiwa(holidays_year)}）の年度がちがいます",
                 steps(f"内閣府の「国民の祝日」CSV を <code>元データ/全国/{y}年度/syukujitsu.csv</code> に保存する（download_sources.py でも保存される）",
                       f"<code>python gomiappV3.1/tools/update_year.py {y}</code> で作り直す"))
        if unknown:
            lv = BAD
            note(BAD, f"calendar.js に city.js にない区分があります（{'・'.join(unknown)}）")
        ye = cal.get("yearEnd") or {}
        if ye.get("tentative"):
            lv = max(lv, WARN, key=[OK, WARN, BAD].index)
            note(WARN, f"年末年始の休みが仮（{'〜'.join(ye.get('off', []))}）のままです",
                 steps("市のホームページで「年末年始の家庭ごみ収集の日程」を探す（毎年10〜11月ごろに出る）",
                       f"<code>gomiappV3.1/tools/munis/{h(m.path)}/calendar.py</code> の <code>YEAR_END</code> に、休みの期間と、その日だけ収集しない区分を足す",
                       f"<code>python gomiappV3.1/tools/update_year.py {y} {m.code}</code> で作り直す"))
        empty = [s for s, v in cal["schedules"].items() if not v["days"]]
        if empty:
            lv = BAD
            note(BAD, f"収集日が1日もない日程があります（{'・'.join(empty)}）")
        row["cal"] = (lv, reiwa(y), detail)
    except Exception as e:
        cal = None
        row["cal"] = (BAD, "読めません", str(e))
        note(BAD, f"calendar.js が読めません：{e}")

    # ---- 品目（items.js）----
    try:
        items = m.read("items")
        names = [x[0] if isinstance(x, list) else x["n"] for x in items]
        cs = [x[1] if isinstance(x, list) else x["c"] for x in items]
        bad_c = sorted({c for c in cs if c not in cats})
        no_read = sum(1 for x in items if isinstance(x, list) and not x[2])
        lv = BAD if bad_c else (WARN if len(items) < 100 else OK)
        if bad_c:
            note(BAD, f"items.js に city.js にない区分があります（{'・'.join(bad_c)}）")
        if len(items) < 100:
            note(WARN, f"品目が {len(items)} 件と少なめです（冊子の例だけなど）",
                 "<p>オープンデータの「ゴミの分別方法一覧」があれば、それに切り替えると品目が増えます（<code>opendata.py</code>）。"
                 "なければ市の分別の冊子から足します。</p>")
        if no_read:
            note(WARN, f"読み（ひらがな）のない品目が {no_read} 件あります（ひらがなで探せません）")
        dup = len(names) - len(set(names))
        mk = m.module("make_items")
        bk = getattr(mk, "BOOKLET", None) if mk else None
        src = ""
        if bk and Path(bk).exists():
            nb = sum(1 for x in Path(bk).read_text(encoding="utf-8").splitlines() if x.strip() and not x.startswith("#"))
            src = f"冊子（{getattr(mk, 'BOOKLET_DATE', '')}）{nb}件＋ほか {max(len(items) - nb, 0)}件"
            bdate = getattr(mk, "BOOKLET_DATE", "")
            if bdate and (today - dt.date.fromisoformat(bdate + "-01")).days > 400:
                note(WARN, f"品目の元にした冊子「{getattr(mk, 'BOOKLET_TITLE', '')}」（{bdate}）から1年以上たっています",
                     steps("市のホームページで、新しい冊子（毎年3月ごろ）が出ていないか見る",
                           f"出ていたら元データに保存して、<code>gomiappV3.1/tools/munis/{h(m.path)}/{h(Path(bk).name)}</code> を新しい冊子と見くらべて直す（Claude に頼む）",
                           f"<code>python gomiappV3.1/tools/munis/{h(m.path)}/make_items.py</code> で作り直す"))
        row["items"] = (lv, f"{len(items):,} 件", "・".join(x for x in [src, f"同じ名前 {dup} 件" if dup else ""] if x))
    except Exception as e:
        row["items"] = (BAD, "読めません", str(e))
        note(BAD, f"items.js が読めません：{e}")

    # ---- 今いる場所から探す（geo）----
    g = geo_cities.get(m.code)
    if not g:
        has_tool = (m.tool_dir / "geo.py").exists()
        row["geo"] = (WARN, "なし", "geo.py はある（build_geo.py を実行）" if has_tool else "geo.py がない")
        note(WARN, "今いる場所から探すの地図がありません")
    else:
        towns = g["towns"]
        if "line" in g:
            row["geo"] = (OK, f"町丁 {len(towns)}", f"境目の線で{'・'.join(g.get('sides', []))}")
        else:
            none = sum(1 for t in towns if not t.get("c"))
            row["geo"] = (OK if none <= len(towns) * 0.1 else WARN, f"町丁 {len(towns)}", f"地区が決まらない町 {none}")
            if none > len(towns) * 0.1:
                note(WARN, f"地区が決まらない町が {none} あります",
                     steps(f"<code>gomiappV3.1/tools/munis/{h(m.path)}/geo.py</code> の町名と地区の対応表を見直す",
                           f"<code>python gomiappV3.1/tools/build_geo.py {m.pref}</code> で作り直す"))

    # ---- 住所（郵便番号・PDF の読み取り）----
    address_check(m, cal, g, zips, row, note)
    # 住所の列から飛べるように、住所の最初の注意に印（addr-<コード>）を付ける
    i = next((i for i, n in enumerate(notes) if n[1].startswith("住所：") and not n[3]), None)
    if i is not None:
        notes[i] = notes[i][:3] + (f"addr-{m.code}",)

    # ---- 元データ ----
    mod = m.module("calendar")
    need = getattr(mod, "NEED", []) if mod else []
    years = sorted(int(p.name[:4]) for p in m.src_dir.glob("*年度") if p.name[:4].isdigit()) if m.src_dir.exists() else []
    def complete(y):
        return need and all((m.year_dir(y) / f).exists() for f in need)
    # アプリの収集日の年度（データの元）と、その次の年度（次に入れるもの）
    cal_y = cal["year"] if cal else now_fy
    next_y = cal_y + 1
    cur_ok, next_ok = complete(cal_y), complete(next_y)
    books = sorted(p.name for p in (m.src_dir / "分別の冊子").glob("*")) if (m.src_dir / "分別の冊子").exists() else []
    mk = m.module("make_items")
    if mk and getattr(mk, "BOOKLET_PDF", None):   # 冊子を年度のフォルダなどに置いているとき（京都市）
        if (m.src_dir / mk.BOOKLET_PDF).exists():
            books.append(Path(mk.BOOKLET_PDF).name)
        else:
            note(WARN, f"品目の元にした冊子が元データにありません（{mk.BOOKLET_PDF}）",
                 f"<p>市のサイトから冊子（PDF）を保存して、<code>元データ/{h(m.src_dir.relative_to(M.SOURCES).as_posix())}/{h(mk.BOOKLET_PDF)}</code> に置きます。</p>")
    kml = (m.src_dir / "地図" / f"r2ka{m.code}.kml").exists() or any((m.src_dir / "地図").glob("r2ka*.kml"))   # 区のある市は区ごとの地図
    lv = OK if cur_ok and books and kml else WARN
    if not cur_ok:
        note(WARN, f"今の収集日の元にした 元データ/{m.src_dir.relative_to(M.SOURCES).as_posix()}/{cal_y}年度/ のファイルがそろっていません",
             steps(f"<code>python gomiappV3.1/tools/download_sources.py {cal_y} {m.code}</code> で保存し直す",
                   "市のサイトにもう無いときは、なくてもアプリは動きます。足りないファイル：" + h("・".join(f for f in need if not (m.year_dir(cal_y) / f).exists()))))
    if not books and not m.module("make_items"):
        note(WARN, "分別の冊子（品目の元にした資料）が元データにありません",
             f"<p>市のサイトから分別の冊子（PDF）を保存して、<code>元データ/{h(m.src_dir.relative_to(M.SOURCES).as_posix())}/分別の冊子/</code> に置きます。</p>")
    if not kml:
        note(WARN, "地図（e-Stat の KML）が元データにありません",
             f"<p>e-Stat（政府統計の総合窓口）の「境界データ」で、国勢調査の小地域（町丁・字等）の {m.code} の KML を保存し、"
             f"<code>元データ/{h(m.src_dir.relative_to(M.SOURCES).as_posix())}/地図/r2ka{m.code}.kml</code> に置きます。</p>")
    row["src"] = (lv, "・".join(f"{y}" for y in years) + "年度" if years else "なし",
                  f"冊子 {len(books)}・地図 {'あり' if kml else 'なし'}" + (f"・{next_y}年度そろっている" if next_ok else ""))

    # ---- 道具 ----
    tools = [n for n in ("calendar.py", "geo.py", "README.md") if (m.tool_dir / n).exists()]
    can_dl = bool(mod and hasattr(mod, "download"))
    row["tools"] = (OK if len(tools) == 3 and can_dl else WARN, f"{len(tools)}/3", "自動ダウンロード" + ("あり" if can_dl else "なし"))
    if not can_dl:
        note(WARN, "calendar.py に download がありません（毎年、手でダウンロード）",
             f"<p>毎年4月に、<code>gomiappV3.1/tools/munis/{h(m.path)}/README.md</code> のダウンロード元から手で保存します。"
             "自動にしたいときは、calendar.py に download を書きます（ほかの自治体のものをまねる）。</p>")

    # ---- 商用利用（license.json）と、使っているオープンデータ ----
    od_used = list(dict.fromkeys(_opendata_used(m, web, note, today)))
    od_text = "オープンデータ：" + ("・".join(od_used) if od_used else "なし")
    lic_file = m.tool_dir / "license.json"
    if lic_file.exists():
        try:
            lic = json.loads(lic_file.read_text(encoding="utf-8"))
            judge = lic.get("商用利用", "要確認")
            checked = lic.get("確認した日", "")
            asked = lic.get("許可の記録", [])
            need = [d["データ"] for d in lic.get("データごと", []) if d.get("商用利用") in ("要許可", "要確認")]
            lv = OK if judge in ("可", "出典表示で可") else BAD if judge == "要許可" and not asked else WARN
            detail = od_text + "／" + (f"{'・'.join(need)}が{judge}" if need else "すべて使える") + (f"（確認 {checked}）" if checked else "")
            row["lic"] = (lv, judge, detail)
            if need:
                note(WARN, f"商用利用：{'・'.join(need)}は{judge}", lic_how(m, lic), key=f"lic-{m.code}")
            try:
                if checked and (today - dt.date.fromisoformat(checked)).days > 365:
                    pages = [lic.get("サイトの利用条件", {}), lic.get("オープンデータの方針", {})]
                    note(WARN, f"商用利用：利用条件を確かめてから1年以上たっています（{checked}）",
                         steps(*[f'<a href="{h(x["URL"])}" target="_blank" rel="noopener">{h(x["URL"])}</a> を開いて、書いてあることが変わっていないか見る' for x in pages if x.get("URL")],
                               f"変わっていなければ <code>gomiappV3.1/tools/munis/{h(m.path)}/license.json</code> の「確認した日」を今日の日付にする。変わっていたら中身も直す"))
            except ValueError:
                note(WARN, f"license.json の「確認した日」が日付になっていません（{checked}）")
        except Exception as e:
            row["lic"] = (BAD, "読めません", str(e))
            note(BAD, f"license.json が読めません：{e}")
    else:
        row["lic"] = (WARN, "未調査", od_text + "／license.json なし")
        note(WARN, "商用利用：license.json がありません（使っている資料の利用条件を調べて書く）",
             "<p>ほかの自治体の <code>license.json</code> をまねて、使っている資料ごとに、利用条件・判定・問い合わせ先を書きます（書き方は <code>gomiappV3.1/tools/README.md</code> の「商用利用」）。</p>")

    # ---- 次の年度（アプリに入っている年度の次）のカレンダーが市のサイトに出ているか ----
    if web and getattr(mod, "PERENNIAL", False):
        # 町ごとの曜日で決まる市（京都市など）は毎年のカレンダーがない。年末年始は「収集日」の列で見る
        row["next"] = (OK, "毎年同じ", "曜日で決まる（年末年始だけ毎年足す）")
    elif web and can_dl:
        import web as W
        plan = W.Plan()
        try:
            mod.download(next_y, m.year_dir(next_y), W, plan)
            found = not plan.problems
        except Exception as e:
            found, plan.problems = False, [str(e)]
        late = next_y <= now_fy   # もう始まっている年度なのに、まだ出ていない
        row["next"] = ((OK if found or not late else BAD), f"{reiwa(next_y)}：" + ("出ている" if found else "まだ"),
                       ("download_sources.py で保存できます" if not next_ok else "保存ずみ") if found else (plan.problems[0][:60] if plan.problems else ""))
        if found and not next_ok:
            note(WARN, f"{reiwa(next_y)}のカレンダーが市のサイトに出ています",
                 steps(f"<code>python gomiappV3.1/tools/download_sources.py {next_y}</code>",
                       f"<code>python gomiappV3.1/tools/update_year.py {next_y}</code>（4月より前に試すときは、アプリのアドレスに <code>?date={next_y}-04-01</code> を付けて見る）",
                       "GitHub Desktop で Commit → Push origin"))
        if not found and late:
            note(BAD, f"{reiwa(next_y)}が始まっているのに、市のサイトで新しいカレンダーが見つかりません",
                 steps(f"<code>gomiappV3.1/tools/munis/{h(m.path)}/README.md</code> のダウンロード元のページをブラウザで開く",
                       "ページの場所やファイルの名前が変わっていたら、calendar.py の download を直す（Claude に頼む）",
                       "見つからない理由：" + h(plan.problems[0] if plan.problems else "不明")))
    elif web:
        row["next"] = (WARN, "調べられません", "自動ダウンロードなし")
    return row, notes


h = html.escape   # HTML の文字にする（e は例外の名前に使っているので h）


# ---------------- 住所（郵便番号一覧の町名＝市の正式な町名との照合。元データ/全国/郵便番号/県別/、tools/build_zip.py で作る） ----------------
_CHOME = re.compile(r"[0-9一二三四五六七八九十]+丁目([~〜～][0-9一二三四五六七八九十]+丁目)?$")
TOWN_VAR = str.maketrans({"薮": "藪", "菴": "庵", "峯": "峰", "龍": "竜", "斉": "斎", "槇": "槙", "桧": "檜", "曽": "曾",
                          "渕": "淵", "圓": "円", "阪": "坂", "篭": "籠", "檀": "壇"})


def tkey(x):
    """町名をくらべる形：大字・（1）・（通りの側など）・全域を取り、カタカナをひらがなに、
    ヶ→け、之→の、異体字（薮→藪 など）、通り→通"""
    x = re.sub(r"全域$", "", re.sub(r"（[^）]*）$", "", re.sub(r"（\d+）$", "", re.sub(r"^大字", "", x))))
    out = ""
    for c in unicodedata.normalize("NFKC", x).lower():
        if "\u30a1" <= c <= "\u30f6":
            c = chr(ord(c) - 0x60)
        if re.match(r"[\s・･、,。]", c):
            continue
        out += c
    return out.replace("ゖ", "け").replace("ヶ", "け").replace("之", "の").translate(TOWN_VAR).replace("通り", "通")


def same_town(area, t):
    a, b = tkey(area), tkey(t)
    return a == b or _CHOME.sub("", a) == b


def geo_town(n, t):
    a, b = _CHOME.sub("", tkey(n)), tkey(t)
    return a == b or (len(b) >= 3 and a.endswith(b))


def names_html(xs, limit=80):
    more = f"<br>…ほか {len(xs) - limit}" if len(xs) > limit else ""
    return "<p>" + "、".join(h(x) for x in xs[:limit]) + more + "</p>"


def address_check(m, cal, g, zips, row, note):
    """住所の列：正式な町（郵便番号一覧）で収集日の地区が見つからない町、収集日の町名が正式な町名に無いもの、PDF の読み取りで気になったところ"""
    if not cal:
        return
    areas = cal["areas"]
    z = (zips or {}).get(m.pref)
    lv, parts, main = OK, [], "照合なし（郵便番号一覧がない）"
    if z:
        # この自治体の郵便番号の町（政令市は区ごと。区はアプリの「地域」）
        towns = {}
        for v in z["zips"].values():
            for e in v:
                c = e["c"]
                if e.get("t") and (c == m.code or (c[:3] + "00" == m.code and c != m.code)):
                    ward = z["cities"][c]["n"].replace(m.name, "") if c != m.code else ""
                    towns.setdefault((ward, e["t"]), None)
        regions = {a.get("r", "") for a in areas}
        miss = []
        for ward, t in towns:
            reg = ward if ward in regions else ""
            ok = any((not reg or a.get("r") == reg) and same_town(a["n"], t) for a in areas)
            if not ok and g and "towns" in g:
                ok = any(geo_town(gt["n"], t) and any(not reg or areas[i].get("r") == reg for i in gt.get("c", [])) for gt in g["towns"])
            if not ok:
                miss.append((ward + " " if ward else "") + t)
        found = len(towns) - len(miss)
        main = f"町 {found:,}/{len(towns):,}"
        parts.append(f"地区が見つからない町 {len(miss)}")
        if miss:
            if len(miss) > len(towns) * 0.05:
                lv = WARN
            note(WARN if lv == WARN else INFO, f"住所：収集日の地区が見つからない町が {len(miss)}（正式な町 {len(towns)} のうち）",
                 "<p>郵便番号一覧にある町（市の正式な町名）のうち、アプリの収集日の地区の一覧にも、「今いる場所から探す」の町→地区の対応にも見つからない町です。"
                 "市の資料で別の名前や別の地区にまとめられているか、アプリに入っていない（市の資料から読み落とした）かもしれません。"
                 "この町に住んでいる人は、町名で探しても見つかりません。</p>"
                 + names_html(sorted(miss))
                 + steps("市の収集日の資料（カレンダー・地区の一覧）で、この町を探す",
                         "地区の名前が町名の市（京都市・周南市など）：資料にあれば、町名の書き方がちがうか、読み落としなので calendar.py を直す（Claude に頼む）",
                         f"地区が町より大きい市（下松市・光市など）：<code>gomiappV3.1/tools/munis/{h(m.path)}/geo.py</code> の町→地区の対応に、この町を足す",
                         "工場・港・山の中など、人の住んでいない所なら、そのままでよい"))
        # 収集日の町名が郵便番号の町名にあるか（地区の名前が町名の自治体だけ）
        pt = {}
        for ward, t in towns:
            pt.setdefault(ward, set()).add(_CHOME.sub("", tkey(t)))
        def in_post(a):
            k = _CHOME.sub("", tkey(a["n"]))
            return k in pt.get(a.get("r", ""), set()) or k in pt.get("", set())
        bases = {}
        for a in areas:
            if not a.get("d", "").startswith("右京区京北"):
                bases.setdefault((a.get("r", ""), re.sub(r"（[^）]*）$", "", re.sub(r"（\d）$", "", a["n"]))), a)
        hit = [k for k, a in bases.items() if in_post(a)]
        if bases and len(hit) >= len(bases) * 0.5:
            nm = sorted(f"{r} {n}".strip() for (r, n), a in bases.items() if not in_post(a))
            parts.append(f"正式な町名に無い {len(nm)}")
            if nm:
                note(INFO, f"住所：収集日の町名のうち、正式な町名（郵便番号一覧）に見つからないものが {len(nm)}",
                     "<p>山の中の字や、郵便番号のない地名が多いです。市の一覧表の書きまちがい・異体字のこともあります"
                     "（そのときは、正式な町名で検索しても見つかりません）。</p>" + names_html(nm)
                     + steps(f"書きまちがいなら <code>gomiappV3.1/tools/munis/{h(m.path)}/calendar.py</code> で直す（京都市は PAIRS に字の組を足す）",
                             f"<code>python gomiappV3.1/tools/update_year.py {cal['year']} {m.code}</code> で作り直す"))
        else:
            parts.append("地区名（町名と照合しない）")
    # PDF の読み取りで気になったところ（読み取りの注意.txt を書く自治体）
    rf = m.year_dir(cal["year"]) / "読み取りの注意.txt"
    if rf.exists():
        lines = [x for x in rf.read_text(encoding="utf-8").splitlines()[3:] if x.strip()]
        unread = [x for x in lines if "読めない行" in x]
        guess = [x for x in lines if "頭を" in x or "頭が決まらない" in x]
        dupn = [x for x in lines if "同じ名前" in x]
        fixed = [x for x in lines if "書き方に直した" in x]
        parts.append(f"読めない行 {len(unread)}・頭の推測 {len(guess)}・同名 {len(dupn)}・直した町名 {len(fixed)}")
        if unread:
            lv = BAD
            note(BAD, f"住所：市の PDF に読めない行が {len(unread)} あります（その町はアプリに入っていません）",
                 names_html(unread) + steps(f"<code>元データ/{h(m.src_dir.relative_to(M.SOURCES).as_posix())}/{cal['year']}年度/読み取りの注意.txt</code> と PDF を見くらべる",
                                            "calendar.py の読み取りを直す（Claude に頼む）"))
        if guess or dupn:
            lv = max(lv, WARN, key=[OK, WARN, BAD].index)
            note(WARN, f"住所：町名の頭を推測したもの {len(guess)}・同じ名前で収集日がちがう町 {len(dupn)}",
                 names_html(guess + dupn) + steps("市の PDF と見くらべて、合っているか確かめる",
                                                  "まちがっていたら calendar.py の PREFIX_FIX に手で書く"))
    row["addr"] = (lv, main, "・".join(parts))


def steps(*items):
    return "<ol>" + "".join(f"<li>{x}</li>" for x in items) + "</ol>"


def lic_how(m, lic):
    """商用利用で、許可（確認）が必要な情報と、問い合わせ先・例文"""
    rows = lic.get("データごと", [])
    need = [x for x in rows if x.get("商用利用") in ("要許可", "要確認")]
    ok = [x for x in rows if x not in need]

    def link(x):
        return f'<a href="{h(x["元のURL"])}" target="_blank" rel="noopener">{h(x.get("元", ""))}</a>' if x.get("元のURL") else h(x.get("元", ""))

    out = [f"<p><b>{h(m.name)}で、商用に使う前に許可（または確認）が必要な情報</b>（{h(lic.get('確認した日', ''))} に確認）</p>",
           '<div class="wrap2"><table class="lic"><thead><tr><th>情報</th><th>アプリで使っているもの</th><th>元にした資料</th><th>市のきまり</th><th>判定</th></tr></thead><tbody>']
    for x in need:
        cls = "bad" if x["商用利用"] == "要許可" else "warn"
        out.append(f'<tr><td><b>{h(x["データ"])}</b></td><td>{h(x.get("使っている情報", ""))}</td><td>{link(x)}</td>'
                   f'<td>{h(x.get("利用条件", ""))}</td><td class="c {cls}"><b>{h(x["商用利用"])}</b></td></tr>')
    out.append("</tbody></table></div>")
    if ok:
        out.append('<p class="muted">許可がいらないもの（出典を書けば使える）：'
                   + "、".join(f"{h(x['データ'])}（{h(x.get('元', '').split('（')[0])}）" for x in ok) + "</p>")
    site = lic.get("サイトの利用条件", {})
    if site.get("URL"):
        out.append(f'<p>市のサイトの利用条件：<a href="{h(site["URL"])}" target="_blank" rel="noopener">{h(site["URL"])}</a>'
                   f'<br><span class="muted">{h(site.get("内容", ""))}</span></p>')
    contacts = lic.get("許可の問い合わせ先", [])
    if contacts:
        out.append("<h4>問い合わせ先</h4><ul>" + "".join(
            f"<li>{h(c['課'])}　電話 {h(c.get('電話', ''))}"
            + (f'　<a href="mailto:{h(c["メール"])}">{h(c["メール"])}</a>' if c.get("メール") else "") + "</li>"
            for c in contacts) + "</ul>")
    # 例文のあて先は、ごみのデータを作っている課（なければ最初の課）
    main = next((c for c in contacts if "ごみのデータ" in c["課"]), contacts[0] if contacts else None)
    dept = main["課"].split("（")[0] if main else "ご担当課"
    letter = (f"{m.name} {dept} ご担当者さま\n\n"
              "個人で「ごみ出しカレンダー」という、ごみの収集日と分け方を調べるアプリ（ウェブ版と、Android・iPhone のアプリ）を作っています。\n"
              "今後、アプリストアで無料（広告つき）で公開することを考えています。\n\n"
              "アプリでは、貴市の資料をもとに、次の情報をアプリ用の形に直して表示しています。\n"
              + "".join(f"・{x['データ']}：{x.get('使っている情報', '')}（元：{x.get('元', '')}）\n" for x in need)
              + "\n冊子のイラストや画像は使っていません。文章は、アプリ用に短くまとめ直しています。\n"
              "アプリには「市の公式アプリではないこと」「出典」「問い合わせ先として貴市の担当課」を表示しています。\n\n"
              "この使い方でアプリを公開してよいか、また、出典の書き方などの条件があれば教えていただけますでしょうか。\n"
              "（お名前・連絡先）")
    out.append(f'<h4>問い合わせの例文</h4><textarea class="letter" readonly rows="14">{h(letter)}</textarea>'
               '<button class="copy" type="button" onclick="const t=this.previousElementSibling;t.select();'
               'if(navigator.clipboard)navigator.clipboard.writeText(t.value);this.textContent=&quot;写しました&quot;">文を写す</button>')
    out.append("<h4>許可をもらったら</h4>" + steps(
        f"<code>gomiappV3.1/tools/munis/{h(m.path)}/license.json</code> の「許可の記録」に、日付・相手・結果・条件を書く",
        "許可をもらった情報の「商用利用」を「可」（出典の指定があれば「出典表示で可」）に直し、いちばん上の「商用利用」も直す",
        "出典の書き方の指定があれば、アプリの下の出典（<code>city.js</code> の footer）を直す",
        "<code>python gomiappV3.1/tools/status.py</code> で、ここが緑になるか確かめる"))
    out.append('<p class="muted">許可が取れない情報は、オープンデータに切り替えるか、自分のことばで書き直すか、その自治体は後回しにします。'
               "法律の判断ではないので、迷ったら市に確かめます。</p>")
    return "".join(out)


OD_OLD_DAYS = 730   # オープンデータがこれより長く更新されていなければ「古くなっていないか」と出す（opendata.py の DATASETS の old_days で変えられる）


def _opendata_used(m, web, note, today):
    """この自治体が使っているオープンデータ（用途の名前）。古さも調べて note に出す"""
    import opendata as OD
    used = []
    sets = []
    mod = m.module("opendata")
    if mod:
        sets += [(ds["use"], ds["url"], m.src_dir / "オープンデータ" / ds["file"], ds) for ds in mod.DATASETS]
    cal_mod = m.module("calendar")
    if cal_mod and getattr(cal_mod, "DATASET", None):
        sets.append(("収集日", cal_mod.DATASET, None, {}))   # 収集日は毎年の更新（status の「次のカレンダー」）で見る
    for use, url, path, ds in sets:
        used.append(use.split("（")[0])
        local = OD.meta(path) if path else None
        modified = local["modified"] if local else ""
        if web:
            try:
                import web as W
                res = next((r for r in OD.info(url, W)["resources"] if ds.get("pick", lambda r: False)(r)), None)
                cat = res["modified"] if res else ""
                if path and cat and cat != modified:
                    note(WARN, f"オープンデータ「{use}」がカタログで新しくなっています（{cat}）",
                         steps(f"<code>python gomiappV3.1/tools/update_opendata.py {m.code}</code> で取ってきて作り直す",
                               "アプリで品目などを見て、おかしくないか確かめる", "GitHub Desktop で Commit → Push origin"))
                modified = modified or cat
            except Exception as e:
                note(WARN, f"オープンデータ「{use}」のカタログを調べられませんでした（{e}）")
        if path and not path.exists():
            note(WARN, f"オープンデータ「{use}」のファイルが元データにありません",
                 f"<p><code>python gomiappV3.1/tools/update_opendata.py {m.code}</code> で取ってきます。</p>")
        try:
            if modified and (today - dt.date.fromisoformat(modified)).days > ds.get("old_days", OD_OLD_DAYS):
                note(WARN, f"オープンデータ「{use}」は {modified} から更新されていません",
                     steps(f'<a href="{h(url)}" target="_blank" rel="noopener">カタログのページ</a>で、新しいものが出ていないか見る',
                           "市のサイトの分別の冊子やカレンダーが、これより新しく改定されていないか見る",
                           "古くなっていたら、市にオープンデータの更新をお願いするか、市の資料に戻す（Claude に相談）"))
        except ValueError:
            pass
    return used


CSS = """
:root{--bg:#f6f5f1;--surface:#fff;--line:#e1ded6;--text:#1f2421;--muted:#636a66;--accent:#2f8f5b;
  --ok:#2f8f5b;--ok-bg:#e6f4ec;--warn:#9a6a00;--warn-bg:#fdf3d8;--bad:#c0392b;--bad-bg:#fbe6e3}
@media (prefers-color-scheme: dark){:root{--bg:#141715;--surface:#1d211f;--line:#323834;--text:#e9ece9;--muted:#a1a9a4;
  --accent:#4fb87d;--ok:#4fb87d;--ok-bg:#1b3125;--warn:#e0b44a;--warn-bg:#3a3018;--bad:#f0705a;--bad-bg:#3d1f1b}}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--text);font:15px/1.6 system-ui,-apple-system,"Hiragino Sans","Yu Gothic UI",sans-serif}
main{max-width:1200px;margin:0 auto;padding:20px 16px 40px}
h1{font-size:22px;margin:0 0 4px} h2{font-size:17px;margin:28px 0 8px}
.sub{color:var(--muted);margin:0 0 16px;font-size:13px}
.sum{display:grid;grid-template-columns:repeat(auto-fill,minmax(110px,1fr));gap:8px;margin:0 0 8px}
.sum div{background:var(--surface);border:1px solid var(--line);border-radius:10px;padding:8px 12px}
.sum b{display:block;font-size:20px} .sum span{color:var(--muted);font-size:12px}
.wrap{overflow-x:auto;background:var(--surface);border:1px solid var(--line);border-radius:12px}
table{border-collapse:collapse;width:100%;min-width:900px}
th,td{padding:8px 10px;border-bottom:1px solid var(--line);text-align:left;vertical-align:top}
th{font-size:12px;color:var(--muted);font-weight:600;white-space:nowrap;background:var(--surface);position:sticky;top:0}
tr:last-child td{border-bottom:0}
td.pref{color:var(--muted);font-size:13px;white-space:nowrap}
td.name b{display:block} td.name small{color:var(--muted)}
.c{white-space:nowrap}
.c b{display:inline-block;padding:1px 8px;border-radius:999px;font-size:13px;font-weight:600}
.c small{display:block;color:var(--muted);font-size:12px;white-space:normal}
.ok b{background:var(--ok-bg);color:var(--ok)} .warn b{background:var(--warn-bg);color:var(--warn)} .bad b{background:var(--bad-bg);color:var(--bad)}
ul.notes{margin:0;padding:0;list-style:none;background:var(--surface);border:1px solid var(--line);border-radius:12px}
ul.notes li{padding:8px 12px;border-bottom:1px solid var(--line)} ul.notes li:last-child{border-bottom:0}
.tag{display:inline-block;font-size:12px;font-weight:700;padding:0 6px;border-radius:4px;margin-right:6px}
.tag.warn{background:var(--warn-bg);color:var(--warn)} .tag.bad{background:var(--bad-bg);color:var(--bad)} .tag.info{background:var(--bg);color:var(--muted);border:1px solid var(--line)}
.howto{color:var(--muted);font-size:13px} code{font-size:12px;background:var(--bg);padding:1px 5px;border-radius:4px}
ul.notes details summary{cursor:pointer;list-style:none}
ul.notes details summary::-webkit-details-marker{display:none}
ul.notes details summary::after{content:"▸ くわしく";float:right;color:var(--accent);font-size:12.5px;font-weight:700;margin-left:8px}
ul.notes details[open] summary::after{content:"▾ とじる"}
.how{margin:8px 0 4px;padding:10px 12px;background:var(--bg);border-radius:10px;font-size:14px}
.how p{margin:4px 0 8px} .how ol,.how ul{margin:4px 0 8px;padding-left:1.4em} .how li{margin:3px 0}
.how h4{margin:12px 0 4px;font-size:13.5px}
.muted{color:var(--muted);font-size:13px}
.how a{color:var(--accent);word-break:break-all} .how code,.howto code,.sub code{word-break:break-all}
.wrap2{overflow-x:auto}
table.lic{min-width:640px;background:var(--surface);border:1px solid var(--line);border-radius:8px;font-size:13px}
table.lic th{position:static}
.letter{width:100%;font:13px/1.6 system-ui,-apple-system,"Hiragino Sans","Yu Gothic UI",sans-serif;padding:8px 10px;border:1px solid var(--line);border-radius:8px;background:var(--surface);color:var(--text);resize:vertical}
.copy{margin-top:6px;border:1px solid var(--accent);background:var(--surface);color:var(--accent);font-weight:700;border-radius:999px;padding:4px 14px;cursor:pointer}
a.cell{color:inherit;text-decoration:none;display:block} a.cell b::after{content:" ›"}
:target{scroll-margin-top:12px}
"""

JS = """
function openHash(){ const el = location.hash && document.getElementById(location.hash.slice(1)); if (el){ const d = el.querySelector("details"); if (d) d.open = true; el.scrollIntoView({block:"start"}); } }
window.addEventListener("hashchange", openHash); openHash();
"""

COLS = [("cal", "収集日"), ("items", "品目"), ("city", "設定"), ("geo", "今いる場所"), ("addr", "住所"), ("src", "元データ"), ("tools", "道具"), ("lic", "商用利用"), ("next", "次のカレンダー（市のサイト）")]


def main():
    web = "--web" in sys.argv
    today = dt.date.today()
    for a in sys.argv[1:]:
        if a.startswith("--date="):
            today = dt.date.fromisoformat(a[7:])
    now_fy = fiscal_year(today)
    hol = json.loads((M.DATA / "holidays.js").read_text(encoding="utf-8").split("window.GOMI_HOLIDAYS = ", 1)[1].rstrip().rstrip(";"))
    geo_cities = {}
    for f in M.GEO.glob("*.json"):
        if f.name != "index.json":
            geo_cities.update(json.loads(f.read_text(encoding="utf-8")).get("cities", {}))
    # 郵便番号一覧（tools/build_zip.py で作る）。県ごと
    zips = {}
    zdir = M.SOURCES / "全国" / "郵便番号" / "県別"
    for f in zdir.glob("*.json"):
        if f.name != "index.json":
            zips[f.name[:2]] = json.loads(f.read_text(encoding="utf-8"))
    rows, all_notes = [], []
    for m in M.munis():
        print("調べています:", m)
        row, notes = check_muni(m, now_fy, hol["year"], geo_cities, web, today, zips)
        rows.append((m, row, notes))
        all_notes += [(lv, m, t, how, key) for lv, t, how, key in notes]
    cols = [c for c in COLS if web or c[0] != "next"]
    e = html.escape
    n_bad = sum(1 for lv, *_ in all_notes if lv == BAD)
    n_warn = sum(1 for lv, *_ in all_notes if lv == WARN)
    prefs = {m.pref for m, *_ in rows}
    body = [f"""<main>
<h1>ごみ出しカレンダー 状況一覧</h1>
<p class="sub">{today:%Y年%m月%d日} に作成（今は{reiwa(now_fy)}）。作り直すには <code>python gomiappV3.1/tools/status.py</code>{'' if web else '（市のサイトに次の年度が出ているかも調べるときは <code>--web</code> を付ける）'}</p>
<div class="sum">
  <div><b>{len(prefs)}</b><span>都道府県</span></div>
  <div><b>{len(rows)}</b><span>自治体</span></div>
  <div><b>{sum(1 for m, r, _ in rows if r['cal'][0] == OK)}</b><span>収集日が今の年度</span></div>
  <div><b>{n_bad}</b><span>直すこと</span></div>
  <div><b>{n_warn}</b><span>気をつけること</span></div>
  <div><b>{reiwa(hol['year'])}</b><span>祝日のデータ</span></div>
</div>
<h2>自治体ごと</h2>
<div class="wrap"><table>
<thead><tr><th>都道府県</th><th>自治体</th>{''.join(f'<th>{h(t)}</th>' for _, t in cols)}</tr></thead><tbody>"""]
    for m, row, notes in rows:
        keys = {n[3] for n in notes}   # くわしくへ飛べる列（商用利用・住所）
        cells = "".join(
            (f'<td class="c {row[k][0]}"><a class="cell" href="#{k}-{m.code}"><b>{h(row[k][1])}</b><small>{h(row[k][2])}</small></a></td>'
             if f"{k}-{m.code}" in keys else
             f'<td class="c {row[k][0]}"><b>{h(row[k][1])}</b><small>{h(row[k][2])}</small></td>') if k in row else "<td></td>"
            for k, _ in cols)
        body.append(f'<tr><td class="pref">{h(m.pref)} {h(m.pref_name)}</td><td class="name"><b>{h(m.name)}</b><small>{h(m.code)}</small></td>{cells}</tr>')
    body.append("</tbody></table></div>")
    body.append("<h2>直すこと・気をつけること</h2>")
    if all_notes:
        order = {BAD: 0, WARN: 1, INFO: 2}
        body.append('<p class="howto">それぞれをクリックすると、どうすればよいかが出ます。</p><ul class="notes">' + "".join(
            (f'<li id="{key}">' if key else "<li>")
            + f'<details><summary><span class="tag {lv}">{"直す" if lv == BAD else "注意" if lv == WARN else "参考"}</span><b>{h(m.name)}</b>　{h(t)}</summary>'
            + f'<div class="how">{how}</div></details></li>'
            for lv, m, t, how, key in sorted(all_notes, key=lambda x: (order[x[0]], x[1].code))) + "</ul>")
    else:
        body.append('<p class="howto">ありません。</p>')
    body.append(f"""<h2>見かた</h2>
<p class="howto">緑＝問題なし、黄＝気をつけること、赤＝直すこと。
収集日は毎年4月に <code>download_sources.py</code> → <code>update_year.py</code> で更新します（くわしくは <code>gomiappV3.1/tools/README.md</code>）。
自治体ごとの注意は <code>gomiappV3.1/tools/munis/&lt;県&gt;/&lt;自治体&gt;/README.md</code> にあります。<br>
商用利用は <code>license.json</code> から出しています（可・出典表示で可＝緑、要確認・許可を問い合わせ中＝黄、要許可＝赤）。「オープンデータ：」は、そのデータをオープンデータから作っているもの（<code>opendata.py</code>・<code>calendar.py</code> から）。市のサイトの利用条件のまとめで、法律の判断ではありません。<br>
住所は、郵便番号一覧の町名（市の正式な町名。<code>元データ/全国/郵便番号/県別/</code>、<code>tools/build_zip.py</code> で作る）とくらべたもの。
「町 a/b」は、その市の正式な町 b のうち、アプリで収集日の地区が見つかる町が a（町名が同じか、「今いる場所から探す」の町→地区の対応にある）。
「参考」は数えていない知っておくこと（山の中の字など、直さなくてよいことが多い）。</p>
</main>""")
    page = f'<!doctype html><html lang="ja"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>状況一覧</title><style>{CSS}</style></head><body>{"".join(body)}<script>{JS}</script></body></html>'
    out = M.SOURCES / "状況一覧.html"
    out.write_text(page, encoding="utf-8")
    print(f"\n自治体 {len(rows)}・直すこと {n_bad}・気をつけること {n_warn}")
    for lv, m, t, *_ in all_notes:
        print(f"  [{'直す' if lv == BAD else '注意' if lv == WARN else '参考'}] {m.name}：{t}")
    print("wrote", out)


if __name__ == "__main__":
    main()
