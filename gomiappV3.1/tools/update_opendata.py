"""オープンデータから作っているデータを、最新のオープンデータで作り直す。

使い方（gomi フォルダで実行）:
  python gomiappV3.1/tools/update_opendata.py                 ← すべての自治体：カタログから最新を取ってきて、作り直す
  python gomiappV3.1/tools/update_opendata.py 35215 下松市    ← 自治体を指定（自治体コードか名前）
  python gomiappV3.1/tools/update_opendata.py --no-fetch      ← 取ってこないで、元データ/ にあるもので作り直す
  python gomiappV3.1/tools/update_opendata.py --check         ← 取ってくるだけ（作り直さない）。カタログの更新日を見る

使うオープンデータと作り方は、自治体ごとの tools/munis/<県>/<自治体>/opendata.py に書いてある。
取ってきたファイルは 元データ/<県>/<自治体>/オープンデータ/ に保存し、横に <名前>.meta.json（どこから・カタログの更新日）を書く。
収集日のオープンデータ（下松市など）は毎年の更新（download_sources.py → update_year.py）で使う。
作り直したら、アプリをブラウザで開いて確かめ、GitHub Desktop で Commit → Push origin。
"""
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)
sys.path.insert(0, str(Path(__file__).resolve().parent / "lib"))
import munis as M  # noqa: E402
import opendata as OD  # noqa: E402
import web as W  # noqa: E402


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    fetch, check = "--no-fetch" not in sys.argv, "--check" in sys.argv
    done = 0
    for m in M.munis(args or None):
        mod = m.module("opendata")
        if not mod:
            continue
        print(f"== {m}")
        src = m.src_dir / "オープンデータ"
        for ds in mod.DATASETS:
            path = src / ds["file"]
            if fetch:
                old = OD.meta(path)
                meta = OD.fetch(ds["url"], path, ds["pick"], W)
                if not meta:
                    print(f"  ！ {ds['use']}：カタログにファイルが見つかりません（{ds['url']}）")
                    continue
                new = not old or old.get("modified") != meta["modified"]
                print(f"  {ds['use']}：カタログの更新日 {meta['modified']}{'（新しくなっています）' if new and old else ''} → {path.relative_to(M.ROOT)}")
            else:
                meta = OD.meta(path)
                print(f"  {ds['use']}：{path.relative_to(M.ROOT)}（カタログの更新日 {meta['modified'] if meta else '不明'}）")
        if not check:
            for line in mod.build(src):
                print("  " + line)
        done += 1
    if not done:
        print("オープンデータを使っている自治体がありません（tools/munis/<県>/<自治体>/opendata.py）")


if __name__ == "__main__":
    main()
