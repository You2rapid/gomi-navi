"""山口県 周南市（35215）：オープンデータから品目検索のデータ（data/35_yamaguchi/35215_shunan/items.js）を作る。

このファイルのきまり（どの自治体も同じ形。tools/update_opendata.py から使う）:
  DATASETS  … 使うオープンデータ（用途・データセットのページ・保存する名前・どのファイルか）
              保存先は 元データ/<県>/<自治体>/オープンデータ/
  build(src) … src（上のフォルダ）のファイルからアプリのデータを作って書く。作ったものの説明（文字列のリスト）を返す

元：山口県オープンデータカタログサイト「【周南市】ゴミの分別方法一覧」（CC BY 4.0）
"""
import csv
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "lib"))
import kana  # noqa: E402
import munis as M  # noqa: E402

DATASETS = [
    {"use": "品目", "url": "https://yamaguchi-opendata.jp/ckan/dataset/352152_garbage_separation",
     "file": "garbage_separation.csv", "pick": lambda r: r["format"] == "CSV"},
]

# オープンデータの分別区分 → アプリの区分（city.js の cats）
CATS = {"燃やせるごみ": "可燃", "古紙・衣類": "紙衣", "びん・缶類": "びん缶", "ペットボトル": "ペット",
        "容器包装プラスチック": "容プラ", "その他プラスチック": "他プラ", "燃やせないごみ": "不燃", "処理困難物": "処困",
        "粗大ごみ": "粗大", "使用済小型家電": "小型家電", "家電リサイクル対象品": "家電", "市が収集しないもの": "×"}

# オープンデータの品目に無いが、よく探される言葉（アプリで足す。説明はアプリで書いたもの）
EXTRA = [
    {"n": "生ごみ", "c": "可燃", "y": "なまごみ", "d": "水気をよく切ってください。"},
    {"n": "雑がみ（紙箱・包装紙・紙袋など）", "c": "紙衣", "y": "ざつがみ（かみばこ・ほうそうし・かみぶくろなど）",
     "d": "小さな雑がみは紙袋に入れてから、ひもで束ねてください。"},
]

# 半角のかな記号・単位を、アプリの表示に合わせる
FIX = str.maketrans({"｡": "。", "､": "、", "｢": "「", "｣": "」", "･": "・"})


def tidy(s):
    return kana.letters(s).translate(FIX).replace("㎝", "cm").replace("㎏", "kg").strip()


def item_name(s):
    """「空き缶　スプレー缶」→「空き缶（スプレー缶）」、「網（あみ）　網戸のあみ　プラスチック製」→「網（あみ）（網戸のあみ（プラスチック製））」"""
    parts = [p.strip() for p in tidy(s).split("　") if p.strip()]
    if len(parts) == 1:
        return parts[0]
    inner = parts[-1]
    for p in reversed(parts[1:-1]):
        inner = f"{p}（{inner}）"
    return f"{parts[0]}（{inner}）"


def build(src):
    src = Path(src)
    rows = list(csv.DictReader(open(src / "garbage_separation.csv", encoding="utf-8-sig")))
    items, unknown = [], []
    for r in rows:
        c = CATS.get(r["分別区分"].strip())
        if not c:
            unknown.append(f"{r['品目']}（{r['分別区分']}）")
            continue
        n = item_name(r["品目"])
        it = {"n": n, "c": c, "y": kana.yomi(n)}
        if r["注意点"].strip():
            it["d"] = tidy(r["注意点"])
        items.append(it)
    if unknown:
        raise SystemExit("アプリの区分に当てはまらない分別区分があります（CATS に足す）：" + "、".join(unknown))
    items += EXTRA
    m = M.munis(["35215"])[0]
    rows_js = [json.dumps(x, ensure_ascii=False, separators=(",", ":")) for x in items]
    (m.data_dir / "items.js").write_text(
        f"// 山口県 周南市（35215）の品目検索のデータ（{len(items)}件）\n"
        "// 山口県オープンデータカタログサイト「【周南市】ゴミの分別方法一覧」（CC BY 4.0）から自動で作ったファイルです。\n"
        "// 手で直さず、python gomiappV3.1/tools/update_opendata.py 35215 で作り直してください（足す言葉は opendata.py の EXTRA）。\n"
        "// 1行に1品目：{n:品名, c:区分, y:読み, d:注意}\n"
        'gomiData("35215", "items", /*ITEMS-START*/[\n' + ",\n".join(rows_js) + "\n]/*ITEMS-END*/);\n",
        encoding="utf-8", newline="\n")
    return [f"品目 {len(items)}件（オープンデータ {len(items) - len(EXTRA)}件＋アプリで足した言葉 {len(EXTRA)}件）→ {m.data_dir / 'items.js'}"]
