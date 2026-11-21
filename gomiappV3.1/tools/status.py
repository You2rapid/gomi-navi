"""自治体ごとのデータの状況を1枚の表（状況一覧）にする。

使い方（gomi フォルダで実行）:
  python gomiappV3.1/tools/status.py          ← 元データ/状況一覧.html を作る（ブラウザで開いて見る）
  python gomiappV3.1/tools/status.py --web    ← あわせて、市のサイトに次の年度のカレンダーが出ているかも調べる（少し時間がかかる）
  python gomiappV3.1/tools/status.py --date=2027-04-10   ← その日に見たらどうなるかを試す

表に出すもの:
  収集日（何年度か・地区の数・祝日のデータと年度が合っているか）、品目（件数・区分の書きまちがい）、
  設定（区分・色）、今いる場所から探す（町の数・地区が決まらない町の数）、
  元データ（今の年度と次の年度のファイルがそろっているか・分別の冊子・地図）、道具（calendar.py・geo.py・README）、
  商用利用（license.json：使っている資料の利用条件・許可が必要か・確かめた日）と、オープンデータを使っているか・古くなっていないか
"""
import datetime as dt
import html
import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)
sys.path.insert(0, str(Path(__file__).resolve().parent / "lib"))
import munis as M  # noqa: E402

OK, WARN, BAD = "ok", "warn", "bad"


def fiscal_year(d):
    return d.year if d.month >= 4 else d.year - 1


def reiwa(y):
    return f"令和{y - 2018}年度"


def check_muni(m, now_fy, holidays_year, geo_cities, web=None, today=None):
    """1つの自治体を調べて、(列ごとの [状態, 表示, くわしく]) と、気をつけることの一覧を返す"""
    notes, row = [], {}
    today = today or dt.date.today()

    def note(level, text):
        notes.append((level, text))

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
            note(BAD, f"収集日が {reiwa(y)} のままです（今は {reiwa(now_fy)}）。"
                      f"download_sources.py {now_fy} → update_year.py {now_fy} で更新してください")
        if y != holidays_year:
            lv = max(lv, WARN, key=[OK, WARN, BAD].index)
            note(WARN, f"収集日（{reiwa(y)}）と祝日のデータ（{reiwa(holidays_year)}）の年度がちがいます")
        if unknown:
            lv = BAD
            note(BAD, f"calendar.js に city.js にない区分があります（{'・'.join(unknown)}）")
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
            note(WARN, f"品目が {len(items)} 件と少なめです（冊子の例だけなど）")
        if no_read:
            note(WARN, f"読み（ひらがな）のない品目が {no_read} 件あります（ひらがなで探せません）")
        dup = len(names) - len(set(names))
        row["items"] = (lv, f"{len(items):,} 件", f"同じ名前 {dup} 件" if dup else "")
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
                note(WARN, f"地区が決まらない町が {none} あります（geo.py の対応表を見直す）")

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
    kml = (m.src_dir / "地図" / f"r2ka{m.code}.kml").exists()
    lv = OK if cur_ok and books and kml else WARN
    if not cur_ok:
        note(WARN, f"今の収集日の元にした 元データ/{m.src_dir.relative_to(M.SOURCES).as_posix()}/{cal_y}年度/ のファイルがそろっていません")
    if not books:
        note(WARN, "分別の冊子（品目の元にした資料）が元データにありません")
    if not kml:
        note(WARN, "地図（e-Stat の KML）が元データにありません")
    row["src"] = (lv, "・".join(f"{y}" for y in years) + "年度" if years else "なし",
                  f"冊子 {len(books)}・地図 {'あり' if kml else 'なし'}" + (f"・{next_y}年度そろっている" if next_ok else ""))

    # ---- 道具 ----
    tools = [n for n in ("calendar.py", "geo.py", "README.md") if (m.tool_dir / n).exists()]
    can_dl = bool(mod and hasattr(mod, "download"))
    row["tools"] = (OK if len(tools) == 3 and can_dl else WARN, f"{len(tools)}/3", "自動ダウンロード" + ("あり" if can_dl else "なし"))
    if not can_dl:
        note(WARN, "calendar.py に download がありません（毎年、手でダウンロード）")

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
                note(WARN, f"商用利用：{'・'.join(need)}は{judge}。license.json の「やること」と「許可の問い合わせ先」を見る")
            try:
                if checked and (today - dt.date.fromisoformat(checked)).days > 365:
                    note(WARN, f"商用利用：利用条件を確かめてから1年以上たっています（{checked}）。市のサイトで確かめ直す")
            except ValueError:
                note(WARN, f"license.json の「確認した日」が日付になっていません（{checked}）")
        except Exception as e:
            row["lic"] = (BAD, "読めません", str(e))
            note(BAD, f"license.json が読めません：{e}")
    else:
        row["lic"] = (WARN, "未調査", od_text + "／license.json なし")
        note(WARN, "商用利用：license.json がありません（使っている資料の利用条件を調べて書く）")

    # ---- 次の年度（アプリに入っている年度の次）のカレンダーが市のサイトに出ているか ----
    if web and can_dl:
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
            note(WARN, f"{reiwa(next_y)}のカレンダーが市のサイトに出ています。download_sources.py {next_y} → update_year.py {next_y}")
        if not found and late:
            note(BAD, f"{reiwa(next_y)}が始まっているのに、市のサイトで新しいカレンダーが見つかりません（市のページが変わったかもしれません。README.md のダウンロード元を開いて確かめる）")
    elif web:
        row["next"] = (WARN, "調べられません", "自動ダウンロードなし")
    return row, notes


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
                    note(WARN, f"オープンデータ「{use}」がカタログで新しくなっています（{cat}）。python gomiappV3.1/tools/update_opendata.py {m.code}")
                modified = modified or cat
            except Exception as e:
                note(WARN, f"オープンデータ「{use}」のカタログを調べられませんでした（{e}）")
        if path and not path.exists():
            note(WARN, f"オープンデータ「{use}」のファイルが元データにありません。python gomiappV3.1/tools/update_opendata.py {m.code}")
        try:
            if modified and (today - dt.date.fromisoformat(modified)).days > ds.get("old_days", OD_OLD_DAYS):
                note(WARN, f"オープンデータ「{use}」は {modified} から更新されていません。市の新しい資料と見くらべて、古くなっていないか確かめる")
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
.tag.warn{background:var(--warn-bg);color:var(--warn)} .tag.bad{background:var(--bad-bg);color:var(--bad)}
.howto{color:var(--muted);font-size:13px} code{font-size:12px;background:var(--bg);padding:1px 5px;border-radius:4px}
"""

COLS = [("cal", "収集日"), ("items", "品目"), ("city", "設定"), ("geo", "今いる場所"), ("src", "元データ"), ("tools", "道具"), ("lic", "商用利用"), ("next", "次のカレンダー（市のサイト）")]


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
    rows, all_notes = [], []
    for m in M.munis():
        print("調べています:", m)
        row, notes = check_muni(m, now_fy, hol["year"], geo_cities, web, today)
        rows.append((m, row, notes))
        all_notes += [(lv, m, t) for lv, t in notes]
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
<thead><tr><th>都道府県</th><th>自治体</th>{''.join(f'<th>{e(t)}</th>' for _, t in cols)}</tr></thead><tbody>"""]
    for m, row, _ in rows:
        cells = "".join(f'<td class="c {row[k][0]}"><b>{e(row[k][1])}</b><small>{e(row[k][2])}</small></td>' if k in row else "<td></td>" for k, _ in cols)
        body.append(f'<tr><td class="pref">{e(m.pref)} {e(m.pref_name)}</td><td class="name"><b>{e(m.name)}</b><small>{e(m.code)}</small></td>{cells}</tr>')
    body.append("</tbody></table></div>")
    body.append("<h2>直すこと・気をつけること</h2>")
    if all_notes:
        order = {BAD: 0, WARN: 1}
        body.append('<ul class="notes">' + "".join(
            f'<li><span class="tag {lv}">{"直す" if lv == BAD else "注意"}</span><b>{e(m.name)}</b>　{e(t)}</li>'
            for lv, m, t in sorted(all_notes, key=lambda x: (order[x[0]], x[1].code))) + "</ul>")
    else:
        body.append('<p class="howto">ありません。</p>')
    body.append(f"""<h2>見かた</h2>
<p class="howto">緑＝問題なし、黄＝気をつけること、赤＝直すこと。
収集日は毎年4月に <code>download_sources.py</code> → <code>update_year.py</code> で更新します（くわしくは <code>gomiappV3.1/tools/README.md</code>）。
自治体ごとの注意は <code>gomiappV3.1/tools/munis/&lt;県&gt;/&lt;自治体&gt;/README.md</code> にあります。<br>
商用利用は <code>license.json</code> から出しています（可・出典表示で可＝緑、要確認・許可を問い合わせ中＝黄、要許可＝赤）。「オープンデータ：」は、そのデータをオープンデータから作っているもの（<code>opendata.py</code>・<code>calendar.py</code> から）。市のサイトの利用条件のまとめで、法律の判断ではありません。</p>
</main>""")
    page = f'<!doctype html><html lang="ja"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>状況一覧</title><style>{CSS}</style></head><body>{"".join(body)}</body></html>'
    out = M.SOURCES / "状況一覧.html"
    out.write_text(page, encoding="utf-8")
    print(f"\n自治体 {len(rows)}・直すこと {n_bad}・気をつけること {n_warn}")
    for lv, m, t in all_notes:
        print(f"  [{'直す' if lv == BAD else '注意'}] {m.name}：{t}")
    print("wrote", out)


if __name__ == "__main__":
    main()
