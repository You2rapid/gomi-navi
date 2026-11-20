"""毎年4月の「年度の切り替え」をまとめて行う。

使い方（gomi フォルダで実行）:
  python v3/tools/download_sources.py 2027     ← 市のサイトから新しいカレンダーを 元データ/2027年度/ に保存
  python v3/tools/update_year.py 2027          ← 元データから v3/data/ と v3/geo/towns.json を作り直す

  --check   ファイルがそろっているかだけ調べる（何も書きかえない）

やること:
  1. 元データ/<年度>年度/ に必要なファイルがそろっているか確かめる
  2. 祝日（内閣府のCSV）から data/holidays.js を作る
  3. 3市のカレンダーPDFから data/calendar_*.js を作る（一度、作業用の場所に作り、全部うまくいったら入れかえる）
  4. 地区の一覧から「今いる場所から探す」の geo/towns.json を作り直す
途中で読めないものがあれば止まり、data/ は前のまま残る。
"""
import csv
import datetime as dt
import io
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)
TOOLS = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS))
from datafile import DATA, ROOT, V3, read_calendar, write_holidays, nendo  # noqa: E402

# 市ごとに必要なファイル（元データ/<年度>年度/<市>/ に置く名前）と、作る道具
CITIES = {
    "shunan": ("周南市", "extract_calendar.py",
               ["A.pdf", "B.pdf", "C.pdf", "D.pdf", "E.pdf", "F.pdf", "G.pdf", "H.pdf", "otsushima.pdf",
                "tokuyama_sankan.pdf", "wada_sankan.pdf", "tokuyama.html", "shinnanyo.html", "kumage.html"]),
    "kudamatsu": ("下松市", "extract_kudamatsu.py", ["nishi.pdf", "higashi.pdf"]),
    "hikari": ("光市", "extract_hikari.py",
               ["murozumi.pdf", "mitsui.pdf", "shimata.pdf", "asaekita.pdf", "asaeminami.pdf", "mishima.pdf", "yamato.pdf"]),
}
MAP_FILES = ["r2ka35215.kml", "r2ka35207.kml", "r2ka35210.kml"]


def check(src):
    missing = []
    for key, (name, _, files) in CITIES.items():
        missing += [f"{name}/{f}" for f in files if not (src / name / f).exists()]
    if not (src / "祝日" / "syukujitsu.csv").exists():
        missing.append("祝日/syukujitsu.csv")
    missing += [f"../地図/{f}" for f in MAP_FILES if not (ROOT / "元データ" / "地図" / f).exists()]
    return missing


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
    # 年末年始（12/29〜1/3）は祝日でなくても、どの市も収集が休み
    year_end = [dt.date(year, 12, d).isoformat() for d in (29, 30, 31)] + [dt.date(year + 1, 1, d).isoformat() for d in (1, 2, 3)]
    return sorted(days), year_end


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if not args:
        raise SystemExit(__doc__)
    year = int(args[0])
    src = ROOT / "元データ" / f"{year}年度"
    print(f"== {nendo(year)} のデータを作ります（元データ: {src}）")
    missing = check(src)
    if missing:
        print("足りないファイルがあります。tools/download_sources.py で保存するか、手でダウンロードしてください:")
        for m in missing:
            print("  ", m)
        raise SystemExit(1)
    print("ファイルはそろっています。")
    if "--check" in sys.argv:
        return

    work = Path(tempfile.mkdtemp(prefix="gomi_update_"))
    try:
        hol, ye = holidays(year, src / "祝日" / "syukujitsu.csv")
        write_holidays(year, hol, ye, work / "holidays.js")
        print(f"祝日 {len(hol)}日")
        for key, (name, tool, _) in CITIES.items():
            print(f"\n== {name}（tools/{tool}）")
            out = work / f"calendar_{key}.js"
            r = subprocess.run([sys.executable, str(TOOLS / tool), str(src / name), str(year), str(out)])
            if r.returncode != 0 or not out.exists():
                raise SystemExit(f"{name} のカレンダーを読み取れませんでした。上のメッセージを見てください（data/ は前のままです）。")
            cal = read_calendar(key, out)
            if cal["year"] != year:
                raise SystemExit(f"{name}: 年度がちがいます（{cal['year']}）")
        # ここまで全部うまくいったので、data/ を入れかえる
        for f in work.iterdir():
            shutil.copy(f, DATA / f.name)
        print(f"\n書きかえました: {DATA}")
    finally:
        shutil.rmtree(work, ignore_errors=True)

    print("\n== 今いる場所から探す（geo/towns.json）")
    subprocess.run([sys.executable, str(TOOLS / "build_geo.py"), str(ROOT / "元データ" / "地図"), str(V3 / "geo" / "towns.json")], check=True)

    print(f"""
== できあがり。次にやること
  1. アプリをブラウザで開いて、各市の地区のカレンダーが市の配布物と合っているか、いくつか見くらべる
     （年度が始まる前に確かめるときは、アドレスの最後に ?date={year}-04-01 を付ける）
  2. 光市の大和地区のように出す時刻が地区でちがう所、周南市の山間部の注記（tools/extract_calendar.py の
     MOUNTAIN_OVERRIDES）が新しいカレンダーでも同じか確かめる
  3. GitHub Desktop で Commit → Push origin""")


if __name__ == "__main__":
    main()
