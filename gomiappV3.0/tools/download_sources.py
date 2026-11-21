"""新しい年度のごみ収集カレンダーなどを、市のサイトから 元データ/ にダウンロードする。

使い方（gomi フォルダで実行）:
  python gomiappV3.0/tools/download_sources.py 2027               ← すべての自治体の令和9年度のファイルを保存
  python gomiappV3.0/tools/download_sources.py 2027 35215 光市    ← 自治体を指定（自治体コードか名前）
  python gomiappV3.0/tools/download_sources.py 2027 --list        ← 見つかったファイルの一覧だけ出す（保存しない）

保存先：元データ/<県>/<自治体>/<年度>年度/（祝日は 元データ/全国/<年度>年度/syukujitsu.csv）
探し方は自治体ごとの tools/munis/<県>/<自治体>/calendar.py の download() に書いてある。
見つからないときは、まだ新しい年度のカレンダーが出ていないか、市のページのつくりが変わっている。
そのときは市のページをブラウザで開いて手で保存する（名前は calendar.py の NEED のとおり）。
"""
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)
sys.path.insert(0, str(Path(__file__).resolve().parent / "lib"))
import munis as M  # noqa: E402
import web  # noqa: E402

HOLIDAY_CSV = "https://www8.cao.go.jp/chosei/shukujitsu/syukujitsu.csv"   # 内閣府「国民の祝日」


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if not args:
        raise SystemExit(__doc__)
    year, codes = int(args[0]), args[1:]
    only_list = "--list" in sys.argv
    plan = web.Plan()
    plan.add(HOLIDAY_CSV, M.holiday_csv(year))
    for m in M.munis(codes or None):
        mod = m.module("calendar")
        if not mod or not hasattr(mod, "download"):
            plan.problem(f"{m}：自動でダウンロードするしくみがありません（手で保存してください）")
            continue
        before = len(plan.problems)
        try:
            mod.download(year, m.year_dir(year), web, plan)
        except Exception as e:   # ページが開けないなど
            plan.problem(f"{m}：{e}")
        for i in range(before, len(plan.problems)):
            plan.problems[i] = plan.problems[i] if plan.problems[i].startswith(m.name) else f"{m.name}：{plan.problems[i]}"
    for url, path, raw in plan.todo:
        print(f"{'見つけた' if only_list else '保存'}: {path.relative_to(M.ROOT)}  ←  {url}")
        if only_list:
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw if raw is not None else web.get(url))
    if plan.problems:
        print("\n見つからなかったもの（まだ新しい年度の分が出ていないか、市のページが変わっています）:")
        for p in plan.problems:
            print("  ・", p)
        raise SystemExit(1)
    print("\nぜんぶ見つかりました。" + ("" if only_list else f"次は python gomiappV3.0/tools/update_year.py {year}"))


if __name__ == "__main__":
    main()
