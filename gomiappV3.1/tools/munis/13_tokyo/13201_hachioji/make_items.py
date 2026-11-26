"""東京都 八王子市（13201）：市の「分別辞典」（PDF、令和8年4月1日時点）から品目検索のデータ（items.js）を作る。

使い方（gomi フォルダで）：python gomiappV3.1/tools/munis/13_tokyo/13201_hachioji/make_items.py [--download]
元：元データ/13_東京都/13201_八王子市/分別の冊子/bunbetujiten.pdf（45ページ）
  ページ：https://www.city.hachioji.tokyo.jp/kurashi/gomi/kateigomi/dashikata/p002453.html
市の品目のオープンデータ（東京都オープンデータカタログ「ゴミの分別方法一覧」、2025-03-31）もあるが、
分別辞典（令和8年4月）より古く、品目と区分がちがうところがある（チャイルドシート・クーラーボックスの粗大ごみの種類、
電熱ベスト・マッサージガンなどの新しい品目）ので使わない（README）。
表の形：50音の字（x 24〜）・品名（x 50〜）・分別区分（x 165〜）・出し方（x 261〜）・備考（x 384〜）。
  ・左はしの50音の字（「あ」など）で行を分け、行の中の文字を x の位置で列に分ける（品名などは2行になることがある）。
  ・分別区分「-」は、出し方が「市では処理できません。専門業者へ依頼」なら「×」、「お問い合わせください」「直接持ち込み」なら「相談」（市に問い合わせる）。
"""
import collections
import json
import re
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "lib"))
import kana  # noqa: E402
import munis as M  # noqa: E402

URL = "https://www.city.hachioji.tokyo.jp/kurashi/gomi/kateigomi/dashikata/p002453_d/fil/bunbetujiten.pdf"
PDF = "bunbetujiten.pdf"
CAT = {
    "可燃ごみ": "可燃", "不燃ごみ": "不燃", "有害ごみ": "有害", "容器包装プラスチック": "プラ",
    "缶": "缶", "びん": "びん", "ペットボトル": "ペット", "新聞・チラシ": "新聞", "雑誌・雑紙": "雑誌",
    "ダンボール": "ダンボール", "紙パック": "ダンボール", "古着・古布": "古着",
    "粗大ごみ（可燃）": "粗大", "粗大ごみ（不燃）": "粗大", "粗大ごみ（有害）": "粗大",
    "家電リサイクル": "家電", "パソコンリサイクル": "×",
}


def read_pdf(doc):
    """分別辞典 → [[品名, 分別区分, 出し方, 備考]]"""
    rows = []
    for page in doc:
        lines = []
        for b in page.get_text("dict")["blocks"]:
            for ln in b.get("lines", []):
                t = "".join(s["text"] for s in ln["spans"]).strip()
                if t:
                    lines.append((ln["bbox"][0], ln["bbox"][1], t))
        starts = sorted(y for x, y, t in lines if x < 40 and re.fullmatch(r"[ぁ-んァ-ン]", t))
        foot = min([y for x, y, t in lines if re.search(r"ページ$", t)] + [842])
        for i, y0 in enumerate(starts):
            y1 = starts[i + 1] if i + 1 < len(starts) else foot
            cols = ["", "", "", ""]
            for x, y, t in sorted(lines, key=lambda a: (a[1], a[0])):
                if y0 - 2 <= y < y1 - 2 and x >= 40:
                    cols[0 if x < 160 else 1 if x < 255 else 2 if x < 380 else 3] += t
            rows.append(cols)
    return rows


def main():
    import pymupdf
    m = M.munis(["13201"])[0]
    src = m.src_dir / "分別の冊子" / PDF
    if "--download" in sys.argv or not src.exists():
        src.parent.mkdir(parents=True, exist_ok=True)
        src.write_bytes(urllib.request.urlopen(urllib.request.Request(URL, headers={"User-Agent": "Mozilla/5.0"}), timeout=60).read())
    doc = pymupdf.open(src)
    if "令和８年（202６年）4 月1 日時点" not in doc[1].get_text() and "令和8年" not in doc[1].get_text():
        print("  ！ 分別辞典の時点が令和8年ではありません（新しい版？）")
    rows = read_pdf(doc)
    # 区分ごとのいちばん多い出し方（注意には、それとちがうときだけ出し方を書く）
    usual = {c: collections.Counter(r[2] for r in rows if r[1] == c).most_common(1)[0][0] for c in {r[1] for r in rows}}
    out, seen, bad = [], set(), []
    for name, cat, how, note in rows:
        name = name.strip()
        if cat == "-":
            c = "×" if "処理できません" in how else "相談"
        else:
            c = CAT.get(cat)
        if not name or c is None:
            bad.append((name, cat, how))
            continue
        d = []
        if c == "粗大" or cat in ("新聞・チラシ", "紙パック", "パソコンリサイクル"):
            d.append(cat)
        if how and (how != usual.get(cat) or c == "相談") and c != "×" and how != "お問い合わせください":
            d.append(how)
        if note:
            d.append(note)
        key = (name, c)
        if key in seen:
            continue
        seen.add(key)
        x = {"n": name, "c": c, "y": kana.yomi(re.sub(r"[（(].*", "", name)).strip()}
        if d:
            x["d"] = "。".join(s.rstrip("。") for s in d).replace("最終ページ", "分別辞典の最終ページ")
        out.append(x)
    if bad:
        for b in bad:
            print("  ！ 区分が読めない：", b)
        raise SystemExit(f"区分が読めない品目が {len(bad)} あります")
    if len(out) < 1000:
        raise SystemExit(f"品目が {len(out)} しか読めません（PDF の形がかわった？）")
    rows = [json.dumps(x, ensure_ascii=False, separators=(",", ":")) for x in out]
    (m.data_dir / "items.js").write_text(
        f"// 東京都 八王子市（13201）の品目検索のデータ（{len(out)}件）\n"
        "// 八王子市の「分別辞典」（PDF、令和8年4月1日時点）。tools/munis/13_tokyo/13201_hachioji/make_items.py で作る\n"
        "// 1行に1品目：{n:品名, c:区分, y:読み, d:注意}\n"
        'gomiData("13201", "items", /*ITEMS-START*/[\n' + ",\n".join(rows) + "\n]/*ITEMS-END*/);\n",
        encoding="utf-8", newline="\n")
    print(f"品目 {len(out)}件 → {m.data_dir / 'items.js'}")
    print("  区分ごと：", dict(collections.Counter(x["c"] for x in out)))


if __name__ == "__main__":
    main()
