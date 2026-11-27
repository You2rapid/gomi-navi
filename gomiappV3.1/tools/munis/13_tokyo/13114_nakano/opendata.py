"""東京都 中野区（13114）：オープンデータから品目検索のデータ（data/13_tokyo/13114_nakano/items.js）を作る。

このファイルのきまり（どの自治体も同じ形。tools/update_opendata.py から使う）:
  DATASETS  … 使うオープンデータ（用途・データセットのページ・保存する名前・どのファイルか）
              保存先は 元データ/<県>/<自治体>/オープンデータ/
  build(src) … src（上のフォルダ）のファイルからアプリのデータを作って書く。作ったものの説明（文字列のリスト）を返す

元：東京都オープンデータカタログサイトの中野区「ごみ分別一覧」（CC BY。ファイルは 2025-02-28。約940品目。UTF-8）
  列は見出しのとおり：1列目が品目（ごみの品目）、2列目が読み（インデックス）、3列目が分別区分（種別）、4列目が説明。
  区分は「資源プラスチック」（令和6年4月からの分け方）になっていて、区のページの区分（燃やすごみ・陶器・ガラス・金属ごみ・
  資源プラスチック・びん・缶・ペットボトル・古紙（集団回収）・粗大ごみ）と同じ。
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
    {"use": "品目", "url": CATALOG + "t131148d0000000139",
     "file": "131148_garbage_separation.csv", "pick": lambda r: r["format"] == "CSV"},
]

# 分別区分 → アプリの区分（city.js の cats）
CAT = {
    "燃やすごみ": "燃やす", "陶器・ガラス・金属ごみ": "陶ガラ金", "資源プラスチック": "資源プラ",
    "びん・缶・ペットボトル": "びん缶ペット", "古紙（集団回収）": "集団", "古着・古布（集団回収）": "集団",
    "粗大ごみ": "粗大", "家電リサイクル法対象品目": "家電", "区では収集しないもの": "×", "パソコン": "×",
    "使用済小型家電（拠点回収）": "拠点", "食用油（拠点回収）": "拠点", "乾電池（拠点回収）": "拠点",
    "インクカートリッジ（拠点回収）": "拠点", "使用済蛍光管（拠点回収）": "拠点",
}
# 区分の名前を注意の頭に書くもの（アプリの区分の名前だけではわからないもの）
NOTE_KUBUN = {"古紙（集団回収）", "古着・古布（集団回収）", "パソコン", "使用済小型家電（拠点回収）", "食用油（拠点回収）",
              "乾電池（拠点回収）", "インクカートリッジ（拠点回収）", "使用済蛍光管（拠点回収）"}
HEAD = ["ごみの品目", "インデックス", "種別", "説明"]


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
    if rows[0][:4] != HEAD:
        raise SystemExit(f"品目のオープンデータの列がかわりました（{rows[0]}）。opendata.py を直す")
    items, seen, unknown = [], set(), []
    for r in rows[1:]:
        if len(r) < 4 or not r[0].strip():
            continue
        name, kubun = tidy(r[0]), tidy(r[2])
        c = CAT.get(kubun)
        if not c:
            unknown.append(f"{name}（{kubun}）")
            continue
        if (name, c) in seen:
            continue
        seen.add((name, c))
        d = [x for x in (tidy(r[3]),) if x]
        if kubun in NOTE_KUBUN:
            d.insert(0, kubun)
        y = re.sub(r"[（(].*", "", unicodedata.normalize("NFKC", r[1])).strip() or kana.yomi(re.sub(r"（.*", "", name))
        it = {"n": name, "c": c, "y": y}
        if d:
            it["d"] = "。".join(x.rstrip("。") for x in d)
        items.append(it)
    if unknown:
        raise SystemExit("アプリの区分に当てはまらない分別区分があります（CAT に足す）：" + "、".join(unknown))
    m = M.munis(["13114"])[0]
    rows_js = [json.dumps(x, ensure_ascii=False, separators=(",", ":")) for x in items]
    (m.data_dir / "items.js").write_text(
        f"// 東京都 中野区（13114）の品目検索のデータ（{len(items)}件）\n"
        "// 東京都オープンデータカタログサイトの中野区「ごみ分別一覧」（CC BY）から自動で作ったファイルです。\n"
        "// 手で直さず、python gomiappV3.1/tools/update_opendata.py 13114 で作り直してください。\n"
        "// 1行に1品目：{n:品名, c:区分, y:読み, d:注意}\n"
        'gomiData("13114", "items", /*ITEMS-START*/[\n' + ",\n".join(rows_js) + "\n]/*ITEMS-END*/);\n",
        encoding="utf-8", newline="\n")
    return [f"品目 {len(items)}件 → {m.data_dir / 'items.js'}"]
