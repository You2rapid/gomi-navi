"""高知県 高知市（39201）：e-Stat の町丁 → アプリの地区（大街）。

このファイルのきまり（tools/build_geo.py から使う）:
  town_info(towns, cal) … e-Stat の町丁（towns：名前 name・代表点 x, y・形 rings）ごとに、アプリの地区との対応を返す（c：地区の候補の番号の一覧）
  extra(cal)            … 自治体ぜんたいの追加データ（なければ {}）
  search_words(cal)     … 検索用の町名に足す呼び名 {呼び名: [地区の番号, …]}
地図（KML）は 元データ/39_高知県/39201_高知市/地図/r2ka39201.kml

町と地区（大街）の対応は、市の「高知市大街別町名一覧」（calendar.py が地区の説明 d に町名を入れている）で決める（決まり A1）。
e-Stat の町名は「朝倉本町一丁目」「仁井田（その一）」のように丁目や（その○）が付くので、取ってからくらべる。
大街別町名一覧の町名が e-Stat とちがう書き方のもの（槙山町／槇山町、春野町南ヶ丘…丁目など）は、表記ゆれをそろえてくらべる。
"""
import re

# 地区名がそのまま町名ではない（大街の名前）ので、検索用の町名（towns.js）を作る（手順書の決まり B2）
TOWN_SEARCH = True

KANJI_NUM = "一二三四五六七八九十"


def loose(s):
    """表記ゆれをそろえる（槙・槇、ケ・ヶ）"""
    return s.translate(str.maketrans({"槇": "槙", "ヶ": "ケ", "ｹ": "ケ"}))


def base_name(n):
    """「朝倉本町一丁目」→ 朝倉本町、「仁井田（その一）」→ 仁井田"""
    n = re.sub(r"（その.）$", "", n)
    return re.sub(rf"[{KANJI_NUM}]+丁目$", "", n)


def town_index(cal):
    """{町名（そろえた形）: [地区の番号, …]}。地区の説明 d は「町名、町名、…」か「○○のうち町名」"""
    idx = {}
    for i, a in enumerate(cal["areas"]):
        d = a.get("d", "")
        names = [d.split("のうち", 1)[1]] if "のうち" in d else d.split("、")
        for t in names:
            idx.setdefault(loose(t), []).append(i)
    # 「南街（弘化台を除く）」のように、ほかの地区に移した町は、移した先の地区だけにする
    return idx


def town_info(towns, cal):
    idx = town_index(cal)
    out, miss = [], []
    for t in towns:
        c = idx.get(loose(base_name(t["name"])), [])
        if not c:
            miss.append(t["name"])
        out.append({"c": c})
    print(f"  高知市：大街別町名一覧に見つからない町丁 {len(miss)}／{len(towns)}（{'・'.join(miss)}）")
    return out


def extra(cal):
    return {}


def search_words(cal):
    """大街別町名一覧の町名（e-Stat にない町名も、市の資料にあるので探せるようにする）"""
    return town_index(cal)
