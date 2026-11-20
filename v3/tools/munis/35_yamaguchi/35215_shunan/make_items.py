"""山口県 周南市（35215）：品目検索のデータ（data/35_yamaguchi/35215_shunan/items.js）を作る。

周南市の品目は、冊子「家庭ごみの分別方法」の分別早見表から、初版（v1）の道具で読み取っている。
冊子が改定されたら（gomi フォルダで）:
  1. python tools/extract_items.py 元データ/35_山口県/35215_周南市/分別の冊子/<冊子>.pdf items.json warn.txt gomi_items.js
     （初版の道具。warn.txt に読めなかった所が出る）
  2. python v3/tools/munis/35_yamaguchi/35215_shunan/make_items.py gomi_items.js
     （下の EXTRA を足して items.js に書く）
"""
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "lib"))
import munis as M  # noqa: E402

# 早見表に無いがよく探される言葉（分別ページの記載から補足）
EXTRA = [
    {"n": "生ごみ", "c": "可燃", "k": "ナ", "y": "なまごみ", "d": "水気をよく切ってください。"},
    {"n": "ダンボール", "c": "紙衣", "k": "タ", "d": "粘着テープ・宛先シールなどをできるだけ取り除き、ひもで十文字にしばってください。"},
    {"n": "雑がみ（紙箱・包装紙・紙袋など）", "c": "紙衣", "k": "サ", "y": "ざつがみ（かみばこ・ほうそうし・かみぶくろなど）", "d": "小さな雑がみは紙袋に入れてから、ひもで十文字にしばってください。"},
    {"n": "牛乳パック", "c": "紙衣", "k": "キ", "y": "ぎゅうにゅうぱっく", "d": "中を水洗いして切り開き、乾かしてからひもで十文字にしばってください。内側が銀色のものは「燃やせるごみ」へ"},
]

if __name__ == "__main__":
    src = Path(sys.argv[1]).read_text(encoding="utf-8")
    items = json.loads(re.search(r"window\.GOMI_ITEMS = (\[.*\]);", src, re.S).group(1)) + EXTRA
    m = next(x for x in M.munis(["35215"]))
    rows = [json.dumps(x, ensure_ascii=False, separators=(",", ":")) for x in items]
    (m.data_dir / "items.js").write_text(
        f"// 山口県 周南市（35215）の品目検索のデータ（{len(items)}件）。作り方は tools/munis/35_yamaguchi/35215_shunan/README.md\n"
        "// 1行に1品目：{n:品名, c:区分, k:50音の行（カタカナ1文字）, y:読み, d:注意, new/chg:冊子の新規掲載・区分変更}\n"
        f'gomiData("35215", "items", /*ITEMS-START*/[\n' + ",\n".join(rows) + "\n]/*ITEMS-END*/);\n",
        encoding="utf-8", newline="\n")
    print(len(items), "件 →", m.data_dir / "items.js")
