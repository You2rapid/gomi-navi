"""東京都 江東区（13108）：オープンデータから品目検索のデータ（data/13_tokyo/13108_koto/items.js）を作る。

このファイルのきまり（どの自治体も同じ形。tools/update_opendata.py から使う）:
  DATASETS  … 使うオープンデータ（用途・データセットのページ・保存する名前・どのファイルか）
              保存先は 元データ/<県>/<自治体>/オープンデータ/
  build(src) … src（上のフォルダ）のファイルからアプリのデータを作って書く。作ったものの説明（文字列のリスト）を返す

元：東京都オープンデータカタログサイトの江東区のデータセット（どちらも CC BY）
  ・「ゴミの分別方法一覧」（2026-01-26。約1100品目。列は見出しのとおり：4列目が品目、5列目が分別区分、10列目が備考）
  ・「資源回収・ごみ収集日一覧」（2024-11-30。町名ごとの地区番号と曜日。calendar.py の見くらべに使う）
"""
import csv
import json
import re
import sys
import unicodedata
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "lib"))
import kana  # noqa: E402
import munis as M  # noqa: E402

CATALOG = "https://catalog.data.metro.tokyo.lg.jp/dataset/"
DATASETS = [
    {"use": "品目", "url": CATALOG + "t131083d3100000008",
     "file": "131083_028_garbage_separation.csv", "pick": lambda r: r["format"] == "CSV"},
    {"use": "収集日（区の一覧との見くらべ用）", "url": CATALOG + "t131083d3100000009",
     "file": "131083_201_kotocity_waste_recycle_collectionday.csv", "pick": lambda r: r["format"] == "CSV"},
]

# 分別区分 → アプリの区分（city.js の cats）。かっこの中の種類は注意に書く
CAT = {
    "燃やすごみ": "燃やす", "燃やさないごみ": "燃やさない", "燃やさないごみ（水銀を含む製品）": "燃やさない",
    "燃やさないごみ（発火性）": "燃やさない", "プラスチック": "プラ",
    "資源（古紙）": "資源", "資源（びん・かん・ペットボトル）": "資源", "資源（発泡トレイ・発泡スチロール）": "資源",
    "粗大ごみ": "粗大", "収集不可": "×", "家電リサイクル法対象品": "家電", "パソコン": "×",
    "燃やすごみ・プラスチック": "燃やす",
}
PLAIN = {"燃やすごみ", "燃やさないごみ", "プラスチック", "粗大ごみ"}


def tidy(s):
    s = unicodedata.normalize("NFKC", kana.letters(s)).strip()
    s = s.replace("(", "（").replace(")", "）").replace("　", " ")
    return re.sub(r"\s+", " ", s).strip()


def build(src):
    src = Path(src)
    rows = list(csv.reader(open(src / DATASETS[0]["file"], encoding="utf-8-sig")))
    head = rows[0]
    if head[3:6] != ["ゴミの品目", "分別区分", "注意点"] or head[9] != "備考":
        raise SystemExit(f"品目のオープンデータの列がかわりました（{head}）。opendata.py を直す")
    items, seen, unknown = [], set(), []
    for r in rows[1:]:
        if len(r) < 10 or not r[3].strip():
            continue
        name, kubun = tidy(r[3]), tidy(r[4])
        c = CAT.get(kubun)
        if not c:
            unknown.append(f"{name}（{kubun}）")
            continue
        if (name, c) in seen:
            continue
        seen.add((name, c))
        d = [x for x in (tidy(r[5]), tidy(r[9])) if x]
        if kubun not in PLAIN:
            d.insert(0, kubun)
        it = {"n": name, "c": c, "y": kana.yomi(re.sub(r"（.*", "", name)).strip()}
        if d:
            it["d"] = "。".join(x.rstrip("。") for x in d)
        items.append(it)
    if unknown:
        raise SystemExit("アプリの区分に当てはまらない分別区分があります（CAT に足す）：" + "、".join(unknown))
    m = M.munis(["13108"])[0]
    rows_js = [json.dumps(x, ensure_ascii=False, separators=(",", ":")) for x in items]
    (m.data_dir / "items.js").write_text(
        f"// 東京都 江東区（13108）の品目検索のデータ（{len(items)}件）\n"
        "// 東京都オープンデータカタログサイトの江東区「ゴミの分別方法一覧」（CC BY）から自動で作ったファイルです。\n"
        "// 手で直さず、python gomiappV3.1/tools/update_opendata.py 13108 で作り直してください。\n"
        "// 1行に1品目：{n:品名, c:区分, y:読み, d:注意}\n"
        'gomiData("13108", "items", /*ITEMS-START*/[\n' + ",\n".join(rows_js) + "\n]/*ITEMS-END*/);\n",
        encoding="utf-8", newline="\n")
    return [f"品目 {len(items)}件 → {m.data_dir / 'items.js'}"]
