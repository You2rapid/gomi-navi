"""東京都 葛飾区（13122）：オープンデータから品目検索のデータ（data/13_tokyo/13122_katsushika/items.js）を作る。

このファイルのきまり（どの自治体も同じ形。tools/update_opendata.py から使う）:
  DATASETS  … 使うオープンデータ（用途・データセットのページ・保存する名前・どのファイルか）
              保存先は 元データ/<県>/<自治体>/オープンデータ/
  build(src) … src（上のフォルダ）のファイルからアプリのデータを作って書く。作ったものの説明（文字列のリスト）を返す

元：東京都オープンデータカタログサイトの葛飾区「ゴミの分別方法一覧」（CC BY。2025-03-31。約750品目。文字コードは Shift_JIS）
  列は見出しのとおり：4列目が品目、5列目が分別区分、6列目が注意点、10列目が備考。
  製品プラスチックを資源の日に出す分け方（区のカレンダー 2026年度版）になっていることと、
  区のカレンダーの「質問の多いもの、まちがえやすいもの参考例」（全地区共通ページ p.15）の品目と分け方が合っていることを見た。
"""
import csv
import io
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
    {"use": "品目", "url": CATALOG + "t131229d0000000014",
     "file": "131229_garbage_separation.csv", "pick": lambda r: r["format"] == "CSV"},
]

# 分別区分 → アプリの区分（city.js の cats）。資源のかっこの中の種類は注意に書く
CAT = {
    "燃やすごみ": "燃やす", "燃やさないごみ": "燃やさない", "プラマーク": "プラ",
    "資源（製品プラスチック）": "資源", "資源（ペットボトル）": "資源", "資源（古紙類）": "資源",
    "資源（びん）": "資源", "資源（缶）": "資源", "資源（食品トレイ）": "資源",
    "粗大ごみ": "粗大", "収集できません": "×",
}
PLAIN = {"燃やすごみ", "燃やさないごみ", "プラマーク", "粗大ごみ", "収集できません"}


def tidy(s):
    s = unicodedata.normalize("NFKC", kana.letters(s)).strip()
    s = s.replace("(", "（").replace(")", "）").replace("　", " ")
    return re.sub(r"\s+", " ", s).strip()


def read_csv(path):
    b = Path(path).read_bytes()
    for enc in ("utf-8-sig", "cp932"):
        try:
            return list(csv.reader(io.StringIO(b.decode(enc))))
        except UnicodeDecodeError:
            pass
    raise SystemExit(f"{path} の文字コードがわかりません")


def build(src):
    src = Path(src)
    rows = read_csv(src / DATASETS[0]["file"])
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
        note = tidy(r[9])
        if c == "×" and "家電販売店" in note:
            c = "家電"        # エアコン・テレビ・冷蔵庫・冷凍庫・洗濯機（家電リサイクル法）
        if (name, c) in seen:
            continue
        seen.add((name, c))
        d = [x for x in (tidy(r[5]), note) if x]
        if r[6].strip() == "有料" and c == "粗大":
            d.append("有料")
        if kubun not in PLAIN:
            d.insert(0, kubun)
        it = {"n": name, "c": c, "y": kana.yomi(re.sub(r"（.*", "", name)).strip()}
        if d:
            it["d"] = "。".join(x.rstrip("。") for x in d)
        items.append(it)
    if unknown:
        raise SystemExit("アプリの区分に当てはまらない分別区分があります（CAT に足す）：" + "、".join(unknown))
    m = M.munis(["13122"])[0]
    rows_js = [json.dumps(x, ensure_ascii=False, separators=(",", ":")) for x in items]
    (m.data_dir / "items.js").write_text(
        f"// 東京都 葛飾区（13122）の品目検索のデータ（{len(items)}件）\n"
        "// 東京都オープンデータカタログサイトの葛飾区「ゴミの分別方法一覧」（CC BY）から自動で作ったファイルです。\n"
        "// 手で直さず、python gomiappV3.1/tools/update_opendata.py 13122 で作り直してください。\n"
        "// 1行に1品目：{n:品名, c:区分, y:読み, d:注意}\n"
        'gomiData("13122", "items", /*ITEMS-START*/[\n' + ",\n".join(rows_js) + "\n]/*ITEMS-END*/);\n",
        encoding="utf-8", newline="\n")
    return [f"品目 {len(items)}件 → {m.data_dir / 'items.js'}"]
