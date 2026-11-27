"""東京都 新宿区（13104）：区のページ「資源・ごみ分別辞典」から品目検索のデータ（items.js）を作る。

使い方（gomi フォルダで）：python gomiappV3.1/tools/munis/13_tokyo/13104_shinjuku/make_items.py （--download で区のページを取り直す）
元：元データ/13_東京都/13104_新宿区/2026年度/分別辞典.html（表：行・品目名・分別種別・注意点等。2024年12月27日更新）
  https://www.city.shinjuku.lg.jp/seikatsu/seiso01_001025.html
品目のオープンデータ「新宿区のゴミの分別方法一覧」（東京都オープンデータカタログ t131041d0000000129、CSV は 2023年4月）は、
「資源プラスチック」（製品プラスチックもいっしょに出す）より前の分け方（「容器包装プラスチック」）のままで古いので使わない。
・分別種別が「燃やすごみ、金属・陶器・ガラスごみ、資源プラスチック」のように2つ以上あるもの（素材で分かれる）は、区分ごとに同じ品目を並べ、
  注意点（「100％プラスチック素材のものは「資源プラスチック」…」）をそのまま付ける（区の辞典のとおり。どれか1つにしない）。
・資源（週1回）は、古紙・資源プラスチック・びん・缶・ペットボトル・スプレー缶・カセットボンベ・乾電池を同じ日に出す（city.js の dayAs）。
・収集不可のうち、家電リサイクル法の品目は「家電」、区の回収ボックスで回収するもの（携帯電話・インクカートリッジなど）は「拠点」、ほかは「×」。
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

URL = "https://www.city.shinjuku.lg.jp/seikatsu/seiso01_001025.html"
CATS = {"燃やすごみ": "燃やす", "金属・陶器・ガラスごみ": "金属", "粗大ごみ": "粗大", "古紙": "古紙", "資源プラスチック": "プラ",
        "びん・缶・ペットボトル": "びん缶ペット", "スプレー缶・カセットボンベ・乾電池": "スプレー", "収集不可": "×"}
KADEN = ("エアコン", "クーラー", "テレビ", "冷蔵庫", "冷凍庫", "洗濯機", "衣類乾燥機", "衣類用乾燥機")


def clean(s):
    s = re.sub(r"<br\s*/?>", " ", s)
    s = H.unescape(re.sub(r"<[^>]+>", "", s)).replace("　", " ")
    return re.sub(r"\s+", " ", s).strip()


def main():
    m = M.munis(["13104"])[0]
    src = m.year_dir(2026) / "分別辞典.html"
    if "--download" in sys.argv:
        src.write_bytes(urllib.request.urlopen(urllib.request.Request(URL, headers={"User-Agent": "Mozilla/5.0"}), timeout=60).read())
    t = src.read_text(encoding="utf-8")
    items, unknown, seen, nrow = [], [], set(), 0
    for tb in re.findall(r"<table.*?</table>", t, re.S):
        for tr in re.findall(r"<tr.*?</tr>", tb, re.S):
            cells = [clean(x) for x in re.findall(r"<t[hd][^>]*>(.*?)</t[hd]>", tr, re.S)]
            if len(cells) != 4 or cells[1:3] == ["品目名", "分別種別"]:
                continue        # 見出しと、ページの下の問い合わせ先の表
            _, name, kubun, note = cells
            nrow += 1
            for k in kubun.split("、"):
                c = CATS.get(k.strip())
                if not c:
                    unknown.append(f"{name}（{kubun}）")
                    continue
                if c == "×" and any(x in name for x in KADEN) and "リサイクルが義務" in note:
                    c = "家電"
                elif c == "×" and re.search(r"回収ボックス|回収BOX", note):
                    c = "拠点"
                if (name, c) in seen:
                    continue
                seen.add((name, c))
                it = {"n": name, "c": c, "y": kana.yomi(re.sub(r"（.*", "", name)).strip()}
                if note:
                    it["d"] = note
                items.append(it)
    if unknown:
        raise SystemExit("アプリの区分に当てはまらない分別種別があります（CATS に足す）：" + "、".join(unknown))
    if nrow < 400:
        raise SystemExit(f"品目が {nrow} 行しか読めません（ページの形がかわった？）")
    rows = [json.dumps(x, ensure_ascii=False, separators=(",", ":")) for x in items]
    (m.data_dir / "items.js").write_text(
        f"// 東京都 新宿区（13104）の品目検索のデータ（{len(items)}件）\n"
        "// 新宿区のページ「資源・ごみ分別辞典」の表。tools/munis/13_tokyo/13104_shinjuku/make_items.py で作る\n"
        "// 1行に1品目：{n:品名, c:区分, y:読み, d:注意}\n"
        'gomiData("13104", "items", /*ITEMS-START*/[\n' + ",\n".join(rows) + "\n]/*ITEMS-END*/);\n",
        encoding="utf-8", newline="\n")
    print(f"品目 {len(items)}件（辞典の行 {nrow}）→ {m.data_dir / 'items.js'}")


if __name__ == "__main__":
    main()
