"""東京都 墨田区（13107）：区のページ「資源とごみの分別一覧表（50音順）」から品目検索のデータ（items.js）を作る。

使い方（gomi フォルダで）：python gomiappV3.1/tools/munis/13_tokyo/13107_sumida/make_items.py （--download で区のページを取り直す）
元：元データ/13_東京都/13107_墨田区/分別の冊子/分別一覧表_50音順.html（表：50音・ものの名前・種類・出し方や注意点。200品目）
  https://www.city.sumida.lg.jp/kurashi/gomi_recycle/kateikei/gomi-50onbunbetu.html
区のオープンデータ「ゴミの分別方法一覧」（東京都オープンデータカタログ t131075d0000000142）は、CSV の URL が見つからない（404。2026-11-27）ので使えなかった。
種類 → アプリの区分：
  資源（古紙）・資源（缶）・資源（びん）・資源（ペットボトル）→「資源」（資源の日）、資源（プラスチック）→「プラ」（プラスチックの日）、
  資源（拠点回収）・資源（イベント回収）・リサイクル協力店の回収ボックス →「拠点」（集積所には出さない）、
  区では収集できない・医療機関に相談・パソコンリサイクル →「×」。
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

URL = "https://www.city.sumida.lg.jp/kurashi/gomi_recycle/kateikei/gomi-50onbunbetu.html"
# 種類 → [(アプリの区分, 注意の頭に書くこと)]
CATS = {
    "燃やすごみ": [("可燃", "")],
    "燃やさないごみ": [("不燃", "")],
    "粗大ごみ": [("粗大", "")],
    "資源（プラスチック）": [("プラ", "")],
    "資源（古紙）": [("資源", "資源（古紙）")],
    "資源（缶）": [("資源", "資源（缶）")],
    "資源（びん）": [("資源", "資源（びん）")],
    "資源（ペットボトル）": [("資源", "資源（ペットボトル）")],
    "資源（拠点回収）": [("拠点", "拠点回収（集積所には出さない）")],
    "資源（イベント回収）": [("拠点", "イベント回収（集積所には出さない）")],
    "資源（拠点回収）または燃やさないごみ": [("拠点", "拠点回収（集積所には出さない）"), ("不燃", "")],
    "電器店などの「リサイクル協力店」にある回収ボックスを利用": [("拠点", "電器店などの「リサイクル協力店」の回収ボックスへ（集積所には出さない）")],
    "処方された医療機関か薬局に相談": [("×", "処方された医療機関か薬局に相談")],
    "区では収集できないので、専門業者に相談": [("×", "区では収集できないので、専門業者に相談")],
    "パソコンリサイクル": [("×", "パソコンリサイクル（メーカーなどの回収。区では収集しない）")],
}


def clean(s):
    s = re.sub(r"<br\s*/?>", "\n", s)
    s = H.unescape(re.sub(r"<[^>]+>", "", s)).replace("　", " ")
    lines = [re.sub(r"\s+", " ", x).strip() for x in s.split("\n")]
    return "".join(x for x in lines if x)


def main():
    m = M.munis(["13107"])[0]
    src = m.year_dir(2026).parent / "分別の冊子" / "分別一覧表_50音順.html"
    if "--download" in sys.argv:
        src.write_bytes(urllib.request.urlopen(urllib.request.Request(URL, headers={"User-Agent": "Mozilla/5.0"}), timeout=60).read())
    t = src.read_text(encoding="utf-8")
    tbs = re.findall(r"<table.*?</table>", t, re.S)
    if len(tbs) != 1 or re.search(r"rowspan|colspan", tbs[0]):
        raise SystemExit("区のページの表の形がかわりました（make_items.py を直す）")
    items, unknown, seen = [], [], set()
    for tr in re.findall(r"<tr.*?</tr>", tbs[0], re.S):
        cells = [clean(c) for c in re.findall(r"<t[hd][^>]*>(.*?)</t[hd]>", tr, re.S)]
        if len(cells) != 4:
            raise SystemExit(f"表の行の形がかわりました：{cells}")
        if cells[1] == "ものの名前":
            if cells[2] != "種類":
                raise SystemExit(f"表の見出しがかわりました：{cells}")
            continue
        _, name, kind, note = cells
        cs = CATS.get(kind)
        if not cs:
            unknown.append(f"{name}（{kind}）")
            continue
        for c, head in cs:
            if (name, c) in seen:
                continue
            seen.add((name, c))
            d = [x for x in (head, note) if x]
            it = {"n": name, "c": c, "y": kana.yomi(re.sub(r"（.*", "", name)).strip()}
            if d:
                it["d"] = "。".join(x.rstrip("。") for x in d)
            items.append(it)
    if unknown:
        raise SystemExit("アプリの区分に当てはまらない種類があります（CATS に足す）：" + "、".join(unknown))
    rows = [json.dumps(x, ensure_ascii=False, separators=(",", ":")) for x in items]
    (m.data_dir / "items.js").write_text(
        f"// 東京都 墨田区（13107）の品目検索のデータ（{len(items)}件）\n"
        "// 墨田区のページ「資源とごみの分別一覧表（50音順）」の表。tools/munis/13_tokyo/13107_sumida/make_items.py で作る\n"
        "// 1行に1品目：{n:品名, c:区分, y:読み, d:注意}\n"
        'gomiData("13107", "items", /*ITEMS-START*/[\n' + ",\n".join(rows) + "\n]/*ITEMS-END*/);\n",
        encoding="utf-8", newline="\n")
    from collections import Counter
    print(f"品目 {len(items)}件 → {m.data_dir / 'items.js'}")
    print(Counter(x["c"] for x in items))


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
