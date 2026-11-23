"""山口県 岩国市（35208）：オープンデータから品目検索のデータ（data/35_yamaguchi/35208_iwakuni/items.js）を作る。

このファイルのきまり（どの自治体も同じ形。tools/update_opendata.py から使う）:
  DATASETS  … 使うオープンデータ（用途・データセットのページ・保存する名前・どのファイルか・old_days：古さの注意を出すまでの日数）
              保存先は 元データ/<県>/<自治体>/オープンデータ/
  build(src) … src（上のフォルダ）のファイルからアプリのデータを作って書く。作ったものの説明（文字列のリスト）を返す

元：山口県オープンデータカタログサイト「【岩国市】ゴミの分別方法一覧」（CC BY 4.0、令和7年4月時点）
（「【岩国市】ゴミ集積所一覧」は、市が非公開にしていてデータがない。収集日のオープンデータもない）
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
    {"use": "品目", "url": "https://yamaguchi-opendata.jp/ckan/dataset/352080-garbage_separation",
     "file": "garbage_separation.csv", "pick": lambda r: r["format"] == "CSV"},
]

# オープンデータの分別区分 → アプリの区分（city.js の cats）
CATS = {"焼却ごみ": "焼却", "びん類": "びん", "かん類": "かん", "陶磁器及びガラス類": "陶磁器", "プラスチック類": "プラ",
        "金属類及び破砕ごみ": "金属", "資源品": "資源", "処理困難ごみ": "処理困難",
        "粗大ごみ（可燃性）": "粗大", "粗大ごみ（不燃性）": "粗大"}
BOX = "使用済小型家電回収ボックス"


def read_csv(path):
    raw = Path(path).read_bytes()
    for enc in ("utf-8-sig", "cp932"):
        try:
            return list(csv.DictReader(io.StringIO(raw.decode(enc))))
        except UnicodeDecodeError:
            pass
    raise SystemExit(f"{path} の文字コードが読めません")


def one_line(s):
    """注意の文：改行は「。」でつなぐ。先頭の「・」や、行の中のよけいな空白をとる"""
    lines = [re.sub(r"[ 　]+$", "", re.sub(r"^[・\s　]+", "", x)) for x in s.splitlines()]
    out = ""
    for x in (x for x in lines if x):
        out += x if not out or x.startswith("（") else "。" + x   # 「（家電リサイクル法対象品目）」は前の行に続ける
    return out


def item_name(s):
    # 「腕時計・時計（充電池内蔵式）\n※電池が外せない…」→ 品名は1行目、2行目からは注意へ
    s = kana.letters(s).strip()
    first, _, rest = s.partition("\n")
    return first.strip().strip("　"), one_line(rest)


def build(src):
    src = Path(src)
    items, unknown, skipped = [], [], []
    for r in read_csv(src / "garbage_separation.csv"):
        n, extra = item_name(r["ゴミの分別方法_品目"])
        cat = r["ゴミの分別方法_分別区分"].strip()
        note = one_line(r["ゴミの分別方法_注意点"])
        if not n:
            continue   # 品目が空の行
        parts = [p.strip() for p in cat.split(",") if p.strip()]
        if not parts:
            # 区分が空：家電リサイクル法の品目、市では収集しないもの（販売店等へ）、ペットボトル（回収協力店へ）
            if "家電リサイクル法" in note:
                c = "家電"
            elif n.startswith("ペットボトル"):
                c = "ペット"
            elif note:
                c = "×"
            else:
                skipped.append(n)   # 区分も注意も空（市のデータで出し方がわからない）→ 入れない
                continue
        else:
            c = CATS.get(parts[0])
            if not c:
                unknown.append(f"{n}（{cat}）")
                continue
            # 2つ目からの区分（処理困難ごみ・使用済小型家電回収ボックス）は「ほかの出し方」として注意に書く
            others = [("「使用済小型家電回収ボックス」" if p == BOX else f"〔{p}〕") for p in parts[1:]]
            if others:
                note = "・".join(others) + "にも出せる" + ("。" + note if note else "")
            if parts[0].startswith("粗大ごみ（"):
                note = parts[0] + ("。" + note if note else "")   # 粗大ごみ（可燃性）・（不燃性）
        if extra:
            note = extra + ("。" + note if note else "")
        items.append([n, c, kana.yomi(n), note])
    if unknown:
        raise SystemExit("アプリの区分に当てはまらない分別区分があります（CATS に足す）：" + "、".join(unknown))
    m = M.munis(["35208"])[0]
    rows_js = [json.dumps(x, ensure_ascii=False, separators=(",", ":")) for x in items]
    (m.data_dir / "items.js").write_text(
        f"// 山口県 岩国市（35208）の品目検索のデータ（{len(items)}件）\n"
        "// 山口県オープンデータカタログサイト「【岩国市】ゴミの分別方法一覧」（CC BY 4.0）から自動で作ったファイルです。\n"
        "// 手で直さず、python gomiappV3.1/tools/update_opendata.py 35208 で作り直してください。\n"
        "// 1行に1品目：[品名, 区分, 読み, 注意]\n"
        'gomiData("35208", "items", /*ITEMS-START*/[\n' + ",\n".join(rows_js) + "\n]/*ITEMS-END*/);\n",
        encoding="utf-8", newline="\n")
    out = [f"品目 {len(items)}件 → {m.data_dir / 'items.js'}"]
    if skipped:
        out.append(f"区分も注意も空なので入れなかった品目 {len(skipped)}件：{'、'.join(skipped)}")
    return out
