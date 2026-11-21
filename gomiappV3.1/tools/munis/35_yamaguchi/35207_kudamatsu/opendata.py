"""山口県 下松市（35207）：オープンデータから品目検索のデータ（data/35_yamaguchi/35207_kudamatsu/items.js）を作る。
「収集地区一覧」は、今いる場所から探す（geo.py）で町名 → 西地区・東地区 に使う。
収集日のオープンデータ（「【下松市】ゴミ収集カレンダー」）は、毎年の更新で calendar.py が使う。

このファイルのきまり（どの自治体も同じ形。tools/update_opendata.py から使う）:
  DATASETS  … 使うオープンデータ（用途・データセットのページ・保存する名前・どのファイルか・old_days：古さの注意を出すまでの日数）
              保存先は 元データ/<県>/<自治体>/オープンデータ/
  build(src) … src（上のフォルダ）のファイルからアプリのデータを作って書く。作ったものの説明（文字列のリスト）を返す

元：山口県オープンデータカタログサイト「【下松市】ゴミの分別方法一覧」「【下松市】ゴミ収集地区一覧」（CC BY 4.0）
"""
import csv
import io
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "lib"))
import kana  # noqa: E402
import munis as M  # noqa: E402

DATASETS = [
    {"use": "品目", "url": "https://yamaguchi-opendata.jp/ckan/dataset/352071_garbage_separation",
     "file": "garbage_separation.csv", "pick": lambda r: r["format"] == "CSV" and "List of" not in r["name"]},
    {"use": "収集地区（今いる場所）", "url": "https://yamaguchi-opendata.jp/ckan/dataset/352071_garbage_collection_area",
     "file": "garbage_collection_area.csv", "pick": lambda r: r["format"] == "CSV",
     "old_days": 3650},   # 地区の分け方はめったに変わらないので、古さの注意は10年まで出さない
]

# オープンデータの分別区分 → アプリの区分（city.js の cats）
CATS = {"燃やす袋ごみ": "燃やす", "大型可燃ごみ": "大型可燃", "可燃系資源": "可燃資源", "びん・かん類": "びん缶", "ペットボトル": "ペット",
        "金属類": "金属", "小型家電品": "小型家電", "プラスチック製容器包装": "容プラ", "その他プラスチック類": "他プラ",
        "埋立ごみ": "埋立", "大型不燃ごみ": "大型不燃", "有害ごみ": "有害",
        "市では収集しないごみ＜特定家庭用機器＞": "家電", "市では収集しないごみ＜パソコン＞": "家電",
        "市では収集しないごみ＜処理が困難なごみ＞": "×", "市では収集しないごみ＜処理が困難なごみのリサイクルについて＞": "×"}


def read_csv(path):
    raw = Path(path).read_bytes()
    for enc in ("utf-8-sig", "cp932"):
        try:
            return list(csv.DictReader(io.StringIO(raw.decode(enc))))
        except UnicodeDecodeError:
            pass
    raise SystemExit(f"{path} の文字コードが読めません")


def item_name(s):
    s = kana.letters(s).strip().strip("　")
    return re.sub(r"　+", "・", s)


def build(src):
    src = Path(src)
    items, unknown = [], []
    for r in read_csv(src / "garbage_separation.csv"):
        n, cat, note = item_name(r["ゴミの分別方法_品目"]), r["ゴミの分別方法_分別区分"].strip(), r["ゴミの分別方法_注意点"].strip()
        if not n:
            continue   # 品目が空の行
        c = CATS.get(cat)
        if not c and "UMOU" in cat:
            # 羽毛製品（区分の欄に、回収のお知らせの文が入っている）→ 市では収集しない（回収のお知らせを注意に）
            c, note = "×", cat
        if not c:
            unknown.append(f"{n}（{cat}）")
            continue
        items.append([n, c, kana.yomi(n), note])
    if unknown:
        raise SystemExit("アプリの区分に当てはまらない分別区分があります（CATS に足す）：" + "、".join(unknown))
    m = M.munis(["35207"])[0]
    rows_js = [json.dumps(x, ensure_ascii=False, separators=(",", ":")) for x in items]
    (m.data_dir / "items.js").write_text(
        f"// 山口県 下松市（35207）の品目検索のデータ（{len(items)}件）\n"
        "// 山口県オープンデータカタログサイト「【下松市】ゴミの分別方法一覧」（CC BY 4.0）から自動で作ったファイルです。\n"
        "// 手で直さず、python gomiappV3.1/tools/update_opendata.py 35207 で作り直してください。\n"
        "// 1行に1品目：[品名, 区分, 読み, 注意]\n"
        'gomiData("35207", "items", /*ITEMS-START*/[\n' + ",\n".join(rows_js) + "\n]/*ITEMS-END*/);\n",
        encoding="utf-8", newline="\n")
    n_area = len(read_csv(src / "garbage_collection_area.csv"))
    return [f"品目 {len(items)}件 → {m.data_dir / 'items.js'}",
            f"収集地区 {n_area}件（今いる場所から探すは python gomiappV3.1/tools/build_geo.py 35 で作り直す）"]
