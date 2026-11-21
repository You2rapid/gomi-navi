"""毎年4月の「年度の切り替え」をまとめて行う。

使い方（gomi フォルダで実行）:
  python gomiappV3.1/tools/download_sources.py 2027          ← 市のサイトから新しいカレンダーを 元データ/ に保存
  python gomiappV3.1/tools/update_year.py 2027               ← 元データから gomiappV3.1/data/ と gomiappV3.1/geo/ を作り直す（すべての自治体）
  python gomiappV3.1/tools/update_year.py 2027 35215 光市    ← 自治体を指定（自治体コードか名前）
  --check   ファイルがそろっているかだけ調べる（何も書きかえない）

やること:
  1. 元データ/<県>/<自治体>/<年度>年度/ に必要なファイルがそろっているか確かめる
  2. 祝日（内閣府のCSV：元データ/全国/<年度>年度/syukujitsu.csv）から data/holidays.js を作る
  3. 自治体ごとに tools/munis/<県>/<自治体>/calendar.py でカレンダーを読み取り、data/<県>/<自治体>/calendar.js を作る
     （読み取れなかった自治体は前のまま残し、最後にまとめて知らせる）
  4. 「今いる場所から探す」の地図（geo/）を作り直す
"""
import csv
import datetime as dt
import io
import subprocess
import sys
import traceback
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)
TOOLS = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS / "lib"))
import munis as M  # noqa: E402


def holidays(year, csv_path):
    text = csv_path.read_bytes().decode("cp932")
    start, end = dt.date(year, 4, 1), dt.date(year + 1, 3, 31)
    days = []
    for row in csv.reader(io.StringIO(text)):
        try:
            d = dt.datetime.strptime(row[0], "%Y/%m/%d").date()
        except (ValueError, IndexError):
            continue
        if start <= d <= end:
            days.append(d.isoformat())
    if not any(d.startswith(f"{year + 1}-0") for d in days):
        raise SystemExit(f"祝日のCSVに {year + 1}年1〜3月の祝日がありません。新しいCSVをダウンロードしてください。")
    # 年末年始（12/29〜1/3）は祝日でなくても収集が休み（ちがう自治体が出てきたら、自治体ごとの設定にする）
    year_end = [dt.date(year, 12, d).isoformat() for d in (29, 30, 31)] + [dt.date(year + 1, 1, d).isoformat() for d in (1, 2, 3)]
    return sorted(days), year_end


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if not args:
        raise SystemExit(__doc__)
    year, codes = int(args[0]), args[1:]
    targets = []
    for m in M.munis(codes or None):
        mod = m.module("calendar")
        if mod:
            targets.append((m, mod))
        else:
            print(f"（{m} は calendar.py がないので飛ばします）")
    print(f"== {M.nendo(year)} のデータを作ります")

    # 1. ファイルがそろっているか
    missing = [] if M.holiday_csv(year).exists() else [str(M.holiday_csv(year).relative_to(M.ROOT))]
    for m, mod in targets:
        missing += [str((m.year_dir(year) / f).relative_to(M.ROOT)) for f in mod.NEED if not (m.year_dir(year) / f).exists()]
    if missing:
        print("足りないファイルがあります。tools/download_sources.py で保存するか、手でダウンロードしてください:")
        for f in missing:
            print("  ", f)
        raise SystemExit(1)
    print("ファイルはそろっています。")
    if "--check" in sys.argv:
        return

    # 2. 祝日
    hol, ye = holidays(year, M.holiday_csv(year))
    M.write_holidays(year, hol, ye)
    print(f"祝日 {len(hol)}日 → data/holidays.js")

    # 3. 自治体ごとのカレンダー
    failed = []
    for m, mod in targets:
        print(f"\n== {m}")
        try:
            data = mod.make_calendar(m.year_dir(year), year)
            if data["year"] != year:
                raise ValueError(f"年度がちがいます（{data['year']}）")
            if not data.get("schedules") or not data.get("areas"):
                raise ValueError("日程か地区が空です")
        except (Exception, SystemExit) as e:
            if isinstance(e, Exception):
                traceback.print_exc()
            else:
                print(e)
            failed.append(m)
            continue
        print("wrote", m.write_calendar(data).relative_to(M.ROOT))

    # 4. 地図（地区の名前が変わることがあるので、毎年作り直す）
    print("\n== 今いる場所から探す（geo/）")
    subprocess.run([sys.executable, str(TOOLS / "build_geo.py")] + sorted({m.pref for m, _ in targets}), check=True)

    if failed:
        print("\n!! 読み取れなかった自治体（前の年度のデータのまま）:")
        for m in failed:
            print("   ", m, f"→ tools/munis/{m.path}/calendar.py を直す")
    print(f"""
== 次にやること
  1. アプリをブラウザで開いて、各自治体のいくつかの地区のカレンダーが、市の配布物と合っているか見くらべる
     （年度が始まる前に確かめるときは、アドレスの最後に ?date={year}-04-01 を付ける）
  2. 自治体ごとの注意（tools/munis/<県>/<自治体>/README.md）を確かめる
  3. GitHub Desktop で Commit → Push origin""")
    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
