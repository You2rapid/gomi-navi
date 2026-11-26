"""東京都 杉並区（13115）：区の「ごみと資源の分け方・出し方『50音順』」（PDF）から品目検索のデータ（items.js）を作る。

使い方（gomi フォルダで）：python gomiappV3.1/tools/munis/13_tokyo/13115_suginami/make_items.py
元：元データ/13_東京都/13115_杉並区/分別の冊子/goju.pdf（31ページ。令和8年4月からの修正版。区のページ「ごみと資源の分け方・出し方」ID 713）
  https://www.city.suginami.tokyo.jp/documents/713/goju.pdf
この PDF は画像だけ（文字がない）なので、Windows の文字読み取り（OCR）で読む。
  1. ページを 300dpi の画像にして ocr.ps1 で読む → 分別の冊子/goju_ocr/gNN.png.tsv（1文字ずつの位置と文字）
     区分のマスが読めなかった行は、マスだけを切り出して読みなおした → goju_ocr/cells/c_<ページ>_<行>.png.tsv
     用途・素材のマスが空になった行も、マスだけを読みなおした → goju_ocr/cells/u_<ページ>_<行>.png.tsv
     （作りなおすときは --ocr。PowerShell で ocr.ps1 を動かす。マスの読みなおしは手でやった）
  2. 画像の罫線（黒い横線）で行を、決まった位置で列（50音・品名・用途 素材 形状・分別・出し方と注意点）を分ける。
  3. OCR の読みまちがい（「/ヾ」→「バ」、「)レ」→「ル」、「工アコン」→「エアコン」など）を FIX で直す。
     それでも読めなかった品名・区分は、画像を見て NAME・CAT に書いた（ページと行の番号）。
区分（分別の列）→ アプリの区分：可燃・不燃・資源プラ・びん・かん・古紙・ペットボトル・粗大・拠点回収・収集不可。
  「不燃または粗大」のように2つあるときは、はじめの区分にして、注意に「（不燃ごみ・粗大ごみ）」と書く。
品目のオープンデータ「ごみの分別方法一覧」（a2.csv、令和7年4月時点・128品目）もあるが、令和8年度の冊子より古く、品目も少ないので使わない（README）。
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
URL = "https://www.city.suginami.tokyo.jp/documents/713/goju.pdf"
COLS = [119, 212, 677, 1107, 1577, 2330]      # 300dpi の画像での列の境目（50音・品名・用途・分別・出し方）
TOP = 327                                       # 見出しの下の線
CAT = {"可燃": "可燃", "不燃": "不燃", "資源プラ": "資源プラ", "びん": "びん", "かん": "かん", "古紙": "古紙",
       "ペットボトル": "ペット", "粗大": "粗大", "拠点回収": "拠点", "収集不可": "×", "資源": "資源プラ"}
LONG = {"可燃": "可燃ごみ", "不燃": "不燃ごみ", "資源プラ": "資源プラスチック", "びん": "びん", "かん": "かん", "古紙": "古紙",
        "ペット": "ペットボトル", "粗大": "粗大ごみ", "拠点": "拠点回収", "×": "収集不可"}

# 画像を見て読んだ品名（OCR で読めなかったもの）：(ページ, 行) → 品名
NAME = {(1, 21): "網戸", (4, 7): "縁台", (5, 17): "温室", (5, 19): "温度計", (5, 20): "温度計", (6, 7): "鏡", (6, 14): "かご",
        (9, 11): "くぎ", (11, 2): "雑誌", (11, 6): "皿", (11, 7): "皿", (11, 8): "皿", (11, 9): "皿", (15, 19): "体温計",
        (15, 20): "体温計", (18, 21): "電池", (19, 0): "テント", (19, 16): "時計", (20, 1): "人形", (20, 8): "ネジ",
        (20, 9): "ネット", (20, 13): "ノート", (20, 20): "バーベル", (21, 3): "廃油", (21, 4): "廃油", (21, 13): "はしご",
        (21, 21): "バット", (22, 0): "バット", (22, 1): "バット", (25, 5): "ベンジン", (27, 22): "ミシン", (28, 8): "メジャー",
        (28, 9): "メジャー", (29, 13): "ライター", (30, 4): "ルアー", (30, 7): "冷温庫", (30, 19): "レンジ台"}
# 画像を見て読んだ区分（マスを切り出しても OCR で読めなかったもの）
CATFIX = {(2, 3): "不燃", (2, 17): "", (4, 9): "不燃", (6, 8): "不燃", (9, 8): "不燃", (9, 9): "可燃", (14, 26): "不燃",
          (15, 8): "不燃", (18, 14): "不燃", (18, 15): "不燃", (22, 16): "可燃", (24, 16): "可燃", (24, 20): "可燃",
          (28, 3): "不燃", (28, 21): "不燃", (30, 13): "可燃", (30, 14): "可燃"}
# OCR の読みまちがい（順に置きかえる）
FIX = [("/ヾ", "バ"), ("/、", "ハ"), (")レ", "ル"), (")し", "ル"), ("ッバ", "ッパ"), ("バソコン", "パソコン"), ("スバナ", "スパナ"),
       ("ペーバー", "ペーパー"), ("ペ-バ-", "ペーパー"), ("電気力", "電気カ"), ("ポトル", "ボトル"), ("ポンべ", "ボンベ"), ("ボンべ", "ボンベ"),
       ("ポード", "ボード"), ("ポ-ド", "ボード"), ("ダンポール", "ダンボール"), ("ゴルフポール", "ゴルフボール"), ("テニスポール", "テニスボール"),
       ("ポール各種", "ボール各種"), ("ポールペン", "ボールペン"), ("バック", "パック"), ("カーベット", "カーペット"), ("フライバン", "フライパン"),
       ("バンフレット", "パンフレット"), ("バネル", "パネル"), ("パイブ", "パイプ"), ("パイプペッド", "パイプベッド"), ("ペーカリー", "ベーカリー"),
       ("ンユ", "ジュ"), ("クレョン", "クレヨン"), ("こたっ", "こたつ"), ("バケッ", "バケツ"), ("リャカー", "リヤカー"), ("アダブター", "アダプター"),
       ("プロバン", "プロパン"), ("プロック", "ブロック"), ("シャッキ", "ジャッキ"), ("シュラルミン", "ジュラルミン"), ("丁ン", "テン"),
       ("ィーゼル", "イーゼル"), ("レンシ", "レンジ"), ("ハンデイ", "ハンディ"), ("マーシャン", "マージャン"), ("ニコンポ", "ミニコンポ"),
       ("ニ次", "二次"), ("ニ輪", "二輪"), ("しや", "しゃ"), ("じよう", "じょう"), ("びよう", "びょう"), ("ドーナツツ", "ドーナッツ"),
       ("シェーハー", "シェーバー"), ("ポールベン", "ボールペン"), ("耐熱性、の", "耐熱性の"), ("ミミニ", "ミニ"), ("ステレオー式", "ステレオ一式")]
# 途中で切れた品名・用途を、画像のとおりに直す
WHOLE = {"旅行かばん(スーツケー": "旅行かばん(スーツケース)", "レーザーディスクプレー": "レーザーディスクプレーヤー",
         "電動以外(家庭用に限": "電動以外(家庭用に限る)", "紙パック(裏がアルミのもの": "紙パック(裏がアルミのもの)",
         "マヨネーズわさびなど、": "マヨネーズ・わさびなど", "デッキブラシほうき、、モップ": "デッキブラシ・ほうき・モップ",
         "乾電池リチウム一次電、池(円筒型・コイン形リチウム電池)": "乾電池・リチウム一次電池(円筒型・コイン形リチウム電池)",
         "割れたもの・梅酒用(市": "割れたもの・梅酒用(市販)",
         "引uetoothで機器と接続するケーブルのないイヤ": "Bluetoothで機器と接続するケーブルのないイヤホン"}
KATA = re.compile(r"[ァ-ヴー]")


def fix(s):
    s = unicodedata.normalize("NFKC", s).replace("ヘ゛", "ベ")
    for a, b in FIX:
        s = s.replace(a, b)
    s = re.sub(r"工(?=[ァ-ヴ])", "エ", s)
    s = re.sub(r"(?<=[A-Z]) (?=[A-Z])", "", s)
    s = re.sub(r"(?<=\d) ?O(?=cm|mm|kg|\d)", "0", s)
    out = []
    for i, ch in enumerate(s):
        prev, nxt = s[i - 1] if i else "", s[i + 1] if i + 1 < len(s) else ""
        if ch in "-ー" and nxt and nxt in "輪斗升次部" and (not KATA.match(prev) or nxt == "次"):
            ch = "一"                       # ー輪車 → 一輪車、ー斗缶 → 一斗缶、リチウムー次 → リチウム一次
        elif ch == "-":
            ch = "ー" if KATA.match(prev) else "・"
        elif ch in "べぺ" and (KATA.match(prev) or KATA.match(nxt)):
            ch = "ベ" if ch == "べ" else "ペ"
        elif ch == "、" and KATA.match(prev) and KATA.match(nxt):
            ch = ""
        out.append(ch)
    s = "".join(out)
    for a, b in FIX:
        s = s.replace(a, b)
    return WHOLE.get(s, s)


# 注意の文の読みまちがい（電話番号・URL など。画像で確かめた）
NOTEFIX = [("https・〃", "https://"), ("www ", "www."), ("pc3「.加", "pc3r.jp"), ("renet.加", "renet.jp"), ("・般", "一般"),
           ("と・緒", "と一緒"), ("ポックス", "ボックス"), ("スーバー", "スーパー"), ("対、策", "対策"), ("切、れ", "切れ"),
           ("資源、プラ", "資源プラ"), ("サラダ油ごま油", "サラダ油、ごま油"), ("メーカーパソコン", "メーカー、パソコン")]
STD = "最大辺がおおむね30cm以下のもので、プラスチック以外の素材が一部でも使われているものは可燃ごみでお出しください。"


def fix_note(s):
    s = re.sub(r"(?<=\d) (?=[\dA-Z])", "", s)
    s = re.sub(r"(?<=\d)・(?=\d)", "-", s)
    for a, b in NOTEFIX:
        s = s.replace(a, b)
    if "おおね3" in s:          # 文字がたくさん抜けた2つ（お盆・角ハンガーのプラスチック製）。画像は、ほかの品目と同じ文
        s = STD
    return s


def zen(s):
    return s.replace("(", "（").replace(")", "）")


def grid(page):
    """ページの画像の横線（行の境目）の y（300dpi）"""
    import numpy as np
    import pymupdf
    pm = page.get_pixmap(dpi=300, colorspace=pymupdf.csGRAY)
    a = np.frombuffer(pm.samples, dtype=np.uint8).reshape(pm.height, pm.width) < 128
    ys, out = np.where(a.mean(axis=1) > 0.5)[0], []
    for y in ys:
        if out and y - out[-1][-1] <= 3:
            out[-1].append(y)
        else:
            out.append([y])
    return [int(sum(g) / len(g)) for g in out if sum(g) / len(g) >= TOP]


def words(tsv):
    """OCR の TSV → [(y中心, x, 文字, 高さ, x中心)]"""
    out = []
    for ln in open(tsv, encoding="utf-8-sig"):
        f = ln.rstrip("\n").split("\t")
        if len(f) >= 6:
            x, y, w, h = map(int, f[1:5])
            out.append((y + h / 2, x, f[5], h, x + w / 2))
    return out


def join(ws):
    """1つのマスの文字を、行ごと・左から順につなぐ"""
    lines = []
    for w in sorted(ws):
        if lines and abs(w[0] - lines[-1][0][0]) < max(12, w[3] * 0.45):
            lines[-1].append(w)
        else:
            lines.append([w])
    s, prev = "", ""
    for L in lines:
        for w in sorted(L, key=lambda q: q[1]):
            t = w[2]
            if prev[-1:].isascii() and prev[-1:].isalnum() and t[:1].isascii() and t[:1].isalnum():
                s += " "
            s += t
            prev = t
    return s


def read_rows(doc, ocr):
    rows = []
    for page in doc:
        p = page.number + 1
        ys = grid(page)
        cells = {}
        for w in words(ocr / f"g{p:02d}.png.tsv"):
            ri = sum(1 for b in ys if b < w[0]) - 1
            ci = sum(1 for b in COLS if b < w[4]) - 1
            if 0 <= ri < len(ys) - 1 and 0 <= ci < 5:
                cells.setdefault((ri, ci), []).append(w)
        n = 0
        for ri in range(len(ys) - 1):
            row = [join(cells.get((ri, ci), [])) for ci in range(5)]
            if not any(row):
                continue
            cat = unicodedata.normalize("NFKC", row[3]).replace(" ", "")
            if (p, ri) in CATFIX:
                cat = CATFIX[(p, ri)]
            elif not ok(cat):
                c2 = ocr / "cells" / f"c_{p:02d}_{ri:02d}.png.tsv"
                if c2.exists():
                    cat = unicodedata.normalize("NFKC", join(words(c2))).replace(" ", "")
            u = row[2]
            u2 = ocr / "cells" / f"u_{p:02d}_{ri:02d}.png.tsv"
            if not u and u2.exists():
                u = join(words(u2))
            rows.append({"p": p, "r": ri, "n": NAME.get((p, ri)) or fix(row[1]), "u": fix(u), "c": cat, "d": fix(row[4])})
            n += 1
        if n < 8:
            raise SystemExit(f"{p}ページの品目が {n} しか読めません（PDF の形がかわった？）")
    return rows


def ok(cat):
    return bool(cat) and all(x in CAT for x in re.split("または|、", cat))


def ocr_all(doc, ocr):
    """ページを画像にして ocr.ps1 で読む（Windows のみ）"""
    ocr.mkdir(parents=True, exist_ok=True)
    paths = []
    for page in doc:
        f = ocr / f"g{page.number + 1:02d}.png"
        page.get_pixmap(dpi=300).save(f)
        paths.append(str(f))
    subprocess.run(["powershell", "-ExecutionPolicy", "Bypass", "-File", str(HERE / "ocr.ps1"), "-Paths", *paths], check=True)
    for f in paths:
        Path(f).unlink()


def main():
    import pymupdf
    m = M.munis(["13115"])[0]
    src = m.src_dir / "分別の冊子" / "goju.pdf"
    ocr = m.src_dir / "分別の冊子" / "goju_ocr"
    doc = pymupdf.open(src)
    if "--ocr" in sys.argv or not (ocr / "g01.png.tsv").exists():
        ocr_all(doc, ocr)
    out, seen, bad = [], set(), []
    for it in read_rows(doc, ocr):
        name = zen(it["n"] + (f"({it['u']})" if it["u"] else ""))
        cats = [CAT[x] for x in re.split("または|、", it["c"])] if ok(it["c"]) else []
        note = fix_note(zen(it["d"]).lstrip("※"))
        if it["c"] and not cats:
            if it["c"] != "薬局":
                bad.append((it["p"], it["r"], name, it["c"]))
            note = "薬局・医療機関に相談する。" + note
        if not cats:
            c = "×"
        else:
            c = next((x for x in cats if x != "拠点"), cats[0])     # 「拠点回収、不燃または粗大」は、集積所に出せる区分にする
            uniq = list(dict.fromkeys(cats))
            if len(uniq) > 1:
                note = "（" + "・".join(LONG[x] for x in uniq) + "）" + (" " + note if note else "")
        if "家電リサイクル" in note and c == "×":
            c = "家電"
        if not it["n"] or (name, c) in seen:
            if not it["n"]:
                bad.append((it["p"], it["r"], name, "品名なし"))
            continue
        seen.add((name, c))
        x = {"n": name, "c": c, "y": kana.yomi(re.sub(r"（.*?）", "", name))}
        if note:
            x["d"] = note
        out.append(x)
    if bad:
        for b in bad:
            print("  ！", b)
        raise SystemExit(f"読めない行が {len(bad)} あります（NAME・CATFIX に足す）")
    rows = [json.dumps(x, ensure_ascii=False, separators=(",", ":")) for x in out]
    (m.data_dir / "items.js").write_text(
        f"// 東京都 杉並区（13115）の品目検索のデータ（{len(out)}件）\n"
        "// 杉並区の「ごみと資源の分け方・出し方『50音順』」（PDF。画像を OCR で読んだ）。tools/munis/13_tokyo/13115_suginami/make_items.py で作る\n"
        "// 1行に1品目：{n:品名, c:区分, y:読み, d:注意}\n"
        'gomiData("13115", "items", /*ITEMS-START*/[\n' + ",\n".join(rows) + "\n]/*ITEMS-END*/);\n",
        encoding="utf-8", newline="\n")
    print(f"品目 {len(out)}件 → {m.data_dir / 'items.js'}")


if __name__ == "__main__":
    main()
