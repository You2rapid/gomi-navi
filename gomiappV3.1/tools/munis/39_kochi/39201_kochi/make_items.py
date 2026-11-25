"""高知県 高知市（39201）：品目検索のデータ（data/39_kochi/39201_kochi/items.js）を作る。

高知市には品目のオープンデータがない。市の「高知市家庭ごみ辞典」（令和7年5月改訂版、50音順の品目別出し方一覧表、文字の入った PDF）
の表を読む。表は「品名｜分別区分｜備考（注釈）」の3列で、行は横の線で区切られている。
PDF の文字を1文字ずつ、横の位置で3列に分け、横の線のあいだを1行（1品目）にする。

辞典が新しくなったら、元データ/39_高知県/39201_高知市/分別の冊子/ に置き直し、下の BOOKLET_PDF を直して動かす。

使い方（gomi フォルダで）: python gomiappV3.1/tools/munis/39_kochi/39201_kochi/make_items.py
"""
import json
import re
import sys
from pathlib import Path

import pymupdf

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "lib"))
import kana  # noqa: E402
import munis as M  # noqa: E402

sys.stdout.reconfigure(encoding="utf-8")

# 元にした冊子（状況一覧で見る）：元データ/39_高知県/39201_高知市/ からの場所・名前・発行した月
BOOKLET_PDF = "分別の冊子/高知市家庭ごみ辞典_R7.5.pdf"
BOOKLET_TITLE = "高知市家庭ごみ辞典（令和7年5月改訂版）"
BOOKLET_DATE = "2025-05"
COL_CAT, COL_NOTE = 190, 325     # 列の境目（PDF の横の位置）

# 辞典の分別区分 → アプリの区分（city.js の cats）
CAT = {
    "可燃ごみ": "可燃", "可燃ごみ（単品のもの）": "可燃",
    "プラスチック製容器包装": "プラ",
    "資源物「新聞・チラシ」": "紙類", "資源物「ダンボール」": "紙類", "資源物「雑誌」": "紙類",
    "資源物「飲料用紙パック」": "紙類", "資源物「雑がみ」": "紙類",
    "資源物「布類」": "布類", "資源物「衣類」": "布類",
    "資源物「ビン」": "ビン", "資源物「カン」": "カン", "資源物「金属」": "金属",
    "水銀を含むごみ": "水銀", "家電品": "家電品", "可燃粗大ごみ": "粗大", "不燃ごみ": "不燃",
    "発火器具・ライター類": "発火",
    "回収協力店等へ": "ペット",
    "排出禁止物": "×", "排出禁止": "×",
    "排出禁止物（家電リサイクル法対象品）": "家電リ", "排出禁止物（リサイクル法対象品）": "家電リ",
}
# 資源物の細かい分け方（辞典の「」の中）は、注意の頭に書く
SUB = {"資源物「新聞・チラシ」": "新聞・チラシ", "資源物「ダンボール」": "ダンボール", "資源物「雑誌」": "雑誌",
       "資源物「飲料用紙パック」": "飲料用紙パック", "資源物「雑がみ」": "雑がみ", "資源物「衣類」": "衣類"}
HEAD = re.compile(r"^(品\s*名|分別区分|備考（注釈）|品目別出し方一覧表|\d+|[ぁ-ん])$")


def nfkc_paren(s):
    return s.replace("(", "（").replace(")", "）")


def chars(page):
    """ページの文字を (x, y中心, 文字) で返す"""
    out = []
    for b in page.get_text("rawdict")["blocks"]:
        for ln in b.get("lines", []):
            for sp in ln["spans"]:
                for ch in sp["chars"]:
                    x0, y0, x1, y1 = ch["bbox"]
                    out.append(((x0 + x1) / 2, (y0 + y1) / 2, ch["c"]))
    return out


def cell_text(cs):
    """1つのセルの文字を、上の行から順に左から並べる"""
    lines = []
    for x, y, c in sorted(cs, key=lambda t: (t[1], t[0])):
        if lines and abs(lines[-1][0] - y) <= 3:
            lines[-1][1].append((x, c))
        else:
            lines.append([y, [(x, c)]])
    return join_lines(["".join(c for _, c in sorted(ws)) for _, ws in lines])


# 備考の行のつなぎ方：折り返しはそのままつなぎ、文の終わりらしいところ（「」」「ごみ」「連絡」…で終わる行、次が「※」）は「。」を入れる
END = ("」", "ごみ", "可能", "連絡", "手続き", "ください")


def join_lines(lines):
    out = ""
    for ln in lines:
        if out and not out.endswith("。"):
            closed = out.endswith("）") and out.count("（") + out.count("(") == out.count("）") + out.count(")")
            if ln.startswith("※") or out.endswith(END) or closed:
                out += "。"
        out += ln
    return out.strip()


def read_booklet(pdf):
    rows, problems = [], []
    for pg, page in enumerate(pymupdf.open(pdf), 1):
        hs = sorted({round(it[1].y, 1) for g in page.get_drawings() for it in g["items"]
                     if it[0] == "l" and abs(it[1].y - it[2].y) < 0.5 and abs(it[1].x - it[2].x) > 100})
        cs = [c for c in chars(page) if c[2].strip()]
        # 50音の見出し（「か」など）と表の見出し（品名・分別区分・備考）の行の上下にも、区切りの線がないことがあるので足す
        lines = {}
        for x, y, c in cs:
            lines.setdefault(round(y), []).append((x, c))
        for y, ws in lines.items():
            t = "".join(c for _, c in sorted(ws))
            if re.fullmatch(r"[ぁ-ん]|品\s*名|分別区分|備考[（(]注釈[）)]", t) or re.search(r"分別区分|備考[（(]注釈", t):
                hs += [y - 5, y + 5]
        hs = sorted(set(hs))
        for top, bot in zip(hs, hs[1:]):
            cell = [c for c in cs if top < c[1] < bot]
            n = cell_text([c for c in cell if c[0] < COL_CAT])
            k = cell_text([c for c in cell if COL_CAT <= c[0] < COL_NOTE])
            d = cell_text([c for c in cell if c[0] >= COL_NOTE])
            d = re.sub(r"備考[（(]注釈[）)]", "", d).strip()
            k = k.replace("分別区分", "").replace("(", "（").strip()
            n = re.sub(r"品\s*名", "", n).strip()
            if HEAD.match(n) and not k:
                continue
            if not n and not k:
                continue
            if not n or k not in CAT:
                problems.append(f"{pg}ページ：読めない行「{n}｜{k}｜{d}」")
                continue
            rows.append((nfkc_paren(n), k, d.replace("，", "、")))
    return rows, problems


def build(src_dir):
    rows, problems = read_booklet(src_dir / BOOKLET_PDF)
    out, seen = [], set()
    for n, k, d in rows:
        if n in seen:
            continue
        seen.add(n)
        if d.startswith("のマーク"):
            # 辞典ではマークの絵のあとに「のマークがあるもの」と続く（絵は文字にならない）
            d = {"プラ": "プラマーク", "ペット": "PETマーク"}.get(CAT[k], "マーク") + d[len("の") + 3:]
        # 文の途中のマークの絵（ガロンボトル：ペットボトルの回収ボックスの話なので PET マーク）
        d = d.replace("ごみへのマークがあるもの", "ごみへ。PETマークがあるもの")
        if k in SUB:
            d = f"資源物の「{SUB[k]}」に分けて出します。" + (d if d else "")
        elif k.startswith("排出禁止物（"):
            d = "市では収集しません（" + k[len("排出禁止物（"):].rstrip("）") + "）。" + d
        elif k == "回収協力店等へ":
            d = "店舗などの回収ボックスへ。" + d
        out.append({"n": n, "c": CAT[k], "y": kana.yomi(n), **({"d": d} if d else {})})
    return out, problems


if __name__ == "__main__":
    m = M.munis(["39201"])[0]
    items, problems = build(m.src_dir)
    for p in problems:
        print("  ？", p)
    rows = [json.dumps(x, ensure_ascii=False, separators=(",", ":")) for x in items]
    path = m.data_dir / "items.js"
    path.write_text(
        f"// 高知県 高知市（39201）の品目検索のデータ（{len(items)}件）\n"
        f"// 高知市「{BOOKLET_TITLE}」の品目別出し方一覧表。tools/munis/39_kochi/39201_kochi/make_items.py で作る\n"
        "// 1行に1品目：{n:品名, c:区分, y:読み, d:注意}\n"
        'gomiData("39201", "items", /*ITEMS-START*/[\n' + ",\n".join(rows) + "\n]/*ITEMS-END*/);\n",
        encoding="utf-8", newline="\n")
    print(len(items), "件 →", path)
