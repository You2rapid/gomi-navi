"""東京都 練馬区（13120）：区のページ「これって何ごみ？品目別出し方一覧（ごみ分別辞典）」から品目検索のデータ（items.js）を作る。

使い方（gomi フォルダで）：python gomiappV3.1/tools/munis/13_tokyo/13120_nerima/make_items.py
元：元データ/13_東京都/13120_練馬区/分別の冊子/品目検索_<agyo・kagyo・…・yagyo>.html（8ページ。表：品目・分別区分・出し方と注意点）
  https://www.city.nerima.tokyo.jp/kurashi/gomi/wakekata/bunbetsu/index.html
練馬区には品目のオープンデータがない（東京都オープンデータカタログに練馬区の「ごみ分別」はなかった。2026-11-26）。
令和8年10月から、プラスチック製品も「プラスチック」（容器包装プラスチックと同じ日）に出せるようになった。辞典はその後の版（2026-10-01 更新）。
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

PAGES = ["agyo", "kagyo", "sagyo", "tagyo", "nagyo", "hagyo", "magyo", "yagyo"]
URL = "https://www.city.nerima.tokyo.jp/kurashi/gomi/wakekata/bunbetsu/{}.html"
# 分別区分 → アプリの区分（city.js の cats）
CATS = {"可燃ごみ": "可燃", "不燃ごみ": "不燃", "粗大ごみ": "粗大", "プラスチック": "プラ", "容器包装プラスチック": "プラ",
        "古紙": "古紙", "拠点回収": "拠点", "不可": "×", "別途": "別途"}


def clean(s):
    s = re.sub(r"<br\s*/?>", "／", s)
    s = H.unescape(re.sub(r"<[^>]+>", "", s)).replace("　", " ")
    return re.sub(r"\s+", " ", s).strip(" ／")


def main():
    m = M.munis(["13120"])[0]
    src = m.src_dir / "分別の冊子"
    if "--download" in sys.argv:
        for p in PAGES:
            raw = urllib.request.urlopen(urllib.request.Request(URL.format(p), headers={"User-Agent": "Mozilla/5.0"}), timeout=60).read()
            (src / f"品目検索_{p}.html").write_bytes(raw)
    items, unknown, seen = [], [], set()
    for p in PAGES:
        t = (src / f"品目検索_{p}.html").read_text(encoding="utf-8")
        for tr in re.findall(r"<tr>(.*?)</tr>", t, re.S):
            th = re.findall(r'<th scope="row"[^>]*>(.*?)</th>', tr, re.S)
            td = re.findall(r"<td[^>]*>(.*?)</td>", tr, re.S)
            if not th or not td:
                continue
            name, kubun, note = clean(th[0]), clean(td[0]), clean(td[1]) if len(td) > 1 else ""
            if kubun == "飲食用びん・缶・ペットボトル":
                c = "ペット" if "ペットボトル" in name else "びん缶"
            else:
                c = CATS.get(kubun)
            if c == "×" and "家電リサイクル" in note:
                c = "家電"
            if not c:
                unknown.append(f"{name}（{kubun}）")
                continue
            if (name, c) in seen:
                continue
            seen.add((name, c))
            it = {"n": name, "c": c, "y": kana.yomi(name)}
            if note:
                it["d"] = note
            items.append(it)
    if unknown:
        raise SystemExit("アプリの区分に当てはまらない分別区分があります（CATS に足す）：" + "、".join(unknown))
    rows = [json.dumps(x, ensure_ascii=False, separators=(",", ":")) for x in items]
    (m.data_dir / "items.js").write_text(
        f"// 東京都 練馬区（13120）の品目検索のデータ（{len(items)}件）\n"
        "// 練馬区のページ「これって何ごみ？品目別出し方一覧（ごみ分別辞典）」の表。tools/munis/13_tokyo/13120_nerima/make_items.py で作る\n"
        "// 1行に1品目：{n:品名, c:区分, y:読み, d:注意}\n"
        'gomiData("13120", "items", /*ITEMS-START*/[\n' + ",\n".join(rows) + "\n]/*ITEMS-END*/);\n",
        encoding="utf-8", newline="\n")
    print(f"品目 {len(items)}件 → {m.data_dir / 'items.js'}")


if __name__ == "__main__":
    main()
