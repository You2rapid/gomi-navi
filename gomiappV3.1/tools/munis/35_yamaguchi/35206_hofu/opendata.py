"""山口県 防府市（35206）：オープンデータから品目検索のデータ（data/35_yamaguchi/35206_hofu/items.js）を作る。

このファイルのきまり（どの自治体も同じ形。tools/update_opendata.py から使う）:
  DATASETS  … 使うオープンデータ（用途・データセットのページ・保存する名前・どのファイルか・old_days：古さの注意を出すまでの日数）
              保存先は 元データ/<県>/<自治体>/オープンデータ/
  build(src) … src（上のフォルダ）のファイルからアプリのデータを作って書く。作ったものの説明（文字列のリスト）を返す

元：山口県オープンデータカタログサイト「【防府市】ゴミの分別方法一覧」（CC BY 4.0。データの備考は「2025年6月2日更新」）
（「【防府市】ゴミ集積場所一覧」は、市が「諸事情により公表しない」としていてデータがない。収集日のオープンデータもない）
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
    {"use": "品目", "url": "https://yamaguchi-opendata.jp/ckan/dataset/352063-garbage_separation",
     "file": "garbage_separation.csv", "pick": lambda r: r["format"] == "CSV"},
]

# オープンデータの分別区分 → (アプリの区分（city.js の cats）, 注意の頭に書く言葉)
# 資源ごみ・危険ごみは、集積場所で品目ごとに分けて出すので、どの品目かを注意の頭に書く（カレンダーの「資源 危険」の日に出す）
CATS = {
    "燃やせるごみ": ("可燃", ""),
    "燃やせるごみ又は古着・古布": ("可燃", "古着・古布として、クリーンセンターへの持込みでも回収している"),
    "プラスチック製容器包装": ("プラ", ""),
    "プラスチック製容器包装又はペットボトル": ("プラ", "資源ごみの〔ペットボトル〕にも出せる"),
    "新聞": ("資源", "資源ごみの〔新聞〕"),
    "ダンボール": ("資源", "資源ごみの〔ダンボール〕"),
    "雑がみ": ("資源", "資源ごみの〔雑がみ〕"),
    "雑がみ又はダンボール": ("資源", "資源ごみの〔雑がみ〕か〔ダンボール〕"),
    "紙製容器包装": ("資源", "資源ごみの〔紙製容器包装〕"),
    "紙パック": ("資源", "資源ごみの〔紙パック〕"),
    "ペットボトル": ("資源", "資源ごみの〔ペットボトル〕"),
    "缶": ("資源", "資源ごみの〔缶〕"),
    "びん類": ("資源", "資源ごみの〔びん類〕"),
    "スプレー缶類": ("危険", "危険ごみの〔スプレー缶類〕"),
    "乾電池類": ("危険", "危険ごみの〔乾電池類〕"),
    "水銀体温計": ("危険", "危険ごみの〔水銀体温計〕"),
    "蛍光管": ("危険", "危険ごみの〔蛍光管〕"),
    "ライター類": ("危険", "危険ごみの〔ライター類〕"),
    "陶磁器・ガラス類": ("危険", "危険ごみの〔陶磁器・ガラス類〕"),
    "燃やせないごみ": ("不燃", ""),
    "粗大ごみ": ("粗大", ""),
    "埋立ごみ": ("埋立", ""),
    "拠点回収又は販売店回収": ("小型家電", ""),
    "拠点回収又はメーカー回収": ("小型家電", ""),
    "家電リサイクル法対象品": ("家電", ""),
    "市では処理しません": ("×", ""),
}


def read_csv(path):
    raw = Path(path).read_bytes()
    for enc in ("utf-8-sig", "cp932"):
        try:
            return list(csv.DictReader(io.StringIO(raw.decode(enc))))
        except UnicodeDecodeError:
            pass
    raise SystemExit(f"{path} の文字コードが読めません")


def one_line(s):
    """注意の文：改行は「。」でつなぐ。先頭の「・」や、行の中のよけいな空白、文の終わりの「。」をとる"""
    lines = [re.sub(r"[ 　。]+$", "", re.sub(r"^[・\s　]+", "", x)) for x in s.splitlines()]
    return "。".join(x for x in lines if x)


def build(src):
    src = Path(src)
    items, unknown = [], []
    for r in read_csv(src / "garbage_separation.csv"):
        n = kana.letters(r["品目"]).strip()
        cat = r["分別区分"].strip()
        if not n:
            continue
        if cat not in CATS:
            unknown.append(f"{n}（{cat}）")
            continue
        c, head = CATS[cat]
        note = one_line(r["注意点"])
        note = head + ("。" + note if head and note else note)
        items.append([n, c, kana.yomi(n), note])
    if unknown:
        raise SystemExit("アプリの区分に当てはまらない分別区分があります（CATS に足す）：" + "、".join(unknown))
    m = M.munis(["35206"])[0]
    rows_js = [json.dumps(x, ensure_ascii=False, separators=(",", ":")) for x in items]
    (m.data_dir / "items.js").write_text(
        f"// 山口県 防府市（35206）の品目検索のデータ（{len(items)}件）\n"
        "// 山口県オープンデータカタログサイト「【防府市】ゴミの分別方法一覧」（CC BY 4.0）から自動で作ったファイルです。\n"
        "// 手で直さず、python gomiappV3.1/tools/update_opendata.py 35206 で作り直してください。\n"
        "// 1行に1品目：[品名, 区分, 読み, 注意]\n"
        'gomiData("35206", "items", /*ITEMS-START*/[\n' + ",\n".join(rows_js) + "\n]/*ITEMS-END*/);\n",
        encoding="utf-8", newline="\n")
    return [f"品目 {len(items)}件 → {m.data_dir / 'items.js'}"]
