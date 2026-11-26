"""東京都 足立区（13121）：区の「これは何ごみ？（粗大ごみ料金表）50音順」（PDF）から品目検索のデータ（items.js）を作る。

使い方（gomi フォルダで）：python gomiappV3.1/tools/munis/13_tokyo/13121_adachi/make_items.py [--download]
元：元データ/13_東京都/13121_足立区/分別の冊子/gomihp.pdf（12ページ。令和8年3月作成。冊子「資源とごみの分け方・出し方」の22〜33ページと同じ表）
  https://www.city.adachi.tokyo.jp/documents/46173/gomihp.pdf
足立区には品目のオープンデータがない（東京都オープンデータカタログに足立区の「ごみ分別」はなかった。2026-11-26）。
表の形：1行に1品目。列は「プラスチック・燃やすごみ・燃やさないごみ・資源・粗大ごみ」の●（列ごとに色がちがう）、粗大ごみ手数料、品目、出し方と注意点。
  ・全部の列が「－」の品目は「区では収集できない」（注意に「家電リサイクル法」とあれば「家電」）。
  ・品目名が2行のもの（「植木鉢・／プランター」）や、品目名の右に（素焼き・陶器製）のような分け方があるものは、つなげて1つの名前にする。
  ・●が2つ以上の品目（材質に応じて出す）は、表の左の列の区分にして、注意に「（○○・○○）」と書く。
"""
import itertools
import json
import re
import sys
import unicodedata
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "lib"))
import kana  # noqa: E402
import munis as M  # noqa: E402

URL = "https://www.city.adachi.tokyo.jp/documents/46173/gomihp.pdf"
PDF = "gomihp.pdf"
# ●・－ の色 → アプリの区分（表の左からの順）
MARK = {"67328f": "プラ", "dd5432": "燃やす", "0566ab": "燃やさない", "1c8d3b": "資源", "595757": "粗大"}
LONG = {"プラ": "プラスチック", "燃やす": "燃やすごみ", "燃やさない": "燃やさないごみ", "資源": "資源", "粗大": "粗大ごみ"}


def nfkc(s):
    return unicodedata.normalize("NFKC", s).replace("　", " ").strip()


def spans(page):
    out = []
    for b in page.get_text("dict")["blocks"]:
        for ln in b.get("lines", []):
            for s in ln["spans"]:
                if s["text"].strip():
                    x0, y0, x1, y1 = s["bbox"]
                    out.append({"x0": x0, "x1": x1, "y0": y0, "y1": y1, "yc": (y0 + y1) / 2,
                                "t": s["text"], "c": "%06x" % s["color"]})
    return out


def read_page(page):
    ss = spans(page)
    marks = [s for s in ss if s["c"] in MARK and s["t"].strip() in ("●", "－")]
    # 行：●・－ の高さでまとめる
    rows = []
    for m in sorted(marks, key=lambda s: s["yc"]):
        if rows and abs(rows[-1]["yc"] - m["yc"]) < 4:
            rows[-1]["m"].append(m)
        else:
            rows.append({"yc": m["yc"], "m": [m]})
    # 同じ行でとなりあう文字（「 （」「アルミサッシ、ガラス戸を除く」「）」）は1つにする
    raw = []
    for s in sorted((s for s in ss if s["c"] == "221815" and 70 <= s["x0"] < 225 and s["yc"] > 150), key=lambda s: (round(s["y0"]), s["x0"])):
        whole = nfkc(s["t"]).startswith("(") and nfkc(s["t"]).endswith(")")     # 「テレビ台」の右の「（幅1ｍ以上…）」は分け方なのでつなげない
        if raw and abs(raw[-1]["y0"] - s["y0"]) < 1.5 and -1 <= s["x0"] - raw[-1]["x1"] < 3 and not whole:
            raw[-1] = dict(raw[-1], t=raw[-1]["t"] + s["t"], x1=s["x1"])
        else:
            raw.append(s)
    names = []
    for s in raw:
        if True:
            m = re.fullmatch(r"(\S.*?)[　 ]+(（[^（]*）)\s*", s["t"])
            if m:       # 「（家庭使用）　（高さ60cm以上）」「びん （マニキュアのびん）」：品目名と分け方が1つになっている
                names += [dict(s, t=m[1]), dict(s, t=m[2], x0=129)]
            else:
                names.append(s)
    # 分け方（「（高さ70㎝未満）」）は、品目名の右か、全角の空白で右に寄せて書いてある
    # （「鉄板類（アングル、アルミ板、…」のように、品目名のつづきが右にあることもある。分け方は「（…）」で閉じている）
    is_var = [nfkc(s["t"]).startswith("(") and (s["t"][:1].isspace() or (s["x0"] >= 90 and nfkc(s["t"]).endswith(")")))
              for s in names]
    base = sorted((s for s, v in zip(names, is_var) if not v), key=lambda s: s["y0"])
    var = [s for s, v in zip(names, is_var) if v]
    # 品目名のかたまり（「植木鉢・」＋「プランター」、「オーディオ機器」＋「（カラオケ/スピーカー除く）」）
    blocks = []
    for s in base:
        t = nfkc(s["t"])
        open_paren = blocks and blocks[-1]["t"].count("(") > blocks[-1]["t"].count(")")
        if blocks and (blocks[-1]["t"].endswith("・") or t.startswith("(") or open_paren) and s["y0"] - blocks[-1]["y1"] < 6:
            blocks[-1]["t"] += t
            blocks[-1]["y1"] = s["y1"]
        else:
            blocks.append({"t": t, "y0": s["y0"], "y1": s["y1"]})
    notes = [s for s in ss if s["c"] == "221815" and s["x0"] >= 345 and s["yc"] > 150]
    fees = [s for s in ss if s["c"] == "221815" and 310 <= s["x0"] < 345 and s["yc"] > 150]
    for r in rows:
        r["v"] = [nfkc(s["t"]) for s in var if abs(s["yc"] - r["yc"]) < 7]
    used = set()
    for r in rows:              # 分け方のない行：いちばん近い品目名
        if not r["v"]:
            i = min(range(len(blocks)), key=lambda i: max(blocks[i]["y0"] - r["yc"], 0, r["yc"] - blocks[i]["y1"]))
            if max(blocks[i]["y0"] - r["yc"], 0, r["yc"] - blocks[i]["y1"]) > 10:
                raise ValueError(f"{page.number + 1}ページ：y={r['yc']:.0f} の行の品目名が見つかりません")
            r["b"] = i
            used.add(i)
    # 分け方のある行：つづいた行のまとまりごとに、その高さにある品目名（縦のまん中に書いてある）に分ける
    k = 0
    while k < len(rows):
        if not rows[k]["v"]:
            k += 1
            continue
        run = [rows[k]]
        while k + len(run) < len(rows) and rows[k + len(run)]["v"]:
            run.append(rows[k + len(run)])
        k += len(run)
        lo, hi = run[0]["yc"] - 12, run[-1]["yc"] + 12
        bs = [i for i in range(len(blocks)) if i not in used and lo <= (blocks[i]["y0"] + blocks[i]["y1"]) / 2 <= hi]
        if not bs or len(bs) > len(run):
            raise ValueError(f"{page.number + 1}ページ：y={run[0]['yc']:.0f}〜 の分け方の行の品目名がわかりません（{[round(r['yc']) for r in run]} {[(blocks[i]['t'], round(blocks[i]['y0'])) for i in bs]}）")
        best = None
        for cut in itertools.combinations(range(1, len(run)), len(bs) - 1):
            parts = [run[a:b] for a, b in zip((0,) + cut, cut + (len(run),))]
            cost = sum(abs(sum(r["yc"] for r in p) / len(p) - (blocks[i]["y0"] + blocks[i]["y1"]) / 2) for p, i in zip(parts, bs))
            if best is None or cost < best[0]:
                best = (cost, parts)
        for p, i in zip(best[1], bs):
            for r in p:
                r["b"] = i
    items = []
    for r in rows:
        y = r["yc"]
        name = blocks[r["b"]]["t"] + "".join(r["v"])
        name = re.sub(r"\s+", "", name)
        cats = [MARK[m["c"]] for m in sorted(r["m"], key=lambda m: m["x0"]) if m["t"].strip() == "●"]
        mine = sorted((s for s in notes if abs(s["yc"] - y) < 11 and min(rows, key=lambda rr: abs(rr["yc"] - s["yc"])) is r),
                      key=lambda s: s["yc"])
        lines = []          # 同じ高さ（「※」と、そのあとの小さい字）は1行にする
        for s in mine:
            if lines and abs(lines[-1][0]["yc"] - s["yc"]) < 3:
                lines[-1].append(s)
            else:
                lines.append([s])
        note = "／".join("".join(nfkc(s["t"]) for s in sorted(ln, key=lambda s: s["x0"])) for ln in lines)
        fee = [nfkc(s["t"]) for s in fees if abs(s["yc"] - y) < 6]
        items.append({"name": name, "cats": cats, "note": note, "fee": fee[0] if fee else ""})
    return items


def main():
    import pymupdf
    m = M.munis(["13121"])[0]
    src = m.src_dir / "分別の冊子" / PDF
    if "--download" in sys.argv:
        src.write_bytes(urllib.request.urlopen(urllib.request.Request(URL, headers={"User-Agent": "Mozilla/5.0"}), timeout=60).read())
    doc = pymupdf.open(src)
    out, seen, multi = [], set(), []
    for page in doc:
        rows = read_page(page)
        if len(rows) < 20:
            raise SystemExit(f"{page.number + 1}ページの品目が {len(rows)} しか読めません（PDF の形がかわった？）")
        for it in rows:
            note = it["note"]
            if not it["cats"]:
                c = "家電" if "家電リサイクル法" in note else "×"
            else:
                c = it["cats"][0]
                if len(it["cats"]) > 1:
                    multi.append(it["name"])
                    note = "（" + "・".join(LONG[x] for x in it["cats"]) + "）" + (" " + note if note else "")
            if c == "粗大" and it["fee"] and it["fee"] != "－":
                note = f"粗大ごみ手数料 {it['fee']}円" + ("／" + note if note else "")
            if (it["name"], c) in seen:
                continue
            seen.add((it["name"], c))
            x = {"n": it["name"], "c": c, "y": kana.yomi(it["name"])}
            if note:
                x["d"] = note
            out.append(x)
    rows = [json.dumps(x, ensure_ascii=False, separators=(",", ":")) for x in out]
    (m.data_dir / "items.js").write_text(
        f"// 東京都 足立区（13121）の品目検索のデータ（{len(out)}件）\n"
        "// 足立区の「これは何ごみ？（粗大ごみ料金表）50音順」（PDF）の表。tools/munis/13_tokyo/13121_adachi/make_items.py で作る\n"
        "// 1行に1品目：{n:品名, c:区分, y:読み, d:注意}\n"
        'gomiData("13121", "items", /*ITEMS-START*/[\n' + ",\n".join(rows) + "\n]/*ITEMS-END*/);\n",
        encoding="utf-8", newline="\n")
    print(f"品目 {len(out)}件（●が2つ以上 {len(multi)}件）→ {m.data_dir / 'items.js'}")


if __name__ == "__main__":
    main()
