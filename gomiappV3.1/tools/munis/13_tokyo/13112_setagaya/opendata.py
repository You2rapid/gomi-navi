"""東京都 世田谷区（13112）：オープンデータから品目検索のデータ（data/13_tokyo/13112_setagaya/items.js）を作る。

このファイルのきまり（どの自治体も同じ形。tools/update_opendata.py から使う）:
  DATASETS  … 使うオープンデータ（用途・データセットのページ・保存する名前・どのファイルか）
              保存先は 元データ/<県>/<自治体>/オープンデータ/
  build(src) … src（上のフォルダ）のファイルからアプリのデータを作って書く。作ったものの説明（文字列のリスト）を返す

元：東京都オープンデータカタログサイトの世田谷区のデータセット（どちらも CC BY）
  ・「ごみ分別一覧」（新しい。約165品目。区のページ「資源・ごみの分別（50音順）」と同じ中身）
  ・「ごみの分別方法一覧」（古い。約790品目。令和6年11月）
新しいほうを先に使い、古いほうは新しいほうにない品目だけを足す（同じ品目は新しいほうの区分にする）。
どちらの CSV も、見出しの「品目」と「分別区分」の列が入れかわっている（3列目が分別区分、4列目が品目）。
"""
import csv
import json
import re
import sys
import unicodedata
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "lib"))
import kana  # noqa: E402
import munis as M  # noqa: E402

CATALOG = "https://catalog.data.metro.tokyo.lg.jp/dataset/"
DATASETS = [
    {"use": "品目（新しい一覧）", "url": CATALOG + "t131121d3000000001",
     "file": "ごみ分別一覧.csv", "pick": lambda r: r["format"] == "CSV"},
    {"use": "品目（古い一覧）", "url": CATALOG + "t131121d0000000012",
     "file": "ごみの分別方法一覧.csv", "pick": lambda r: r["format"] == "CSV"},
]

# 分別区分の文の中の言葉 → アプリの区分（city.js の cats）。文の中でいちばん前に出てくる言葉の区分にする
# （「拠点回収または不燃ごみ」→ 拠点、「陶器製は不燃ごみ、プラスチック製は可燃ごみ」→ 不燃）。分別区分の文は注意に残す
WORDS = [("区では収集", "×"), ("区では回収", "×"), ("回収ボックス", "拠点"), ("古着回収", "拠点"), ("店頭", "拠点"),
         ("拠点回収", "拠点"), ("粗大ごみ", "粗大"), ("不燃ごみ", "不燃"), ("可燃ごみ", "可燃"), ("資源", "資源")]
PLAIN = {"可燃ごみ", "不燃ごみ", "資源", "粗大ごみ", "拠点回収", "区では収集していません", "区では収集できないもの"}


def tidy(s):
    s = unicodedata.normalize("NFKC", kana.letters(s)).strip()
    s = s.replace("(", "（").replace(")", "）").replace(" ", "　").replace("　", " ")
    return re.sub(r"\s+", " ", s).strip()


def category(kubun, name, note):
    k = tidy(kubun)
    hit = sorted(((k.find(w), c) for w, c in WORDS if w in k), key=lambda x: x[0])
    if not hit:
        return None
    c = hit[0][1]
    if c == "資源" and "ペットボトル" in name:
        c = "ペット"            # ペットボトルは資源とは別の日（月2回）
    if c == "×" and "家電リサイクル" in note:
        c = "家電"
    return c


def read(path):
    rows = list(csv.reader(open(path, encoding="utf-8-sig")))
    head = rows[0]
    if not (head[2].endswith("品目") and head[3].endswith("分別区分")):
        raise SystemExit(f"{path.name}：列がかわりました（{head}）。opendata.py を直す")
    out = []
    for r in rows[1:]:
        if len(r) < 9 or not r[3].strip():
            continue
        kubun, name, note = r[2], tidy(r[3]), tidy(r[8])
        # 見出しどおりの列のときもあるかもしれないので、分別区分らしい方を区分にする
        if category(kubun, name, note) is None and category(r[3], tidy(r[2]), note):
            kubun, name = r[3], tidy(r[2])
        out.append((name, kubun, note))
    return out


def build(src):
    src = Path(src)
    new, old = read(src / "ごみ分別一覧.csv"), read(src / "ごみの分別方法一覧.csv")
    items, seen, unknown, n_old = [], set(), [], 0
    for rows, is_old in ((new, False), (old, True)):
        for name, kubun, note in rows:
            key = re.sub(r"[\s・、]", "", name)
            if key in seen:
                continue
            c = category(kubun, name, note)
            if not c:
                unknown.append(f"{name}（{kubun}）")
                continue
            seen.add(key)
            d = note
            k = tidy(kubun)
            if k not in PLAIN:
                d = f"分別：{k}。" + (d if d else "")
            it = {"n": name, "c": c, "y": kana.yomi(name)}
            if d:
                it["d"] = d
            items.append(it)
            n_old += is_old
    if unknown:
        raise SystemExit("アプリの区分に当てはまらない分別区分があります（WORDS に足す）：" + "、".join(unknown))
    m = M.munis(["13112"])[0]
    rows_js = [json.dumps(x, ensure_ascii=False, separators=(",", ":")) for x in items]
    (m.data_dir / "items.js").write_text(
        f"// 東京都 世田谷区（13112）の品目検索のデータ（{len(items)}件）\n"
        "// 東京都オープンデータカタログサイトの世田谷区「ごみ分別一覧」「ごみの分別方法一覧」（CC BY）から自動で作ったファイルです。\n"
        "// 手で直さず、python gomiappV3.1/tools/update_opendata.py 13112 で作り直してください。\n"
        "// 1行に1品目：{n:品名, c:区分, y:読み, d:注意}\n"
        'gomiData("13112", "items", /*ITEMS-START*/[\n' + ",\n".join(rows_js) + "\n]/*ITEMS-END*/);\n",
        encoding="utf-8", newline="\n")
    return [f"品目 {len(items)}件（新しい一覧 {len(items) - n_old}件＋古い一覧にだけある品目 {n_old}件）→ {m.data_dir / 'items.js'}"]
