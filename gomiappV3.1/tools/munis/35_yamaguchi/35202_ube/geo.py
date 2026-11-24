"""山口県 宇部市（35202）：e-Stat の町丁 → 収集日の地区（24地区）。

宇部市の収集日の地区（東岐波・西岐波・常盤…の24地区。ふれあいセンターの地区）について、
「どの町がどの地区か」の一覧は、市のサイト・オープンデータに見つからなかった（2026-11-24。
「【宇部市】ゴミ集積所一覧」は非公開、小学校の学区は自治会の区で決まっていて町名の一覧ではない）。
市の資料より詳しくしない決まりなので、町名が地区名そのもののときだけ候補にする：
  ・大字（例：大字東岐波・大字東岐波横尾山・大字船木・大字小野瀬戸）… 「大字」のあとが地区名で始まる
  ・大字の頭に東・西・奥が付くもの（大字東万倉・大字西万倉・大字奥万倉 → 万倉、大字東吉部・大字西吉部 → 吉部）
  ・町（例：恩田町一丁目・岬町二丁目・鵜の島町・厚南北一丁目・西宇部南三丁目・黒石北二丁目）
    … 地区名＋（町）＋（北・南・中央）＋（丁目）
それ以外の町（例：北琴芝・東見初町・常盤台・大字沖宇部）は、地区の候補を出さない（人がえらぶ）。

このファイルのきまり（tools/build_geo.py から使う）:
  town_info(towns, cal) … e-Stat の町丁（towns：名前 name・代表点 x, y・形 rings）ごとに、アプリの地区との対応を返す
                           （c：地区の候補の番号の一覧）
  extra(cal)            … 自治体ぜんたいの追加データ（なければ {}）
地図（KML）は 元データ/<県>/<自治体>/地図/r2ka<自治体コード>.kml
"""
import re

CHOME = r"(?:[一二三四五六七八九十]+丁目)?"


def match(town, district):
    if town.startswith("大字"):
        rest = town[2:]
        return rest.startswith(district) or (len(district) >= 2 and re.fullmatch(rf"[東西奥]{district}", rest) is not None)
    return re.fullmatch(rf"{district}町?(?:北|南|中央)?{CHOME}", town) is not None


def town_info(towns, cal):
    names = [a["n"] for a in cal["areas"]]
    out, none = [], 0
    for t in towns:
        c = [i for i, n in enumerate(names) if match(t["name"], n)]
        # 「大字東岐波」のように長い地区名が合うときは、短い地区名（例：なし）より優先する
        if len(c) > 1:
            best = max(len(names[i]) for i in c)
            c = [i for i in c if len(names[i]) == best]
        none += not c
        out.append({"c": c})
    print(f"  宇部市：地区の候補がある町 {len(towns) - none}／{len(towns)}（町名が地区名と同じものだけ。市に町と地区の一覧がないため）")
    return out


def extra(cal):
    return {}
