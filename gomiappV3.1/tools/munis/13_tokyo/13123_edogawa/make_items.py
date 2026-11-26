"""東京都 江戸川区（13123）：区のページ「資源・ごみの分け方・出し方 品目別一覧表」から品目検索のデータ（items.js）を作る。

使い方（gomi フォルダで）：python gomiappV3.1/tools/munis/13_tokyo/13123_edogawa/make_items.py [--download]
元：元データ/13_東京都/13123_江戸川区/分別の冊子/<a・ka・sa・ta・na・ha・ma・ya・ra>.html（9ページ。表：品名・種別・出し方と注意点）
  https://www.city.edogawa.tokyo.jp/kurashi/gomi_recycle/kategomi/hinmoku/index.html
江戸川区には品目のオープンデータがない（東京都オープンデータカタログに江戸川区の「ごみ分別」はなかった。2026-11-26）。
種別は「燃やすごみ」「燃やさないごみ」「資源」「粗大ごみ」「収集できません」の5つ。
「収集できません」のうち、注意に「家電リサイクル法」とあるものは「家電」にする。
"""
import html as H
import json
import re
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "lib"))
import kana  # noqa: E402
import munis as M  # noqa: E402

PAGES = ["a", "ka", "sa", "ta", "na", "ha", "ma", "ya", "ra"]
URL = "https://www.city.edogawa.tokyo.jp/e025/kurashi/gomi_recycle/kategomi/hinmoku/{}.html"
# 種別 → アプリの区分（city.js の cats）
CATS = {"燃やすごみ": "燃やす", "燃やさないごみ": "燃やさない", "資源": "資源", "粗大ごみ": "粗大", "収集できません": "×"}


def clean(s):
    s = re.sub(r"<br\s*/?>|</p>\s*<p[^>]*>", "／", s)
    s = H.unescape(re.sub(r"<[^>]+>", "", s)).replace("　", " ").replace("\xa0", " ")
    return re.sub(r"\s+", " ", s).strip(" ／")


def main():
    m = M.munis(["13123"])[0]
    src = m.src_dir / "分別の冊子"
    if "--download" in sys.argv:
        for p in PAGES:
            raw = urllib.request.urlopen(urllib.request.Request(URL.format(p), headers={"User-Agent": "Mozilla/5.0"}), timeout=60).read()
            (src / f"{p}.html").write_bytes(raw)
    items, unknown, seen = [], [], set()
    for p in PAGES:
        t = (src / f"{p}.html").read_text(encoding="utf-8-sig")
        n = 0
        for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", t, re.S):
            td = re.findall(r"<td[^>]*>(.*?)</td>", tr, re.S)
            if len(td) < 2:
                continue
            name, kubun, note = clean(td[0]), clean(td[1]), clean(td[2]) if len(td) > 2 else ""
            c = CATS.get(kubun)
            if c == "×" and "家電リサイクル法" in note:
                c = "家電"
            if not c:
                unknown.append(f"{name}（{kubun}）")
                continue
            n += 1
            if (name, c) in seen:
                continue
            seen.add((name, c))
            it = {"n": name, "c": c, "y": kana.yomi(name)}
            if note:
                it["d"] = note
            items.append(it)
        if n < 20:
            raise SystemExit(f"{p}.html の品目が {n} しか読めません（ページの形がかわった？）")
    if unknown:
        raise SystemExit("アプリの区分に当てはまらない種別があります（CATS に足す）：" + "、".join(unknown))
    rows = [json.dumps(x, ensure_ascii=False, separators=(",", ":")) for x in items]
    (m.data_dir / "items.js").write_text(
        f"// 東京都 江戸川区（13123）の品目検索のデータ（{len(items)}件）\n"
        "// 江戸川区のページ「資源・ごみの分け方・出し方 品目別一覧表」の表。tools/munis/13_tokyo/13123_edogawa/make_items.py で作る\n"
        "// 1行に1品目：{n:品名, c:区分, y:読み, d:注意}\n"
        'gomiData("13123", "items", /*ITEMS-START*/[\n' + ",\n".join(rows) + "\n]/*ITEMS-END*/);\n",
        encoding="utf-8", newline="\n")
    print(f"品目 {len(items)}件 → {m.data_dir / 'items.js'}")


if __name__ == "__main__":
    main()
