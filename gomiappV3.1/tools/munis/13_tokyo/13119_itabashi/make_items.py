"""東京都 板橋区（13119）：区の「ごみの分別品目一覧（50音順）」（PDF、令和8年4月）から品目検索のデータ（items.js）を作る。

使い方（gomi フォルダで）：python gomiappV3.1/tools/munis/13_tokyo/13119_itabashi/make_items.py [--download]
元：元データ/13_東京都/13119_板橋区/分別の冊子/r8.1.pdf（27ページ）
  ページ：https://www.city.itabashi.tokyo.jp/tetsuduki/gomi/bunbetsu/1001879.html
区の品目のオープンデータ（東京都オープンデータカタログ「ゴミの分別方法一覧」「ゴミ分別」）もあるが、
令和6年4月のプラスチック分別の前のもの（プラスチックが「可燃」のまま）なので使わない（README）。
表の形：品名（まとめたセル）・用途 素材 形状・資源・可燃・不燃・粗大・料金・拠点・不可・出し方と注意点。
  ・横線が表の幅いっぱい（x 51〜547）なら品名の区切り、品名の列の右から（x 124〜）なら同じ品名の中の行の区切り。
  ・文字は1文字ずつの位置で列に分ける（50音の「あ」と品名が1つにつながって出てくるため）。
  ・● はその区分。● が2つ以上のときは左の区分にして、注意に「（資源・可燃ごみ）」と書く。＊ は「汚れたものなどは」の区分（注意に書いてある）。
  ・■（専門業者へ）は「区では収集しない」。注意に「家電リサイクル」とあるものは「家電」。
"""
import json
import re
import sys
import unicodedata
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "lib"))
import kana  # noqa: E402
import munis as M  # noqa: E402

URL = "https://www.city.itabashi.tokyo.jp/_res/projects/default_project/_page_/001/001/879/r8.1.pdf"
PDF = "r8.1.pdf"
# 列（x の範囲）
COLS = [("kana", 50, 63), ("name", 63, 124), ("sub", 124, 214), ("資源", 214, 230), ("可燃", 230, 246), ("不燃", 246, 262),
        ("粗大", 262, 278), ("料金", 278, 302), ("拠点", 302, 318), ("×", 318, 334), ("note", 334, 560)]
MARKS = ["資源", "可燃", "不燃", "粗大", "拠点", "×"]
LONG = {"資源": "資源", "可燃": "可燃ごみ", "不燃": "不燃ごみ", "粗大": "粗大ごみ", "拠点": "拠点回収", "×": "区では収集しない"}


def nfkc(s):
    return unicodedata.normalize("NFKC", s).replace("㎝", "cm").strip()


def hlines(page):
    """横線の y：(品名の区切り, 行の区切り, 出し方の列の区切り)。出し方の列は、まとめたセルのことがある"""
    full, sub, note = set(), set(), set()
    for dr in page.get_drawings():
        for it in dr["items"]:
            if it[0] == "l" and abs(it[1].y - it[2].y) < 0.5:
                x0, x1, y = min(it[1].x, it[2].x), max(it[1].x, it[2].x), it[1].y
            elif it[0] == "re" and it[1].height < 1.5:
                x0, x1, y = it[1].x0, it[1].x1, it[1].y0
            else:
                continue
            if x1 < 300:
                continue
            if x0 < 70:              # 品名の区切り（出し方の列だけ、まとめていることがある）
                full.add(round(y, 1))
            elif 115 < x0 < 130:     # 同じ品名の中の行の区切り
                sub.add(round(y, 1))
            else:
                continue
            if x1 > 500:
                note.add(round(y, 1))
    return sorted(full), sorted(full | sub), sorted(note)


def chars(page):
    """1文字ずつ（x中心, y中心, 文字, 上の y, 列）。続いた文字のまとまりは、はじめの文字の列にする（長い品名が右の列にはみ出すため）"""
    out = []
    for b in page.get_text("rawdict")["blocks"]:
        for ln in b.get("lines", []):
            for sp in ln["spans"]:
                run, last = None, None
                for ch in sp["chars"]:
                    x0, y0, x1, y1 = ch["bbox"]
                    if last is None or x0 - last > 2.5:
                        run = col((x0 + x1) / 2)
                    last = x1
                    c = col((x0 + x1) / 2)
                    if run == "kana" and c != "kana":      # 「あアイロン台」：50音のあとは品名
                        run = c
                    out.append(((x0 + x1) / 2, (y0 + y1) / 2, ch["c"], y0, run if run in ("name", "note") and c in ("sub", "note") else c))
    return out


def col(x):
    return next((n for n, a, b in COLS if a <= x < b), None)


def text(cs):
    """1つのマスの文字 → 行ごとの文字列"""
    lines = []
    for c in sorted(cs, key=lambda c: (round(c[3]), c[0])):
        if lines and abs(lines[-1][-1][3] - c[3]) < 3:
            lines[-1].append(c)
        else:
            lines.append([c])
    return [nfkc("".join(c[2] for c in sorted(L, key=lambda c: c[0]))) for L in lines]


def join(lines):
    """折り返した行をつなぐ（英数字どうしのときだけ空白を入れる）"""
    s = ""
    for t in lines:
        s += (" " if s and s[-1].isascii() and s[-1].isalnum() and t[:1].isascii() and t[:1].isalnum() else "") + t
    return s.replace(" （", "（").replace("( ", "(")


def read_page(page):
    full, allines, nlines = hlines(page)
    cs = [c for c in chars(page) if c[2].strip()]
    rows = []
    for i in range(len(allines) - 1):
        y0, y1 = allines[i], allines[i + 1]
        if y1 - y0 < 5 or y0 < full[0] - 0.5:
            continue
        b0 = max(f for f in full if f <= y0 + 0.5)            # この行の品名のまとまり
        b1 = min((f for f in full if f >= y1 - 0.5), default=y1)
        cell = lambda name, a, b: [c for c in cs if c[4] == name and a <= c[1] < b]
        name = join(text(cell("name", b0, b1)))
        if not name:
            continue
        n0 = max(f for f in nlines if f <= y0 + 0.5)            # 出し方のマス（いくつかの行でまとめていることがある）
        n1 = min((f for f in nlines if f >= y1 - 0.5), default=y1)
        r = {"name": name, "sub": join(text(cell("sub", y0, y1))), "note": join(text(cell("note", n0, n1))),
             "fee": "".join(text(cell("料金", y0, y1))), "y": y0}
        r["main"] = [m for m in MARKS if any(c[2] in "●■" for c in cell(m, y0, y1))]
        r["star"] = [m for m in MARKS if any(c[2] == "＊" for c in cell(m, y0, y1))]
        rows.append(r)
    return rows


def main():
    import pymupdf
    m = M.munis(["13119"])[0]
    src = m.src_dir / "分別の冊子" / PDF
    if "--download" in sys.argv:
        src.write_bytes(urllib.request.urlopen(urllib.request.Request(URL, headers={"User-Agent": "Mozilla/5.0"}), timeout=60).read())
    doc = pymupdf.open(src)
    out, seen, bad, multi = [], set(), [], 0
    for page in doc:
        if page.number == 0:       # 表紙（分け方の説明）
            continue
        rows = read_page(page)
        if len(rows) < 15:
            raise SystemExit(f"{page.number + 1}ページの品目が {len(rows)} しか読めません（PDF の形がかわった？）")
        for r in rows:
            sub = r["sub"]
            if re.fullmatch(r"\([^()]*\)", sub):          # 「(家庭使用)」のように、もとからかっこ付き
                sub = sub[1:-1]
            name = r["name"] + (f"（{sub}）" if sub else "")
            name = name.replace("(", "（").replace(")", "）")
            note = r["note"]
            if not r["main"] and r["star"]:      # ●がなく＊だけ（湯たんぽ「その他」）
                r["main"] = r["star"]
            if not r["main"]:
                bad.append((page.number + 1, name))
                continue
            c = r["main"][0]
            if len(r["main"]) > 1:
                multi += 1
                note = "（" + "・".join(LONG[x] for x in r["main"]) + "）" + (" " + note if note else "")
            if c == "×" and "家電リサイクル" in note:
                c = "家電"
            if c == "粗大" and re.fullmatch(r"\d+", r["fee"]):
                note = f"粗大ごみ手数料 {r['fee']}円" + ("／" + note if note else "")
            if (name, c) in seen:
                continue
            seen.add((name, c))
            x = {"n": name, "c": c, "y": kana.yomi(re.sub(r"（.*", "", name)).strip()}
            if note:
                x["d"] = note
            out.append(x)
    if bad:
        for b in bad:
            print("  ！ 区分の●がない：", b)
        raise SystemExit(f"区分が読めない品目が {len(bad)} あります")
    rows = [json.dumps(x, ensure_ascii=False, separators=(",", ":")) for x in out]
    (m.data_dir / "items.js").write_text(
        f"// 東京都 板橋区（13119）の品目検索のデータ（{len(out)}件）\n"
        "// 板橋区の「ごみの分別品目一覧（50音順）」（PDF、令和8年4月）。tools/munis/13_tokyo/13119_itabashi/make_items.py で作る\n"
        "// 1行に1品目：{n:品名, c:区分, y:読み, d:注意}\n"
        'gomiData("13119", "items", /*ITEMS-START*/[\n' + ",\n".join(rows) + "\n]/*ITEMS-END*/);\n",
        encoding="utf-8", newline="\n")
    print(f"品目 {len(out)}件（●が2つ以上 {multi}件）→ {m.data_dir / 'items.js'}")


if __name__ == "__main__":
    main()
