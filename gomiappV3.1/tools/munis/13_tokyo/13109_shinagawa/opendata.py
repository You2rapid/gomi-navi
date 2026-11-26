"""東京都 品川区（13109）：オープンデータから品目検索のデータ（data/13_tokyo/13109_shinagawa/items.js）を作る。

このファイルのきまり（どの自治体も同じ形。tools/update_opendata.py から使う）:
  DATASETS  … 使うオープンデータ（用途・データセットのページ・保存する名前・どのファイルか）
              保存先は 元データ/<県>/<自治体>/オープンデータ/
  build(src) … src（上のフォルダ）のファイルからアプリのデータを作って書く。作ったものの説明（文字列のリスト）を返す

元：東京都オープンデータカタログサイトの品川区「ゴミの分別方法一覧」（CC BY。2025-02-28。415品目。文字コードは Shift_JIS）
  列は見出しのとおり：4列目が品目、5列目が分別区分、6列目が注意点、8列目が料金、10列目が備考。
  分別区分に「燃やすごみ　プラスチック製は資源」のような説明がついているものは、はじめの区分にして、残りを注意に書く。
  「拠点回収」「里帰りプロジェクト」（集積所には出さないもの）と「収集できません」は「×」、家電リサイクル法の品目は「家電」。
  区の「令和8年版ごみ・リサイクルカレンダー」（p.16〜18 分け方・出し方）と分け方が合っていることを見た
  （プラスチックは資源、スプレー缶・小型充電式電池は陶器・ガラス・金属ごみ、乾電池・蛍光灯は資源）。
収集日のオープンデータ「ごみ収集日」（t131091d0000000007）は 2017年のままなので使わない（収集日は calendar.py で区のページから作る）。
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
    {"use": "品目", "url": CATALOG + "t131091d0000000161",
     "file": "131091_garbage_separation.csv", "pick": lambda r: r["format"] == "CSV"},
]

# 分別区分のはじめのことば → アプリの区分（city.js の cats）
CAT = {
    "燃やすごみ": "燃やす", "もやすごみ": "燃やす",          # 「もやすごみ」は「燃やすごみ」の書きちがい（刃物の1行）
    "陶器・ガラス・金属ごみ": "陶器", "資源": "資源", "粗大ごみ": "粗大",
    "収集できません": "×", "拠点回収": "×", "里帰りプロジェクト": "×",
}
# 分別区分の文ぜんたいで決めるもの（はじめのことばでは決められないもの）
WHOLE = {"拠点回収・少量の場合は燃やすごみ": "燃やす"}      # 油（食用）。カレンダーの燃やすごみのページにも「紙や布に染み込ませるか固めて出す。もしくは拠点回収」
KADEN = ("エアコン", "テレビ", "冷蔵庫", "冷凍庫", "洗濯機", "乾燥機")


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


def split_kubun(k):
    """「燃やすごみ プラスチック製は資源」→ ("燃やすごみ", "プラスチック製は資源")、
    「燃やすごみもしくは拠点回収に資源として出す」→ ("燃やすごみ", 元の文)、「拠点回収・少量の場合は燃やすごみ」→ ("拠点回収", 元の文)"""
    for head in sorted(CAT, key=len, reverse=True):
        if k == head:
            return head, ""
        if k.startswith(head):
            rest = k[len(head):].strip()
            return head, (rest if k[len(head)] == " " else k)
    return None, k


def build(src):
    src = Path(src)
    rows = read_csv(src / DATASETS[0]["file"])
    head = rows[0]
    if head[3:6] != ["ゴミの品目", "分別区分", "注意点"] or head[7] != "料金" or head[9] != "備考":
        raise SystemExit(f"品目のオープンデータの列がかわりました（{head}）。opendata.py を直す")
    items, seen, unknown = [], set(), []
    for r in rows[1:]:
        if len(r) < 10 or not r[3].strip():
            continue
        name, kubun = tidy(r[3]), tidy(r[4])
        first, rest = split_kubun(kubun)
        if not first:
            unknown.append(f"{name}（{kubun}）")
            continue
        c = CAT[first]
        if kubun in WHOLE:
            first, rest, c = "", kubun, WHOLE[kubun]
        if c == "×" and first == "収集できません" and any(k in name for k in KADEN):
            c = "家電"
        if (name, c) in seen:
            continue
        seen.add((name, c))
        note = re.sub(r"\S*URL\S*", "", tidy(r[9])).strip()     # 「乾電池に関するURLhttps://…」のような URL の書きこみはのぞく
        d = [x for x in (rest, tidy(r[5]), note) if x]
        if first in ("拠点回収", "里帰りプロジェクト"):
            d.insert(0, f"{first}（集積所には出さない）")
        if c == "粗大" and r[7].strip():
            d.append(f"有料（{r[7].strip()}円）")
        it = {"n": name, "c": c, "y": kana.yomi(re.sub(r"（.*", "", name)).strip()}
        if d:
            it["d"] = "。".join(x.rstrip("。") for x in d)
        items.append(it)
    if unknown:
        raise SystemExit("アプリの区分に当てはまらない分別区分があります（CAT に足す）：" + "、".join(unknown))
    m = M.munis(["13109"])[0]
    rows_js = [json.dumps(x, ensure_ascii=False, separators=(",", ":")) for x in items]
    (m.data_dir / "items.js").write_text(
        f"// 東京都 品川区（13109）の品目検索のデータ（{len(items)}件）\n"
        "// 東京都オープンデータカタログサイトの品川区「ゴミの分別方法一覧」（CC BY）から自動で作ったファイルです。\n"
        "// 手で直さず、python gomiappV3.1/tools/update_opendata.py 13109 で作り直してください。\n"
        "// 1行に1品目：{n:品名, c:区分, y:読み, d:注意}\n"
        'gomiData("13109", "items", /*ITEMS-START*/[\n' + ",\n".join(rows_js) + "\n]/*ITEMS-END*/);\n",
        encoding="utf-8", newline="\n")
    return [f"品目 {len(items)}件 → {m.data_dir / 'items.js'}"]
