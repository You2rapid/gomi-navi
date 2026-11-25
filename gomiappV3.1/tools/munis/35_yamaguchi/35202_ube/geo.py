"""山口県 宇部市（35202）：e-Stat の町丁 → 収集日の地区（24地区）。

宇部市の収集日の地区（東岐波・西岐波・常盤…の24地区。ふれあいセンターの地区）について、
ごみの資料には「どの町がどの地区か」の一覧がない（2026-11-24。「【宇部市】ゴミ集積所一覧」は非公開）。
そこで、次の2つで地区の候補を出す（2つ以上の地区に合う町は、全部を候補にして人がえらぶ）。

1. 市の人口統計「町丁別・自治会区別住民基本台帳人口」（Excel。元データ/35_山口県/35202_宇部市/地区/jiti_YYYYMMDD.xlsx の
   いちばん新しいもの）。地区（校区）ごとのシートがごみの24地区と同じ名前で、「通称名等」の列に町名などが「、」区切りで入っている。
   e-Stat の町名を、そのまま・「○丁目」を外したもの・大字の残り（「町丁別」シートの大字の名前を外したもの。2文字以上）にして、
   通称名と「同じ」ものだけ合わせる（「吉田1区」の「1区」は外す。前方一致・部分一致はしない）。
2. 町名が地区名そのもの：
  ・大字（例：大字東岐波・大字東岐波横尾山・大字船木・大字小野瀬戸）… 「大字」のあとが地区名で始まる
  ・大字の頭に東・西・奥が付くもの（大字東万倉・大字西万倉・大字奥万倉 → 万倉、大字東吉部・大字西吉部 → 吉部）
  ・町（例：恩田町一丁目・岬町二丁目・鵜の島町・厚南北一丁目・西宇部南三丁目・黒石北二丁目）
    … 地区名＋（町）＋（北・南・中央）＋（丁目）
どちらにも合わない町（例：亀浦・今村北・床波・大字沖宇部・大字際波）は、地区の候補を出さない（人がえらぶ）。

このファイルのきまり（tools/build_geo.py から使う）:
  town_info(towns, cal) … e-Stat の町丁（towns：名前 name・代表点 x, y・形 rings）ごとに、アプリの地区との対応を返す
                           （c：地区の候補の番号の一覧）
  extra(cal)            … 自治体ぜんたいの追加データ（なければ {}）
地図（KML）は 元データ/<県>/<自治体>/地図/r2ka<自治体コード>.kml
"""
import re
import sys
import unicodedata
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "lib"))
import xlsx  # noqa: E402

CHOME = r"(?:[一二三四五六七八九十]+丁目)?"
# 市の「町丁別・自治会区別住民基本台帳人口」（Excel）。いちばん新しい jiti_YYYYMMDD.xlsx を使う
JITI_DIR = Path(__file__).resolve().parents[5] / "元データ" / "35_山口県" / "35202_宇部市" / "地区"


def norm(s):
    return unicodedata.normalize("NFKC", s).replace("ヶ", "ケ").replace("ｹ", "ケ").strip()


def match(town, district):
    """町名が地区名そのもの（大字東岐波○○ → 東岐波、恩田町一丁目 → 恩田 など）"""
    if town.startswith("大字"):
        rest = town[2:]
        return rest.startswith(district) or (len(district) >= 2 and re.fullmatch(rf"[東西奥]{district}", rest) is not None)
    return re.fullmatch(rf"{district}町?(?:北|南|中央)?{CHOME}", town) is not None


def jiti():
    """Excel → (地区ごとの通称名の集合 {地区: {名前}}, 大字の名前の一覧, ファイル名)"""
    files = sorted(JITI_DIR.glob("jiti_*.xlsx"))
    if not files:
        return {}, [], None
    sh = xlsx.sheets(files[-1])
    oaza = sorted({norm(r[0])[2:] for r in sh.get("町丁別", []) if r and norm(r[0]).startswith("大字")}, key=len, reverse=True)
    alias = {}
    for name, rows in sh.items():
        if name == "町丁別":
            continue
        names = set()
        for r in rows[3:]:
            if len(r) < 2 or not r[1]:
                continue
            for a in re.split(r"[、,，・\n]|_x000D_", r[1]):
                a = norm(a)
                a = re.sub(r"\d+区$", "", a)      # 「吉田1区」→ 吉田
                if a:
                    names.add(a)
        alias[name] = names
    return alias, oaza, files[-1].name


def keys(town, oaza):
    """e-Stat の町名から、通称名とくらべる名前：そのまま・丁目を外したもの、大字は大字の名前を外した残り"""
    t = norm(town)
    out = {t, re.sub(rf"{CHOME}$", "", t)}
    if t.startswith("大字"):
        rest = t[2:]
        out.add(rest)
        base = next((b for b in oaza if rest.startswith(b) and len(rest) > len(b)), None)
        # 大字の残りは2文字以上だけ（「大字小串浜」の「浜」が、ほかの地区の通称名「浜」に合ってしまうため）
        if base and len(rest) - len(base) >= 2:
            out.add(rest[len(base):])
    return {k for k in out if k}


def town_info(towns, cal):
    names = [a["n"] for a in cal["areas"]]
    alias, oaza, src = jiti()
    if alias and set(alias) != set(names):
        raise SystemExit(f"{src} のシート名が収集日の地区とちがいます：{sorted(set(alias) ^ set(names))}")
    out, n_name, n_alias, none = [], 0, 0, 0
    for t in towns:
        c = [i for i, n in enumerate(names) if match(t["name"], n)]
        # 「大字東岐波」のように長い地区名が合うときは、短い地区名より優先する
        if len(c) > 1:
            best = max(len(names[i]) for i in c)
            c = [i for i in c if len(names[i]) == best]
        n_name += bool(c)
        # 通称名と合う地区も足す（2つ以上の地区に出てくる町は、全部を候補にして人がえらぶ）
        ks = keys(t["name"], oaza)
        more = [i for i, n in enumerate(names) if ks & alias.get(n, set()) and i not in c]
        n_alias += bool(more) and not c
        c = sorted(c + more)
        none += not c
        out.append({"c": c})
    print(f"  宇部市：地区の候補がある町 {len(towns) - none}／{len(towns)}"
          f"（町名が地区名 {n_name}・人口統計の通称名 {n_alias}{'（' + src + '）' if src else ''}）")
    return out


def search_words(cal):
    """地区の検索用の呼び名：人口統計の Excel の自治会の通称名 → その通称名が出てくる地区（2つ以上なら全部）"""
    names = [a["n"] for a in cal["areas"]]
    alias, _, _ = jiti()
    out = {}
    for i, n in enumerate(names):
        for w in alias.get(n, ()):
            if len(w) >= 2:
                out.setdefault(w, set()).add(i)
    return {w: sorted(cs) for w, cs in out.items()}


def extra(cal):
    return {}
