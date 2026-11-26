"""東京都 北区（13117）：区のページ「家庭ごみ分別辞典」から品目検索のデータ（items.js）を作る。

使い方（gomi フォルダで）：python gomiappV3.1/tools/munis/13_tokyo/13117_kita/make_items.py （--download で区のページを取り直す）
元：元データ/13_東京都/13117_北区/2026年度/分別辞典/<ページ番号>.html（あ行〜わ行の10ページ。表：ごみ名・分別区分・備考）
  https://www.city.kita.lg.jp/living/bins/1002013/1025613/index.html
北区には品目のオープンデータがない（東京都オープンデータカタログに北区の「ごみ分別」はなかった。2026-11-26）。
分別区分のうち、古着・古布・紙パック・発泡トレイ・廃食油・水銀入り乾電池・インクカートリッジ・ペットボトルキャップ・
リサイクルできる電池・「資源ごみ」（モバイルバッテリー）は、集積所には出さず、区の施設の回収容器や店の回収ボックスへ出すもの（冊子 p.19〜20）→「拠点」。
「不燃ごみ・金属資源」「金属資源」は不燃ごみの日に、ほかの不燃ごみとは別の袋で出す（冊子 p.7〜8）→「不燃」。
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

PAGES = ["1025614", "1025624", "1025625", "1025626", "1025627", "1025628", "1025629", "1025630", "1025631", "1025632"]
URL = "https://www.city.kita.lg.jp/living/bins/1002013/1025613/{}.html"
# 分別区分 → アプリの区分（city.js の cats）
CATS = {"可燃ごみ": "可燃", "不燃ごみ": "不燃", "不燃ごみ・金属資源": "不燃", "金属資源": "不燃",
        "古紙": "古紙", "プラスチック": "プラ", "びん・缶・ペットボトル": "びん缶ペット", "粗大ごみ": "粗大",
        "家電リサイクル": "家電", "家庭用パソコン": "×", "区が収集できないもの": "×",
        "古着・古布": "拠点", "紙パック・発泡トレイ": "拠点", "廃食油": "拠点", "水銀入り乾電池": "拠点",
        "使用済みインクカートリッジ": "拠点", "ペットボトルキャップ": "拠点", "リサイクルできる電池": "拠点", "資源ごみ": "拠点"}
# 区分の名前を注意の頭に書くもの（アプリの区分の名前だけではわからないもの）
NOTE_HEAD = {"不燃ごみ・金属資源": "金属資源（ほかの不燃ごみとは別の袋で）", "金属資源": "金属資源（ほかの不燃ごみとは別の袋で）",
             "家庭用パソコン": "家庭用パソコン（区では収集しない）"}
for k, c in CATS.items():
    if c == "拠点":
        NOTE_HEAD[k] = f"{k}（集積所には出さない）"
NOTE_HEAD["ペットボトルキャップ"] += "。捨てる場合は、プラスチックの日に出す"     # 冊子 p.20「捨てる場合は、プラスチック回収日にお出しください」


def clean(s):
    s = re.sub(r"<a[^>]*>(?:(?!</a>).)*外部リンク(?:(?!</a>).)*</a>", "", s, flags=re.S)          # 「粗大ごみ受付センター（外部リンク）」などのリンクはのぞく
    s = re.sub(r"<br\s*/?>|</p>|</li>", "\n", s)
    s = H.unescape(re.sub(r"<[^>]+>", "", s)).replace("　", " ")
    lines = [re.sub(r"\s+", " ", x).strip() for x in s.split("\n")]
    lines = [x for x in lines if x]
    return "".join(x if x[-1] in "。）)」" or i == len(lines) - 1 else x + "。" for i, x in enumerate(lines))


def main():
    m = M.munis(["13117"])[0]
    src = m.year_dir(2026) / "分別辞典"
    if "--download" in sys.argv:
        for p in PAGES:
            raw = urllib.request.urlopen(urllib.request.Request(URL.format(p), headers={"User-Agent": "Mozilla/5.0"}), timeout=60).read()
            (src / f"{p}.html").write_bytes(raw)
    items, unknown, seen = [], [], set()
    for p in PAGES:
        t = (src / f"{p}.html").read_text(encoding="utf-8")
        for tb in re.findall(r"<table.*?</table>", t, re.S):
            for tr in re.findall(r"<tr.*?</tr>", tb, re.S):
                cells = re.findall(r"<t[hd][^>]*>(.*?)</t[hd]>", tr, re.S)
                if len(cells) != 3:
                    raise SystemExit(f"{p}.html の表の形がかわりました：{cells}")
                name, kubun, note = (clean(x) for x in cells)
                if name == "ごみ名":
                    if kubun not in ("分別区分", "分別区別"):
                        raise SystemExit(f"{p}.html の表の見出しがかわりました：{kubun}")
                    continue
                c = CATS.get(kubun)
                if not c:
                    unknown.append(f"{name}（{kubun}）")
                    continue
                if (name, c) in seen:
                    continue
                seen.add((name, c))
                d = [x for x in (NOTE_HEAD.get(kubun, ""), note) if x]
                it = {"n": name, "c": c, "y": kana.yomi(re.sub(r"（.*", "", name)).strip()}
                if d:
                    it["d"] = "。".join(x.rstrip("。") for x in d)
                items.append(it)
    if unknown:
        raise SystemExit("アプリの区分に当てはまらない分別区分があります（CATS に足す）：" + "、".join(unknown))
    rows = [json.dumps(x, ensure_ascii=False, separators=(",", ":")) for x in items]
    (m.data_dir / "items.js").write_text(
        f"// 東京都 北区（13117）の品目検索のデータ（{len(items)}件）\n"
        "// 北区のページ「家庭ごみ分別辞典」の表。tools/munis/13_tokyo/13117_kita/make_items.py で作る\n"
        "// 1行に1品目：{n:品名, c:区分, y:読み, d:注意}\n"
        'gomiData("13117", "items", /*ITEMS-START*/[\n' + ",\n".join(rows) + "\n]/*ITEMS-END*/);\n",
        encoding="utf-8", newline="\n")
    print(f"品目 {len(items)}件 → {m.data_dir / 'items.js'}")


if __name__ == "__main__":
    main()
