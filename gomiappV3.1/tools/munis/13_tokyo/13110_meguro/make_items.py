"""東京都 目黒区（13110）：区の「資源・ごみの分別品目一覧表（50音順）」（令和8年4月改訂、PDF）から品目検索のデータ（items.js）を作る。

使い方（gomi フォルダで）：python gomiappV3.1/tools/munis/13_tokyo/13110_meguro/make_items.py
元：元データ/13_東京都/13110_目黒区/分別の冊子/分別品目一覧_50音順_令和8年4月.pdf
  https://www.city.meguro.tokyo.jp/documents/4395/r804_50onichiran.pdf （ページ：資源・ごみに関する印刷物PDFデータ）
目黒区には品目のオープンデータがない（東京都オープンデータカタログ。2026-11-26）。

表（Excel で作った PDF。文字あり）の読み方：
  ・行：横の罫線で分ける。左から長い線（x≦82）は品名の区切り、品名の列の中ほどから（x≒141）の線は、同じ品名の中の細かい区切り。
    品名のセルが細かく分かれているとき（縦の線 x≒140 がある）は「品名（細かい名前）」にする（例：「いす（パイプ椅子）」）。
  ・種別の列：資源（「プラ」「ペット」「びん」「缶」の文字）・可燃・不燃・水銀・古紙・粗大・不可。
    ●＝その種別、※＝「出し方と注意点」を見て決める種別、■＝区では収集できない。
  ・区分：資源の文字と●の種別すべて（2つ以上なら、同じ品名を区分ごとに並べる）。●がない行は※の種別。
"""
import json
import re
import sys
import unicodedata
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "lib"))
import kana  # noqa: E402
import munis as M  # noqa: E402

PDF = "分別品目一覧_50音順_令和8年4月.pdf"
COLS = [("資源", 278, 295), ("可燃", 295, 312), ("不燃", 312, 329), ("水銀", 329, 346), ("古紙", 346, 363),
        ("粗大", 363, 380), ("不可", 380, 397)]
NOTE_X = 397
APP = {"資源": "資源", "可燃": "可燃", "不燃": "不燃", "水銀": "水銀", "古紙": "古紙", "粗大": "粗大", "不可": "×"}
# 種別の印がない行（区の表のとおり。決まり A1）
NO_MARK = {"ノートパソコン": "×",                          # 出し方：メーカー・認定事業者などに回収を頼む（区では収集しない）
           "ビーズクッションの中身(マイクロビーズ)": None}   # 出し方：清掃事務所に問い合わせ → 区分を決められないので入れない
RES = {"プラ": "プラスチック", "ペット": "ペットボトル", "びん": "びん", "缶": "缶"}


def nfkc(s):
    return unicodedata.normalize("NFKC", s).replace("　", " ").strip()


def chars(page):
    out = []
    for b in page.get_text("rawdict")["blocks"]:
        for ln in b.get("lines", []):
            for sp in ln["spans"]:
                for c in sp["chars"]:
                    x0, y0, x1, y1 = c["bbox"]
                    if c["c"].strip():
                        out.append(((x0 + x1) / 2, (y0 + y1) / 2, c["c"], x0, y1))
    return out


def text_of(cs):
    """文字 → 行ごとにつないだ文"""
    lines = []
    for c in sorted(cs, key=lambda c: (round(c[4]), c[3])):
        if lines and abs(lines[-1][0] - c[4]) < 3:
            lines[-1][1].append(c)
        else:
            lines.append([c[4], [c]])
    return "".join("".join(c[2] for c in sorted(ln, key=lambda c: c[3])) for _, ln in lines)


def lines_of(page):
    hs, vs = [], []
    for dr in page.get_drawings():
        for it in dr["items"]:
            if it[0] == "l":
                a, b = it[1], it[2]
                if abs(a.y - b.y) < 0.5:
                    hs.append((a.y, min(a.x, b.x), max(a.x, b.x)))
                elif abs(a.x - b.x) < 0.5:
                    vs.append((a.x, min(a.y, b.y), max(a.y, b.y)))
            elif it[0] == "re":
                r = it[1]
                if r.height < 1.5:
                    hs.append((r.y0, r.x0, r.x1))
                elif r.width < 1.5:
                    vs.append((r.x0, r.y0, r.y1))
    return hs, vs


def uniq(ys):
    out = []
    for y in sorted(ys):
        if not out or y - out[-1] > 2:
            out.append(y)
    return out


def read(pdf):
    import pymupdf
    rows, problems = [], []
    for pno, page in enumerate(pymupdf.open(pdf)):
        t = page.get_text()
        if "出し方と注意点" not in t or "品目一覧" not in t:
            continue
        hs, vs = lines_of(page)
        big = uniq(y for y, x0, x1 in hs if x0 < 90 and x1 > 780)           # 品名の区切り
        small = uniq(y for y, x0, x1 in hs if x0 < 150 and x1 > 390)       # 細かい区切りも入れた行の区切り（種別の列まで）
        nsep = uniq(y for y, x0, x1 in hs if x0 < 400 and x1 > 780)       # 出し方の列の区切り（出し方は、細かい行をまとめたセルのことがある）
        cs = chars(page)
        # 表の見出し（「品 名」「資 源」…）の下から
        top = max((c[4] for c in cs if c[2] in "資可不水古粗" and 80 < c[1] < 112 and 278 < c[0] < 397), default=0)
        big = [y for y in big if y >= top - 2]
        small = [y for y in small if y >= top - 2]
        nsep = [y for y in nsep if y >= top - 2]
        for a, b in zip(big, big[1:]):
            inner = [y for y in small if a - 1 < y < b + 1]
            split = any(abs(x - 140.5) < 2 and y0 < (a + b) / 2 < y1 for x, y0, y1 in vs)
            main = text_of([c for c in cs if 82 < c[0] < (140 if split else 278) and a < c[1] < b])
            for ra, rb in zip(inner, inner[1:]):
                rc = [c for c in cs if ra < c[1] < rb]
                sub = text_of([c for c in rc if 141 < c[0] < 278]) if split else ""
                marks = {k: text_of([c for c in rc if x0 < c[0] < x1]) for k, x0, x1 in COLS}
                na = max(y for y in nsep if y < ra + 1)
                nb = min(y for y in nsep if y > rb - 1)
                note = text_of([c for c in cs if c[0] > NOTE_X and na < c[1] < nb])
                if not main and not sub:
                    if any(marks.values()) or note:
                        problems.append(f"p.{pno + 1} 品名のない行：{marks} {note}")
                    continue
                rows.append({"page": pno + 1, "main": nfkc(main), "sub": nfkc(sub), "marks": marks, "note": nfkc(note)})
    return rows, problems


def yomi(s):
    """品名の読み。「IC(アイシー)レコーダー」は かっこの中の読みを使い、ほかのかっこ（説明）はのぞく"""
    s = re.sub(r"[A-Za-z0-9]+[（(]([ぁ-んァ-ヶー]+)[）)]", lambda m: m.group(1), s)
    s = re.sub(r"[（(][^）)]*[）)]|【[^】]*】|※.*", "", s)
    return YOMI_FIX.get(s) or kana.yomi(s).strip()


YOMI_FIX = {"傘立て": "かさたて"}      # pykakasi の読みちがい


def main():
    m = M.munis(["13110"])[0]
    pdf = m.year_dir(2026).parent / "分別の冊子" / PDF
    rows, problems = read(pdf)
    items, seen = [], set()
    for r in rows:
        mk = r["marks"]
        res = mk.pop("資源")
        cats = []
        if res:
            if res not in RES:
                problems.append(f"p.{r['page']} {r['main']} {r['sub']}：資源の文字が読めない（{res}）")
                continue
            cats.append(("資源", RES[res]))
        dots = [k for k, v in mk.items() if "●" in v or "■" in v]
        notes = [k for k, v in mk.items() if "※" in v]
        bad = [v for v in mk.values() if v and set(v) - set("●■※.")]     # 「.」は表の中のよごれ（カッターの水銀の列）
        if bad:
            problems.append(f"p.{r['page']} {r['main']} {r['sub']}：種別の印が読めない（{bad}）")
        cats += [(k, "") for k in dots]
        if not cats:
            cats = [(k, "") for k in notes]
        if not cats and r["main"] in NO_MARK:
            if NO_MARK[r["main"]] is None:
                continue
            cats = [({"×": "不可"}[NO_MARK[r["main"]]], "")]
        if not cats:
            problems.append(f"p.{r['page']} {r['main']} {r['sub']}：種別の印がない")
            continue
        name = f"{r['main']}（{r['sub']}）" if r["sub"] else r["main"]
        name = name.replace("（※", "（").replace("※", " ").replace("(", "（").replace(")", "）")
        for k, sub in cats:
            c = APP[k]
            if (name, c) in seen:
                continue
            seen.add((name, c))
            d = []
            if sub:
                d.append(f"資源（{sub}）")
            if r["note"]:
                d.append(r["note"].lstrip("■"))
            it = {"n": name, "c": c, "y": yomi(r["main"])}
            if d:
                it["d"] = "。".join(x.rstrip("。") for x in d)
            items.append(it)
    if problems:
        for p in problems:
            print("！", p)
        raise SystemExit(f"読めない行が {len(problems)} あります")
    rows_js = [json.dumps(x, ensure_ascii=False, separators=(",", ":")) for x in items]
    (m.data_dir / "items.js").write_text(
        f"// 東京都 目黒区（13110）の品目検索のデータ（{len(items)}件）\n"
        "// 目黒区「資源・ごみの分別品目一覧表（50音順）」（令和8年4月改訂）。tools/munis/13_tokyo/13110_meguro/make_items.py で作る\n"
        "// 1行に1品目：{n:品名, c:区分, y:読み, d:注意}\n"
        'gomiData("13110", "items", /*ITEMS-START*/[\n' + ",\n".join(rows_js) + "\n]/*ITEMS-END*/);\n",
        encoding="utf-8", newline="\n")
    from collections import Counter
    print(f"品目 {len(items)}件（表の行 {len(rows)}）→ {m.data_dir / 'items.js'}")
    print(Counter(x["c"] for x in items))


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
