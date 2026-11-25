"""京都府 宇治市（26204）：e-Stat の町丁 → アプリの地区（1〜15地区）。

このファイルのきまり（tools/build_geo.py から使う）:
  town_info(towns, cal) … e-Stat の町丁（towns：名前 name・代表点 x, y・形 rings）ごとに、アプリの地区との対応を返す（c：地区の候補の番号の一覧）
  extra(cal)            … 自治体ぜんたいの追加データ（なければ {}）
  search_words(cal)     … 検索用の町名に足す呼び名 {呼び名: [地区の番号, …]}
地図（KML）は 元データ/26_京都府/26204_宇治市/地図/r2ka26204.kml

町と地区の対応は、市の「収集地区検索表」（ごみ収集カレンダーのページ。calendar.py の read_districts で読む）で決める（決まり A1）。
表は「地区｜大字｜小字（地域）」。e-Stat の町名は「木幡赤塚」のように大字＋小字なので、大字と小字に分けてくらべる。
  ・小字が書いてあれば、その小字の町だけ（「ＪＲ以東の正中」「熊小路〈熊小路町内会除く〉」のような書き方は、正中・熊小路として、
    書いてある地区をすべて候補にする。線路や町内会で分かれる所は、e-Stat の町の形では分けられないので、使う人にえらんでもらう）
  ・「全域」「ＪＲ以北」のように大字だけのものは、その大字のすべての町（〈東垣内除く〉・「外及び大島除く」の小字は除く）
表にない町（例：木幡北山、宇治山王）は、地区を決めない（推測しない）。
"""
import importlib.util
import re
import unicodedata
from pathlib import Path

TOWN_SEARCH = True     # 地区名が「1地区」なので、町名で探せるようにする（手順書の決まり B2）
HERE = Path(__file__).resolve().parent
KANJI_NUM = "一二三四五六七八九十"
LINE = r"(?:JR|京阪|近鉄|府道|都計道路|伊勢田通|堂ノ川|弥陀次郎川)以[東西南北]"


def _cal_module():
    spec = importlib.util.spec_from_file_location("uji_calendar", HERE / "calendar.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def loose(s):
    """表記ゆれをそろえる（峯・峰、ケ・ヶ、槙・槇、全角・半角）"""
    s = unicodedata.normalize("NFKC", s)
    return s.translate(str.maketrans({"峯": "峰", "ヶ": "ケ", "槙": "槇"}))


def split_top(s, seps="、"):
    out, depth, buf = [], 0, ""
    for ch in s:
        if ch in "〈(（":
            depth += 1
        elif ch in "〉)）":
            depth -= 1
        if ch in seps and depth == 0:
            out.append(buf)
            buf = ""
        else:
            buf += ch
    return [x for x in out + [buf] if x]


def parse_entry(e):
    """小字の書き方 1つ → (小字の一覧, 除く小字の一覧)。大字ぜんたいなら小字の一覧は None"""
    e = loose(e)
    ex = []
    m = re.search(r"〈(.*?)〉", e)
    note = m[1] if m else ""
    e = re.sub(r"〈.*?〉", "", e)
    if e in ("全域",) or re.fullmatch(LINE, e):
        # 「JR以東〈東垣内除く〉」：大字ぜんたい（除く小字あり）
        m2 = re.fullmatch(r"(.+?)除く", note)
        if m2 and not re.search(r"町内会|自治会|以[東西南北]", m2[1]):
            ex = [m2[1]]
        return None, ex
    m3 = re.fullmatch(r"(.+?)除く", e)
    if m3:      # 「外及び大島除く」
        return None, re.split(r"及び|・", m3[1])
    e = re.sub(rf"^(?:{LINE})(?:で{LINE})?の", "", e)
    e = re.sub(r"の一部$", "", e)
    return [x for x in re.split(r"・|及び", e) if x], ex


def area_index(cal):
    """{大字: {"whole": [(地区の番号, 除く小字)], "part": {小字: [地区の番号]}}}"""
    mod = _cal_module()
    src = Path(__file__).resolve().parents[5] / "元データ" / "26_京都府" / "26204_宇治市" / f"{cal['year']}年度" / "ごみ収集カレンダー.html"
    dists = mod.read_districts(src)
    names = [a["n"] for a in cal["areas"]]
    idx = {}
    for n, rows in dists.items():
        i = names.index(f"{n}地区")
        for oaza, koaza in rows:
            o = idx.setdefault(loose(oaza), {"whole": [], "part": {}})
            for e in split_top(koaza):
                ks, ex = parse_entry(e)
                if ks is None:
                    o["whole"].append((i, [loose(x) for x in ex]))
                else:
                    for k in ks:
                        o["part"].setdefault(loose(k), []).append(i)
    return idx


def split_name(name, idx):
    """e-Stat の町名 → (大字, 小字)。大字は表にあるもののうち、いちばん長く合うもの"""
    n = loose(name)
    oz = max((o for o in idx if n.startswith(o)), key=len, default=None)
    if not oz:
        return None, None
    k = n[len(oz):]
    k = re.sub(rf"[{KANJI_NUM}]+丁目$", "", k)
    return oz, k


def candidates(name, idx):
    oz, k = split_name(name, idx)
    if not oz:
        return []
    o = idx[oz]
    c = list(o["part"].get(k, []))
    for i, ex in o["whole"]:
        if k not in ex:
            c.append(i)
    return sorted(set(c))


def town_info(towns, cal):
    idx = area_index(cal)
    out, miss, multi = [], [], 0
    for t in towns:
        c = candidates(t["name"], idx)
        if not c:
            miss.append(t["name"])
        elif len(c) > 1:
            multi += 1
        out.append({"c": c})
    print(f"  宇治市：収集地区検索表に見つからない町丁 {len(miss)}／{len(towns)}（{'・'.join(sorted(set(miss)))}）、地区の候補が2つ以上 {multi}")
    return out


def extra(cal):
    return {}


def search_words(cal):
    """収集地区検索表の大字・小字（「木幡赤塚」「赤塚」のどちらでも探せるように）"""
    idx = area_index(cal)
    out = {}
    for oz, o in idx.items():
        for k, cs in o["part"].items():
            out.setdefault(oz + k, set()).update(cs)
            out.setdefault(k, set()).update(cs)
        whole = [i for i, _ in o["whole"]]
        if whole:
            out.setdefault(oz, set()).update(whole)
    return {k: sorted(v) for k, v in out.items()}
