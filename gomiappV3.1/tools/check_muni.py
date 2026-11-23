"""自治体のデータが、決まった形・ルールどおりにできているかを自動で調べる（エージェントが作ったデータの検査）。

使い方（gomi フォルダで実行）:
  python gomiappV3.1/tools/check_muni.py              ← アプリに入っているすべての自治体
  python gomiappV3.1/tools/check_muni.py 35215 光市   ← 自治体を指定（コードか名前）
  python gomiappV3.1/tools/check_muni.py 35215 --md   ← 結果を Markdown で出す（作業報告に貼る用）

結果の印:
  [直す]  決まった形になっていない。アプリで正しく出ない。直さないと「できた」にしてはいけない
  [注意]  たぶん直したほうがよい。直さないときは、理由を README.md の「人がやること」か「確かめたこと」に書く
  [参考]  知っておくこと
直すことが1つでもあると、終わりの番号（終了コード）が 1 になる。

調べること（くわしくは gomiappV3.1/tools/AGENT.md の「できあがりの条件」）:
  登録       municipalities.js のコード・名前・よみが、総務省の全国地方公共団体コード（元データ/全国/地方公共団体コード/lgcode.json）と同じか
  ファイル   data/ の city.js・calendar.js・items.js、tools/munis/ の calendar.py・README.md・license.json がそろっているか
  設定       city.js の必要な項目、区分の色・名前
  収集日     年度の中の日付か、区分が city.js にあるか、月ごとに収集日があるか、1月1日に収集がないか、地区と日程のつながり
  品目       件数、区分、読み（ひらがな）
  商用利用   license.json の必要な項目
  道具       calendar.py の NEED・download・make_calendar、元データの年度のフォルダ
  今いる場所 geo/<県>.json にあるか、地区が決まる町の割合
  README     「人がやること」「確かめたこと」の見出し
"""
import datetime as dt
import json
import re
import sys
from collections import Counter

sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)
from pathlib import Path  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent / "lib"))
import munis as M  # noqa: E402

BAD, WARN, INFO = "直す", "注意", "参考"
LGCODE = M.SOURCES / "全国" / "地方公共団体コード" / "lgcode.json"
CITY_KEYS = ["cats", "order", "calOrder", "short", "long", "bag", "cut", "contact", "footer", "hint", "rules", "regions"]
LIC_KEYS = ["自治体", "確認した日", "商用利用", "データごと", "許可の問い合わせ先", "出典表示"]
LIC_DATA_KEYS = ["データ", "使っている情報", "元", "元のURL", "利用条件", "商用利用", "オープンデータ"]
JUDGE = ["可", "出典表示で可", "要確認", "要許可"]


def load_lgcode():
    if not LGCODE.exists():
        return None
    d = json.loads(LGCODE.read_text(encoding="utf-8"))
    return {m["code"]: m for m in d["munis"]}


def item_tuple(x):
    """items.js の1行（[品名, 区分, 読み, 注意] か {n, c, y, d}）→ (品名, 区分, 読み)"""
    if isinstance(x, list):
        return x[0], x[1], x[2] if len(x) > 2 else ""
    return x.get("n", ""), x.get("c", ""), x.get("y", "")


def check(m, lg, geo_cities):
    out = []

    def say(level, text):
        out.append((level, text))

    # ---- 登録（コード表と同じか）----
    if lg is None:
        say(WARN, f"コード表がありません（{LGCODE.relative_to(M.ROOT)}）。python gomiappV3.1/tools/build_lgcode.py で作る")
    else:
        g = lg.get(m.code)
        if not g:
            say(BAD, f"コード {m.code} が全国地方公共団体コードにありません")
        else:
            if g["kind"] == "ward":
                say(BAD, f"{m.code} は政令指定都市の区です。市（{g.get('city')}）を1つの自治体にして、区は city.js の regions（地域）にする")
            if g["name"] != m.name:
                say(BAD, f"名前がコード表とちがいます（アプリ：{m.name}／コード表：{g['name']}）")
            if g["pref"] != m.pref:
                say(BAD, f"県コードがコード表とちがいます（アプリ：{m.pref}／コード表：{g['pref']}）")
            if m.yomi and g.get("yomi") and m.yomi != g["yomi"]:
                say(WARN, f"よみがコード表とちがいます（アプリ：{m.yomi}／コード表：{g['yomi']}）")
    if not re.fullmatch(r"[a-z][a-z0-9-]*", m.slug):
        say(BAD, f"slug（ローマ字の名前）は小文字の英数字とハイフンだけにする：{m.slug}")
    if not m.yomi:
        say(WARN, "municipalities.js に yomi（ひらがな）がありません")

    # ---- ファイル ----
    for f in ("city.js", "calendar.js", "items.js"):
        if not (m.data_dir / f).exists():
            say(BAD, f"gomiappV3.1/data/{m.path}/{f} がありません")
    for f, lv in (("calendar.py", BAD), ("README.md", BAD), ("license.json", BAD), ("geo.py", WARN)):
        if not (m.tool_dir / f).exists():
            say(lv, f"gomiappV3.1/tools/munis/{m.path}/{f} がありません")

    # ---- 設定（city.js）----
    city, cats = None, {}
    try:
        city = m.read("city")
        cats = city.get("cats", {})
        miss = [k for k in CITY_KEYS if k not in city]
        if miss:
            say(BAD, f"city.js に必要な項目がありません：{'・'.join(miss)}")
        for k, c in cats.items():
            if not c.get("name"):
                say(BAD, f"city.js：区分「{k}」に name がありません")
            if not c.get("color"):
                say(BAD, f"city.js：区分「{k}」に color がありません")
        for key in ("order", "calOrder"):
            bad = [c for c in city.get(key, []) if c not in cats]
            if bad:
                say(BAD, f"city.js：{key} に cats にない区分があります：{'・'.join(bad)}")
        for key in ("short", "long", "bag"):
            bad = [c for c in city.get(key, {}) if c not in cats]
            if bad:
                say(WARN, f"city.js：{key} に cats にない区分があります：{'・'.join(bad)}")
        cut = city.get("cut")
        if not (isinstance(cut, list) and len(cut) == 2 and 0 <= cut[0] <= 23 and 0 <= cut[1] <= 59):
            say(BAD, f"city.js：cut（出す時刻）は [時, 分] にする：{cut}")
    except Exception as e:
        say(BAD, f"city.js が読めません：{e}")

    # ---- 収集日（calendar.js）----
    cal = None
    try:
        cal = m.read("calendar")
        y = cal["year"]
        start, end = dt.date(y, 4, 1), dt.date(y + 1, 3, 31)
        used = set()
        for sid, s in cal["schedules"].items():
            if not s.get("days"):
                say(BAD, f"収集日：日程「{sid}」に収集日が1日もありません")
                continue
            months = set()
            for k, cs in s["days"].items():
                try:
                    d = dt.date.fromisoformat(k)
                except ValueError:
                    say(BAD, f"収集日：日程「{sid}」に日付でないものがあります：{k}")
                    continue
                if not start <= d <= end:
                    say(BAD, f"収集日：日程「{sid}」の {k} が {y}年度（{start}〜{end}）の外です")
                months.add(d.month)
                bad = [c for c in cs if c not in cats]
                if bad:
                    say(BAD, f"収集日：日程「{sid}」の {k} に city.js にない区分があります：{'・'.join(bad)}")
                    break
            if len(months) < 12:
                say(WARN, f"収集日：日程「{sid}」に収集日のない月があります（{sorted(set(range(1, 13)) - months)}月）")
            if f"{y + 1}-01-01" in s["days"]:
                say(WARN, f"収集日：日程「{sid}」の1月1日に収集があります（年末年始の休みが入っているか確かめる）")
            bad = [c for c in s.get("rules", {}) if c not in cats]
            if bad:
                say(WARN, f"収集日：日程「{sid}」の rules に city.js にない区分があります：{'・'.join(bad)}")
        regions = city.get("regions", []) if city else []
        names = Counter()
        no_yomi = 0
        for a in cal["areas"]:
            if a.get("s") not in cal["schedules"]:
                say(BAD, f"収集日：地区「{a.get('n')}」の日程「{a.get('s')}」がありません")
            used.add(a.get("s"))
            if not a.get("n"):
                say(BAD, "収集日：名前のない地区があります")
            if regions and a.get("r") not in regions:
                say(BAD, f"収集日：地区「{a.get('n')}」の地域「{a.get('r')}」が city.js の regions にありません")
            names[(a.get("r", ""), a.get("n"))] += 1
            if not a.get("y"):
                no_yomi += 1
        dup = [f"{r} {n}".strip() for (r, n), c in names.items() if c > 1]
        if dup:
            say(BAD, f"収集日：同じ地域に同じ名前の地区が2つ以上あります（えらべない）：{'、'.join(dup[:10])}")
        unused = [s for s in cal["schedules"] if s not in used and not (city or {}).get("schedPick")]
        if unused:
            say(WARN, f"収集日：どの地区も使っていない日程があります：{'・'.join(unused)}")
        if no_yomi > len(cal["areas"]) * 0.2:
            say(WARN, f"収集日：読み（ひらがな）のない地区が {no_yomi} あります（ひらがなで探せない）")
        ye = cal.get("yearEnd") or {}
        if ye.get("tentative"):
            say(WARN, f"収集日：年末年始の休みが仮のままです（{'〜'.join(ye.get('off', []))}）")
    except Exception as e:
        say(BAD, f"calendar.js が読めません：{e}")

    # ---- 品目（items.js）----
    try:
        items = [item_tuple(x) for x in m.read("items")]
        if len(items) < 100:
            say(WARN, f"品目が {len(items)} 件と少なめです（市の分別の資料に載っている品目を入れる）")
        if any(not n for n, _, _ in items):
            say(BAD, "品目：名前のない品目があります")
        bad = sorted({c for _, c, _ in items if c not in cats})
        if bad:
            say(BAD, f"品目：city.js にない区分があります：{'・'.join(bad)}")
        no_y = sum(1 for _, _, yy in items if not yy)
        if no_y:
            say(WARN, f"品目：読み（ひらがな）のない品目が {no_y} 件あります")
        dup = [n for n, c in Counter(n for n, _, _ in items).items() if c > 1]
        if dup:
            say(INFO, f"品目：同じ名前の品目が {len(dup)} あります（例：{'、'.join(dup[:5])}）")
    except Exception as e:
        say(BAD, f"items.js が読めません：{e}")

    # ---- 商用利用（license.json）----
    lf = m.tool_dir / "license.json"
    if lf.exists():
        try:
            lic = json.loads(lf.read_text(encoding="utf-8"))
            miss = [k for k in LIC_KEYS if k not in lic]
            if miss:
                say(BAD, f"license.json に必要な項目がありません：{'・'.join(miss)}")
            if lic.get("商用利用") not in JUDGE:
                say(BAD, f"license.json の「商用利用」は {'・'.join(JUDGE)} のどれかにする：{lic.get('商用利用')}")
            try:
                dt.date.fromisoformat(lic.get("確認した日", ""))
            except ValueError:
                say(BAD, "license.json の「確認した日」を 2026-11-24 のような日付にする")
            for d in lic.get("データごと", []):
                miss = [k for k in LIC_DATA_KEYS if k not in d]
                if miss:
                    say(BAD, f"license.json：「{d.get('データ', '?')}」に必要な項目がありません：{'・'.join(miss)}")
                if d.get("商用利用") not in JUDGE:
                    say(BAD, f"license.json：「{d.get('データ', '?')}」の商用利用が {'・'.join(JUDGE)} のどれでもありません")
            if not lic.get("許可の問い合わせ先"):
                say(WARN, "license.json：許可の問い合わせ先がありません")
        except Exception as e:
            say(BAD, f"license.json が読めません：{e}")

    # ---- 道具と元データ ----
    mod = None
    try:
        mod = m.module("calendar")
    except Exception as e:
        say(BAD, f"calendar.py が読み込めません：{e}")
    if mod:
        if not hasattr(mod, "make_calendar"):
            say(BAD, "calendar.py に make_calendar がありません")
        if not hasattr(mod, "NEED"):
            say(BAD, "calendar.py に NEED（元データのファイル名）がありません")
        if not hasattr(mod, "download"):
            say(WARN, "calendar.py に download がありません（毎年、手でダウンロードすることになる）")
        if cal and hasattr(mod, "NEED"):
            lack = [f for f in mod.NEED if not (m.year_dir(cal["year"]) / f).exists()]
            if lack:
                say(WARN, f"元データ/{m.src_dir.relative_to(M.SOURCES).as_posix()}/{cal['year']}年度/ にないファイル：{'・'.join(lack)}")

    # ---- 今いる場所（geo）----
    g = geo_cities.get(m.code)
    if not g:
        say(WARN, "今いる場所から探すの地図（geo/）にありません（geo.py を作って build_geo.py）")
    elif "towns" in g and "line" not in g:
        none = sum(1 for t in g["towns"] if not t.get("c"))
        if g["towns"] and none > len(g["towns"]) * 0.15:
            say(WARN, f"今いる場所：地区が決まらない町が {none}／{len(g['towns'])} あります")

    # ---- README ----
    rf = m.tool_dir / "README.md"
    if rf.exists():
        t = rf.read_text(encoding="utf-8")
        for head in ("人がやること", "確かめたこと"):
            if not re.search(rf"^#+\s*{head}", t, re.M):
                say(INFO, f"README.md に「## {head}」の見出しがありません（AGENT.md の作業報告の形）")
    return out


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    md = "--md" in sys.argv
    lg = load_lgcode()
    geo_cities = {}
    for f in M.GEO.glob("*.json"):
        if f.name != "index.json":
            geo_cities.update(json.loads(f.read_text(encoding="utf-8")).get("cities", {}))
    targets = M.munis(args or None)
    if not targets:
        raise SystemExit(f"自治体が見つかりません：{' '.join(args)}（municipalities.js に登録してから）")
    n_bad = 0
    for m in targets:
        res = check(m, lg, geo_cities)
        bad = sum(1 for lv, _ in res if lv == BAD)
        warn = sum(1 for lv, _ in res if lv == WARN)
        n_bad += bad
        head = f"{m}：直す {bad}・注意 {warn}" + ("（合格）" if not bad else "")
        if md:
            print(f"### 自動チェック {head}\n")
            print("\n".join(f"- [{lv}] {t}" for lv, t in res) or "- 問題なし")
            print()
        else:
            print(head)
            for lv, t in res:
                print(f"  [{lv}] {t}")
    sys.exit(1 if n_bad else 0)


if __name__ == "__main__":
    main()
