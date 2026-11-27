"""東京都 豊島区（13116）：冊子「資源回収・ごみ収集のお知らせ」の「50音順分別一覧表」（PDF 2ページ）から品目検索のデータ（items.js）を作る。

使い方（gomi フォルダで）：python gomiappV3.1/tools/munis/13_tokyo/13116_toshima/make_items.py （--ocr で OCR からやり直す。Windows のみ）
元：元データ/13_東京都/13116_豊島区/分別の冊子/50音順分別一覧.pdf
  https://www.city.toshima.lg.jp/150/kurashi/gomi/shigen/013329.html の「50音順分別一覧」
豊島区には品目のオープンデータがない（東京都オープンデータカタログに豊島区のごみのデータはなかった。2026-11-27）。

この PDF は文字が図形になっていて（文字として読めない）、表は1ページに4つ（品目・分別区分・出し方の注意点等）。
  1. 分別区分のマス（色の四角。x が 100・292・511・703、幅 23）を1行とみる。同じ四角が2つ重なっている行があるので1つにする。
  2. 区分はマスの色で決める（燃やす＝赤・金陶ガ＝青・紙布＝緑・プラ＝水色・びかペ＝黄緑・家電・パソコン＝うすい黄・不可＝白）。
     「粗大」と「区施設等」は同じ黄色なので、マスの文字を OCR で読んで見分ける。
  3. 品名（マスの左 56pt）と注意（マスの右 88pt）を 400dpi の画像にして ocr.ps1（Windows の OCR）で読む → 分別の冊子/ocr/<番号><n|c|d>.png.tsv
  4. OCR が読めなかった品名は画像を見て NAME に、読みまちがいは FIX・NOTEFIX に書いた。
"""
import json
import re
import subprocess
import sys
import unicodedata
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "lib"))
import kana  # noqa: E402
import munis as M  # noqa: E402

HERE = Path(__file__).resolve().parent
SRC = Path("元データ/13_東京都/13116_豊島区/分別の冊子/50音順分別一覧.pdf")
OCR = SRC.parent / "ocr"
XS = (100, 292, 511, 703)
COLOR = {"#db414c": "燃やす", "#1b76bb": "金属陶器ガラス", "#469c6b": "紙布", "#00b6ad": "プラ", "#9bbb3c": "びん缶ペット",
         "#f6f3cf": "家電", "#ffffff": "×"}
YELLOW = "#f3e696"      # 「粗大」か「区施設等」（文字で見分ける）
# OCR が品名を読めなかった行（番号は PDF の分別区分のマスの順。画像を見て書いた）
NAME = {35: "温度計", 41: "鏡", 43: "傘", 80: "靴", 90: "ござ", 101: "三輪車", 121: "スーツ", 122: "すずり", 129: "炭",
        151: "爪きり", 153: "テープ（カセットテープ、ビデオテープ）", 162: "電卓", 164: "電話機（固定電話）", 176: "ノート",
        177: "ハーモニカ", 179: "灰", 193: "ピアノ", 231: "本", 237: "マッチ", 239: "ミキサー", 245: "やかん", 260: "綿",
        261: "和服（着物・帯）", 1: "ICレコーダー", 105: "シーツ"}
# OCR が区分のマスの文字を読めなかった行（画像を見て書いた）
CATTEXT = {85: "区施設等", 111: "区施設等", 204: "区施設等"}
# OCR の読みまちがい（品名）
FIX = {
    "安全ヒン": "安全ピン", "ー斗缶": "一斗缶", "工アコン": "エアコン", "ACアダブター": "ACアダプター", "絵の具のチュープ": "絵の具のチューブ",
    "カーヘット": "カーペット", "しゅうたん": "じゅうたん", "カセットホンべ": "カセットボンベ", "がびよう": "がびょう", "カーポン": "カーボン",
    "紙ノヾック": "紙パック", "キーポード": "キーボード", "木くす": "木くず", "グロープ": "グローブ", "なと": "など",
    "カラス、金属製": "ガラス、金属製", "ゴルフポール": "ゴルフボール", "コンタクトレンス": "コンタクトレンズ", "バンフレット": "パンフレット",
    "自転車仔供用含む": "自転車（子供用含む", "ストッキンク": "ストッキング", "ヘット用": "ペット用", "せつけん": "せっけん",
    "たまごのバック": "たまごのパック", "くつついて": "くっついて", "チャイルトシート": "チャイルドシート", "液品": "液晶",
    "プラウン管": "ブラウン管", "電気コート": "電気コード", "、電子辞書": "電子辞書", "電子レンシ": "電子レンジ",
    "電動歯ふらし": "電動歯ブラシ", "トイレットペーバー": "トイレットペーパー", "トナーカートリッシ": "トナーカートリッジ",
    "ヘンキ": "ペンキ", "めいぐるみ": "ぬいぐるみ", "バケッ": "バケツ", "/ーケッ": "バケツ", "/ット": "バット",
    "ノヾソコン": "パソコン", "ヒテオテッキ": "ビデオデッキ", "フライバン": "フライパン", "プロック": "ブロック",
    "ペットボトル体体": "ペットボトル（本体", "べンシン": "ベンジン", "シンナー": "シンナー", "ポールペン": "ボールペン",
    "防虫剤依類用": "防虫剤（衣類用", "マイクロヒーズ": "マイクロビーズ", "よしす": "よしず",
    "キーポード": "キーボード", "トナーカートリッシ": "トナーカートリッジ", "ビザ": "ピザ", "手提け式": "手提げ式",
}
# 読み（pykakasi で読みちがえるもの）
YOMI = {"綿": "わた", "綿毛布": "めんもうふ"}
# 注意の行のつなぎ方：前の行がこの字で終わるときだけ「。」で区切る（ほかは1つの文が2行に分かれている）
SENTENCE_END = ("す", "へ", "照", "可", "む", "い。")
# OCR の読みまちがい（注意）
NOTEFIX = {"30(m": "30cm", "30（m": "30cm", "包既キケン」": "包み「キケン」", "包キケン」": "包み「キケン」", "ヘージ": "ページ", "ヘーシ": "ページ",
           "しはって": "しばって", "の-辺": "の一辺", "8~11": "8〜11"}


def hexcol(f):
    return "#%02x%02x%02x" % tuple(int(x * 255 + .5) for x in f[:3])


def labels():
    """分別区分のマス → [(ページ, 四角, 色)]（PDF の順。番号は NAME の番号）"""
    import pymupdf
    d = pymupdf.open(SRC)
    out = []
    for pn, p in enumerate(d):
        for g in p.get_drawings():
            r = g["rect"]
            if g.get("fill") and 22 < r.width < 24.5 and 13 < r.height < 40 and round(r.x0) in XS:
                out.append((pn, r, hexcol(g["fill"])))
    out.sort(key=lambda x: (x[0], round(x[1].x0), x[1].y0))
    return d, out


def run_ocr():
    import pymupdf
    d, labs = labels()
    OCR.mkdir(exist_ok=True)
    paths = []
    for i, (pn, r, _) in enumerate(labs):
        for kind, clip in [("n", pymupdf.Rect(r.x0 - 56, r.y0, r.x0, r.y1)), ("c", r), ("d", pymupdf.Rect(r.x1, r.y0, r.x1 + 88, r.y1))]:
            fn = OCR / f"{i:03d}{kind}.png"
            d[pn].get_pixmap(dpi=400, clip=clip).save(fn)
            paths.append(str(fn.resolve()))
    subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(HERE / "ocr.ps1"), "-Paths", *paths], check=True)


def text(i, kind):
    p = OCR / f"{i:03d}{kind}.png.tsv"
    lines, cur = [], None
    for row in p.read_text(encoding="utf-8-sig").splitlines():
        if not row.strip():
            continue
        li, *_, w = row.split("\t")
        if li != cur:
            lines.append("")
            cur = li
        lines[-1] += w
    return lines


def tidy(s):
    s = unicodedata.normalize("NFKC", s).replace("(", "（").replace(")", "）").replace("~", "〜")
    s = re.sub(r"(?<=[ァ-ヶー])-(?=[ァ-ヶ])", "ー", s)
    return s.strip()


def build():
    _, labs = labels()
    items, seen, problems = [], set(), []
    # 同じ場所に四角が2つ重なっている行がある（白い四角の上に色の四角）。色のあるほうを使う
    best = {}
    for i, (pn, r, col) in enumerate(labs):
        place = (pn, round(r.x0), round(r.y0))
        if place not in best or best[place][2] == "#ffffff":
            best[place] = (i, r, col)
    keep = {v[0] for v in best.values()}
    for i, (pn, r, col) in enumerate(labs):
        if i not in keep:
            continue
        c_txt = "".join(text(i, "c"))
        if "分別区分" in c_txt:
            continue        # 表の見出し
        if col == YELLOW:
            c_txt = CATTEXT.get(i, c_txt)
            c = "粗大" if "粗大" in c_txt else "拠点" if "区施設" in c_txt else "家電" if "家電" in c_txt else None
        else:
            c = COLOR.get(col)
        if not c:
            problems.append(f"{i}：区分がわからない（色 {col}・文字 {c_txt}）")
            continue
        name = NAME.get(i) or "".join(text(i, "n"))
        for a, b in FIX.items():
            name = name.replace(a, b)
        name = tidy(name)
        for a, b in FIX.items():
            name = name.replace(a, b)
        if not name:
            problems.append(f"{i}：品名が読めない（NAME に書く）")
            continue
        note = ""
        for x in text(i, "d"):
            x = tidy(x)
            note += ("。" if note and note.endswith(SENTENCE_END) else "") + x
        for a, b in NOTEFIX.items():
            note = note.replace(a, b)
        note = tidy(note).replace("。。", "。")
        if c == "拠点":
            note = "区施設等の回収ボックスへ" + (f"。{note}" if note else "")
        if c == "家電" and "パソコン" in note:
            note = note.replace("パソコンリサイクル対象品目で", "パソコンリサイクル対象品目です").replace("ですす", "です")
        if (name, c) in seen:
            continue
        seen.add((name, c))
        base = re.sub(r"（.*", "", name)
        it = {"n": name, "c": c, "y": YOMI.get(base) or kana.yomi(base)}
        if note:
            it["d"] = note
        items.append(it)
    if problems:
        raise SystemExit("\n".join(problems))
    m = M.munis(["13116"])[0]
    rows = [json.dumps(x, ensure_ascii=False, separators=(",", ":")) for x in items]
    (m.data_dir / "items.js").write_text(
        f"// 東京都 豊島区（13116）の品目検索のデータ（{len(items)}件）\n"
        "// 区の冊子「資源回収・ごみ収集のお知らせ」の「50音順分別一覧表」（PDF）から自動で作ったファイルです。\n"
        "// 手で直さず、python gomiappV3.1/tools/munis/13_tokyo/13116_toshima/make_items.py で作り直してください。\n"
        "// 1行に1品目：{n:品名, c:区分, y:読み, d:注意}\n"
        'gomiData("13116", "items", /*ITEMS-START*/[\n' + ",\n".join(rows) + "\n]/*ITEMS-END*/);\n",
        encoding="utf-8", newline="\n")
    print(f"品目 {len(items)}件 → {m.data_dir / 'items.js'}")
    return items


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    if "--ocr" in sys.argv:
        run_ocr()
    build()
