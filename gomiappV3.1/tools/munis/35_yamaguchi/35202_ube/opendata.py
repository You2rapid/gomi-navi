"""山口県 宇部市（35202）：オープンデータから品目検索のデータ（data/35_yamaguchi/35202_ube/items.js）を作る。
収集日のオープンデータ（「各地区のごみ収集日」の CSV）は、calendar.py が市のページと見くらべるのに使う。

このファイルのきまり（どの自治体も同じ形。tools/update_opendata.py から使う）:
  DATASETS  … 使うオープンデータ（用途・データセットのページ・保存する名前・どのファイルか・old_days：古さの注意を出すまでの日数）
              保存先は 元データ/<県>/<自治体>/オープンデータ/
  build(src) … src（上のフォルダ）のファイルからアプリのデータを作って書く。作ったものの説明（文字列のリスト）を返す

元：山口県オープンデータカタログサイト「【宇部市】ごみ収集」（CC BY 4.0）の
  「ごみの種類とごみの出し方」（Excel。市の「ごみ分別案内」チャットボットのデータ）と「各地区のごみ収集日」（CSV。1〜12月の暦年）
（「【宇部市】ゴミ集積所一覧」は、市が非公開にしていてデータがない）
"""
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "lib"))
import kana  # noqa: E402
import munis as M  # noqa: E402
import xlsx  # noqa: E402

DATASET = "https://yamaguchi-opendata.jp/ckan/dataset/352021_garbage_collection"
DATASETS = [
    {"use": "品目", "url": DATASET, "file": "gomibunbetsulist.xlsx", "pick": lambda r: r["format"] == "XLSX"},
    {"use": "収集日（市のページと見くらべる）", "url": DATASET, "file": "garbage_collection.csv",
     "pick": lambda r: "収集日" in r["name"]},
]

# オープンデータのカテゴリー → アプリの区分（city.js の cats）。古紙の3つは1つの区分にし、注意に種類を書く
CATS = {"【燃やせるごみ】": "燃やせる", "【月1回収集の燃やせるごみ】": "月1可燃", "【燃やせないごみ】": "不燃",
        "【びん・缶】": "びん缶", "【ペットボトル】": "ペット", "【危険ごみ】": "危険",
        "【プラスチック製容器包装】": "プラ", "【古紙（新聞）】": "古紙", "【古紙（雑誌・雑がみ）】": "古紙",
        "【古紙（段ボール）】": "古紙", "【紙製容器包装】": "紙容器", "【小型家電品目】": "小型家電",
        "【粗大ごみ】": "粗大", "【ステーションの利用不可】": "持込", "【市での処理不可】": "×",
        "【家電リサイクル法対象品】": "家電"}
KOSHI = {"【古紙（新聞）】": "新聞", "【古紙（雑誌・雑がみ）】": "雑誌・雑がみ", "【古紙（段ボール）】": "段ボール"}
# ごみの品目ではない行（チャットボットのあいさつ・冗談の答え、操作の案内、材質の名前）は入れない
NOT_ITEMS = {"明日", "ありがとう", "夫・旦那", "過去", "彼女", "彼氏", "希望", "恋人", "妻", "未来", "目標", "夢",
             "燃やせるごみの日", "燃やせないごみの日", "ポリプロピレン・ポリエチレン"}


def note_of(s):
    """「♻\n🚮注意事項\n…」→ 注意の文。URL は取り、行は「。」でつなぐ"""
    s = s.split("注意事項", 1)[-1] if "注意事項" in s else s.replace("♻", "")
    s = re.sub(r"https?://\S+", "", s)
    s = re.sub(r"(詳しくは、?|※詳しくは、?)[^。\n]*をご覧ください", "", s)
    lines = [x.strip(" 　") for x in s.splitlines()]
    out = "。".join(x for x in lines if x)
    return re.sub(r"。+", "。", out).strip("。")


def yomi_of(n, furi):
    """読み：Excel の「品目（フリガナ）」の1つ目がひらがななら、それを使う。なければ機械で読む"""
    first = furi.split(";")[0].strip()
    if first and re.fullmatch(r"[ぁ-んー・（）()～、 　]+", first):
        return first
    return kana.yomi(n)


def build(src):
    src = Path(src)
    rows = list(xlsx.sheets(src / "gomibunbetsulist.xlsx").values())[0]
    head = rows[0]
    if head[:4] != ["品目", "品目（フリガナ）", "類義語", "カテゴリー"]:
        raise SystemExit(f"Excel の見出しが変わっています：{head}")
    items, unknown, skipped = [], [], []
    for r in rows[1:]:
        r = r + [""] * (5 - len(r))
        n, cat, raw = kana.letters(r[0]).strip(), r[3].strip(), r[4]
        if not n:
            continue
        if n in NOT_ITEMS or "操作メニュー" in raw:
            skipped.append(n)
            continue
        c = CATS.get(cat)
        if not c:
            unknown.append(f"{n}（{cat or '空'}）")
            continue
        note = note_of(raw)
        if cat in KOSHI:
            note = f"古紙の「{KOSHI[cat]}」として出す。" + note if note else f"古紙の「{KOSHI[cat]}」として出す"
        items.append([n, c, yomi_of(n, r[1]), note])
    if unknown:
        raise SystemExit("アプリの区分に当てはまらないカテゴリーがあります（CATS か NOT_ITEMS に足す）：" + "、".join(unknown))
    m = M.munis(["35202"])[0]
    rows_js = [json.dumps(x, ensure_ascii=False, separators=(",", ":")) for x in items]
    (m.data_dir / "items.js").write_text(
        f"// 山口県 宇部市（35202）の品目検索のデータ（{len(items)}件）\n"
        "// 山口県オープンデータカタログサイト「【宇部市】ごみ収集」の「ごみの種類とごみの出し方」（CC BY 4.0）から自動で作ったファイルです。\n"
        "// 手で直さず、python gomiappV3.1/tools/update_opendata.py 35202 で作り直してください。\n"
        "// 1行に1品目：[品名, 区分, 読み, 注意]\n"
        'gomiData("35202", "items", /*ITEMS-START*/[\n' + ",\n".join(rows_js) + "\n]/*ITEMS-END*/);\n",
        encoding="utf-8", newline="\n")
    return [f"品目 {len(items)}件 → {m.data_dir / 'items.js'}（品目でない行 {len(skipped)}件を外した：{'、'.join(skipped)}）"]
