"""東京都 町田市（13209）：市の「50音別分別ガイド」（PDF、2026年10月版）から品目検索のデータ（items.js）を作る。

使い方（gomi フォルダで）：python gomiappV3.1/tools/munis/13_tokyo/13209_machida/make_items.py
元：元データ/13_東京都/13209_町田市/分別の冊子/50音別分別ガイド_202610.pdf
  https://www.city.machida.tokyo.jp/kurashi/kankyo/gomi/gominowakekata/gomi-bunbetsu/50.html の「50音別分別ガイド」
町田市には品目のオープンデータがない（東京都オープンデータカタログ。2026-11-27）。
表は「品名・分別区分・備考」。1つの品名に区分が2つ以上ある（例：IHクッキングヒーター → 拠点回収／燃やせないごみ）。
  ・分別区分の文字の行を1つの品目にし、品名は、その行にいちばん近い（上下20以内の）品名の行。
  ・備考は、右の列の文字の行を、いちばん近い分別区分の行に付ける。「小型家電回収ボックスの詳細はこちら」などのリンクの文字はのぞく。
  ・有害ごみは、蛍光管・水銀体温計・ライターの日と、電池・充電式小型家電の日がちがうので、品名で分ける（KEIKO）。
"""
import json
import re
import sys
import unicodedata
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "lib"))
import kana  # noqa: E402
import munis as M  # noqa: E402

CATS = {"燃やせるごみ": "燃やせる", "燃やせないごみ": "燃やせない", "容器包装プラスチック": "プラ", "古紙・古着": "古紙",
        "ビン・カン": "ビンカン", "ペットボトル": "ペット", "剪定枝": "剪定枝", "粗大ごみ": "粗大", "拠点回収": "拠点",
        "収集しません": "×"}
KEIKO = ("蛍光", "水銀", "ライター")      # 有害ごみのうち「蛍光管・水銀体温計・ライター」の日のもの
KADEN = ("エアコン", "テレビ", "冷蔵庫", "冷凍庫", "洗濯機", "衣類乾燥機")
SKIP_NOTE = ("詳細はこちら", "クリックすると", "青文字下線部")
X_NAME, X_CAT, X_NOTE = (40, 250), (250, 322), (322, 560)


def nfkc(s):
    return unicodedata.normalize("NFKC", s).replace("～", "〜").strip()


def lines_of(page):
    out = []
    for b in page.get_text("dict")["blocks"]:
        for l in b.get("lines", []):
            t = "".join(s["text"] for s in l["spans"]).strip()
            if t:
                x0, y0, x1, y1 = l["bbox"]
                out.append(((x0 + x1) / 2, (y0 + y1) / 2, x0, t))
    # 同じ行が2回書いてあるもの（リンクの文字）は1つに
    seen, uniq = set(), []
    for ln in out:
        k = (round(ln[0]), round(ln[1]), ln[3])
        if k not in seen:
            seen.add(k)
            uniq.append(ln)
    return uniq


def main():
    import pymupdf
    m = M.munis(["13209"])[0]
    src = m.src_dir / "分別の冊子" / "50音別分別ガイド_202610.pdf"
    items, unknown, seen, nrow = [], [], set(), 0
    for page in pymupdf.open(src):
        # 品目の区切り：品名の列から右はしまで引いた横線（区分の列から引いた線は、1つの品目の中の区分の区切り）
        cuts = sorted({round(dr["rect"].y0, 1) for dr in page.get_drawings()
                       if dr.get("fill") == (0.0, 0.0, 0.0) and dr["rect"].x0 < 60 and dr["rect"].x1 > 318 and dr["rect"].height < 2})     # 線が2本に分かれているページもある
        ls = [ln for ln in lines_of(page) if cuts and cuts[0] < ln[1] < cuts[-1]]       # 表の中だけ
        def item_of(y):
            k = sum(1 for c in cuts if c < y)
            return k if 0 < k < len(cuts) else None
        names = {}
        for ln in sorted(ls, key=lambda ln: ln[1]):
            if X_NAME[0] < ln[2] < X_NAME[1] and ln[0] < X_NAME[1] and not re.fullmatch(r"[あ-ん]|品\s*名", ln[3]) and item_of(ln[1]):
                names[item_of(ln[1])] = (names[item_of(ln[1])] + (" " if ln[3].startswith("※") else "") if item_of(ln[1]) in names else "") + ln[3]       # 2行の品名はつなぐ
        cats = [ln for ln in ls if X_CAT[0] < ln[2] < 280 and ln[3] not in ("分別区分",)]      # 区分の文字は列の左はしから（備考がつながる行もある）
        notes = [ln for ln in ls if ln[2] >= X_NOTE[0] - 2 and not any(k in ln[3] for k in SKIP_NOTE) and ln[3] != "備　　　考"]
        rows = []
        for cx, cy, _, ct in cats:
            k = nfkc(ct)
            base = next((c for c in sorted(CATS, key=len, reverse=True) if k.startswith(c)), "有害ごみ" if k == "有害ごみ" else None)
            name = names.get(item_of(cy))
            if not base or not name:
                unknown.append(f"{page.number + 1}ページ y={cy:.0f}：{ct}（品名 {name}）")
                continue
            rows.append({"cy": cy, "name": nfkc(name), "kubun": base, "extra": k[len(base):].strip(), "note": []})
        used = {r["name"] for r in rows}
        for n in names.values():
            if nfkc(n) not in used:
                unknown.append(f"{page.number + 1}ページ：品名「{n}」に区分がない")
        for nx, ny, _, nt in notes:
            if rows:
                r = min(rows, key=lambda r: abs(r["cy"] - ny))
                if abs(r["cy"] - ny) < 12:
                    r["note"].append(nfkc(nt))
        for r in rows:
            nrow += 1
            name = r["name"].replace("(", "（").replace(")", "）")
            if r["kubun"] == "有害ごみ":
                c = "蛍光管" if any(k in name for k in KEIKO) else "電池"
            else:
                c = CATS[r["kubun"]]
            if c == "×" and any(k in name for k in KADEN):
                c = "家電"
            dup = (name, c) in seen
            seen.add((name, c))
            # 備考の行をつなぐ：文の終わり（「ください」「ます」など）のあとには「。」を入れ、文のとちゅうで折り返した行はそのままつなぐ
            parts = ([r["extra"]] if r["extra"] else []) + r["note"]
            note = "".join(x + "。" if x.endswith(("ください", "ます", "です", "もの", "]", "）", ")")) and i < len(parts) - 1 else x
                           for i, x in enumerate(parts))
            d = [note] if note else []
            if c in ("電池", "蛍光管"):
                d.insert(0, "有害ごみ（" + ("蛍光管・水銀体温計・ライター" if c == "蛍光管" else "電池・充電式小型家電") + "の日）")
            if dup:      # 同じ品名・同じ区分の2行目（大きさなどで注意がちがう）：注意を前の品目につなぐ
                prev = next(x for x in reversed(items) if x["n"] == name and x["c"] == c)
                if d and d[-1] not in prev.get("d", ""):
                    prev["d"] = "。".join(x.rstrip("。") for x in [prev.get("d", "")] + d[-1:] if x)
                continue
            it = {"n": name, "c": c, "y": kana.yomi(re.sub(r"\s*[（※].*", "", name)).strip()}
            if d:
                it["d"] = "。".join(x.rstrip("。") for x in d)
            items.append(it)
    if unknown:
        raise SystemExit("読めない行があります：\n  " + "\n  ".join(unknown[:30]))
    rows = [json.dumps(x, ensure_ascii=False, separators=(",", ":")) for x in items]
    (m.data_dir / "items.js").write_text(
        f"// 東京都 町田市（13209）の品目検索のデータ（{len(items)}件）\n"
        "// 町田市の「50音別分別ガイド」（PDF、2026年10月版）の表。tools/munis/13_tokyo/13209_machida/make_items.py で作る\n"
        "// 1行に1品目：{n:品名, c:区分, y:読み, d:注意}\n"
        'gomiData("13209", "items", /*ITEMS-START*/[\n' + ",\n".join(rows) + "\n]/*ITEMS-END*/);\n",
        encoding="utf-8", newline="\n")
    print(f"品目 {len(items)}件（表の行 {nrow}）→ {m.data_dir / 'items.js'}")


if __name__ == "__main__":
    main()
