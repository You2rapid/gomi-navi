"""京都府 宇治市（26204）：品目検索のデータ（data/26_kyoto/26204_uji/items.js）を作る。

宇治市には品目のオープンデータがない。市の「宇治市ごみ分別辞典」（PDF、76ページ）の「家庭ごみ分別辞典」の表（21〜74ページ目）を読む。
表は「50音｜品目｜分別区分（①・②の2つのマス）｜出し方アドバイス」で、行は横の線で区切られている。
PDF の文字を1文字ずつ、横の位置で列に分け、横の線のあいだを1行（1品目）にする。
分別区分が2つ（①・②）あるものは、①をアプリの区分にして、注意の頭に「①○○ ②○○」を書く（どちらになるかは出し方アドバイスに書いてある）。

辞典が新しくなったら、元データ/26_京都府/26204_宇治市/分別の冊子/ に置き直し、下の BOOKLET_PDF を直して動かす。

使い方（gomi フォルダで）: python gomiappV3.1/tools/munis/26_kyoto/26204_uji/make_items.py
"""
import json
import re
import sys
import unicodedata
from pathlib import Path

import pymupdf

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "lib"))
import kana  # noqa: E402
import munis as M  # noqa: E402

sys.stdout.reconfigure(encoding="utf-8")

# 元にした冊子（状況一覧で見る）：元データ/26_京都府/26204_宇治市/ からの場所・名前・発行した月
BOOKLET_PDF = "分別の冊子/ごみ分別辞典.pdf"
BOOKLET_TITLE = "宇治市ごみ分別辞典"
BOOKLET_DATE = "2026-05"
X_NAME, X_CAT, X_CAT2, X_NOTE, X_END = 82, 235, 294.5, 354, 560     # 列の境目（PDF の横の位置）

# 辞典の分別区分 → アプリの区分（city.js の cats）
CAT = {
    "もえるごみ": "もえる", "もえないごみ": "もえない", "プラスチック資源": "プラ", "缶": "缶", "びん": "びん",
    "ペットボトル": "ペット", "古紙（古布）類": "古紙", "拠点回収": "拠点", "海外リユース": "リユース",
    "有料臨時ごみ": "臨時", "家電リサイクル": "家電リ", "ごみ収集場所に出せないもの": "×", "ごみ収集場所": "×",
    "ごみ収集場所に出せないもの": "×", "まち美化推進課窓口": "窓口",
    # 辞典で分別区分のマスに品名が書いてあるもの（別の袋に入れて、決まった日に出す。市の「乾電池…、スプレー缶・ボンベ缶の出し方」のページ）
    "スプレー缶": "もえない", "カセットボンベ缶": "もえない", "乾電池": "もえる", "ライター": "もえない",
}


# 辞典（2026年5月）のあとで市が出し方を変えたもの：{品名: (区分, 注意)}。市のページを元にする。README.md にも書く
FIX = {
    "ボタン型電池": ("もえる", "2026年7月から、もえるごみの日に、もえるごみとは別の透明か白色半透明の袋（乾電池と同じ袋でもよい）に入れて出す"
                           "（市のページ「ボタン型電池の出し方が一部変更になりました。」）。"),
    "電池（乾電池・コイン型電池）": ("もえる", "乾電池・コイン型電池（CR・BR）・ボタン型電池だけを別の袋に入れて、もえるごみの日に出す"
                                     "（ボタン型電池は2026年7月から。市のページ「ボタン型電池の出し方が一部変更になりました。」）。"),
}


def nk(s):
    """全角英数字を半角に（①②③ はそのまま残す）"""
    s = "".join(c if c in "①②③" else unicodedata.normalize("NFKC", c) for c in s)
    return s.replace("(", "（").replace(")", "）")


def chars(page):
    out = []
    for b in page.get_text("rawdict")["blocks"]:
        for ln in b.get("lines", []):
            for sp in ln["spans"]:
                for ch in sp["chars"]:
                    x0, y0, x1, y1 = ch["bbox"]
                    if ch["c"].strip():
                        out.append(((x0 + x1) / 2, (y0 + y1) / 2, ch["c"]))
    return out


def lines_of(cs):
    """セルの文字 → 行ごとの文字列（上から）"""
    lines = []
    for x, y, c in sorted(cs, key=lambda t: (t[1], t[0])):
        if lines and abs(lines[-1][0] - y) <= 2.5:
            lines[-1][1].append((x, c))
        else:
            lines.append([y, [(x, c)]])
    return ["".join(c for _, c in sorted(ws)) for _, ws in lines]


def read_booklet(pdf):
    rows, problems = [], []
    for pg, page in enumerate(pymupdf.open(pdf), 1):
        cs = chars(page)
        if not any(c[2] == "品" and 120 < c[0] < 140 and c[1] < 215 for c in cs):
            continue      # 辞典の表のページではない
        hs = sorted({round(d["rect"].y0, 1) for d in page.get_drawings()
                     if d["rect"].height < 3 and d["rect"].width > 300 and d["rect"].x1 > 500})
        # 表のいちばん下（線ではなく、マスの色の下の端）
        bottom = max((d["rect"].y1 for d in page.get_drawings() if d.get("fill") and abs(d["rect"].x0 - X_CAT) < 2), default=0)
        hs = sorted(set(hs + [round(bottom, 1)]))
        for top, bot in zip(hs, hs[1:]):
            cell = [c for c in cs if top < c[1] < bot]
            n = nk("".join(lines_of([c for c in cell if X_NAME < c[0] < X_CAT])))
            k1 = nk("".join(lines_of([c for c in cell if X_CAT <= c[0] < X_CAT2])))
            k2 = nk("".join(lines_of([c for c in cell if X_CAT2 <= c[0] < X_NOTE])))
            k = nk("".join(lines_of([c for c in cell if X_CAT <= c[0] < X_NOTE])))
            if k1.startswith(("①", "②")) and k2.startswith(("①", "②")):
                k = "".join(sorted([k1, k2]))     # ①・②の2つのマス（文字が2行になっていても、マスごとに読む）
            d = nk("".join(lines_of([c for c in cell if X_NOTE <= c[0] < X_END])))
            if not n and not k:
                continue
            if n in ("品目",) or "分別区分" in k:
                continue
            ks = [x for x in re.split(r"[①②③]", k) if x]
            if not n or not ks or any(x not in CAT for x in ks):
                problems.append(f"{pg}ページ：読めない行「{n}｜{k}｜{d}」")
                continue
            rows.append((n, ks, k, d))
    return rows, problems


def build(src_dir):
    rows, problems = read_booklet(src_dir / BOOKLET_PDF)
    out, seen = [], set()
    for n, ks, k, d in rows:
        if n in seen:
            continue
        seen.add(n)
        notes = []
        if len(ks) > 1:
            notes.append(k.replace("②", " ②") + "。")
        elif ks[0] in ("スプレー缶", "カセットボンベ缶", "乾電池", "ライター"):
            day = "もえるごみ" if CAT[ks[0]] == "もえる" else "もえないごみ"
            notes.append(f"{day}の日に、{ks[0]}だけ別の袋に入れて出す。")
        if d:
            notes.append(d)
        x = {"n": n, "c": CAT[ks[0]], "y": kana.yomi(n)}
        if notes:
            x["d"] = "".join(notes).replace("（。", "。（")
        if n in FIX:
            x["c"], x["d"] = FIX[n]
        out.append(x)
    lack = [k for k in FIX if k not in seen]
    if lack:
        problems.append(f"FIX の品名が辞典にありません：{lack}")
    return out, problems


if __name__ == "__main__":
    m = M.munis(["26204"])[0]
    items, problems = build(m.src_dir)
    for p in problems:
        print("  ？", p)
    rows = [json.dumps(x, ensure_ascii=False, separators=(",", ":")) for x in items]
    path = m.data_dir / "items.js"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f"// 京都府 宇治市（26204）の品目検索のデータ（{len(items)}件）\n"
        f"// 宇治市「{BOOKLET_TITLE}」の家庭ごみ分別辞典の表。tools/munis/26_kyoto/26204_uji/make_items.py で作る\n"
        "// 1行に1品目：{n:品名, c:区分, y:読み, d:注意}\n"
        'gomiData("26204", "items", /*ITEMS-START*/[\n' + ",\n".join(rows) + "\n]/*ITEMS-END*/);\n",
        encoding="utf-8", newline="\n")
    print(len(items), "件 →", path)
