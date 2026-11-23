"""京都府 京都市（26100）：e-Stat の町丁 → アプリの地区（町名）。

このファイルのきまり（tools/build_geo.py から使う）:
  town_info(towns, cal) … e-Stat の町丁（towns：名前 name・区 city・代表点 x, y・形 rings）ごとに、アプリの地区との対応を返す
                           （c：地区の候補の番号の一覧、r：地域（区））
  extra(cal)            … 自治体ぜんたいの追加データ（なければ {}）
地図（KML）は区ごとに 元データ/26_京都府/26100_京都市/地図/r2ka26101.kml〜r2ka26111.kml

e-Stat の町名は「学区＋町名」（例：待鳳紫野今宮町）なので、町名別一覧表の町名が e-Stat の町名の終わりと合うものを候補にする。
同じ町が通りの東西などで分かれているときは、両方を候補に出す。右京区の京北地域は、旧村の名前（黒田・宇津・山国・細野／周山・弓削）で地区を決める。
"""
import re


def loose(s):
    return s.translate(str.maketrans({"ヶ": "ケ", "ｹ": "ケ", "峯": "峰", "之": "ノ", "の": "ノ"}))


def town_info(towns, cal):
    by_ward = {}
    for i, a in enumerate(cal["areas"]):
        base = re.sub(r"（.*?）$", "", a["n"]) if not a["n"].startswith("京北") else a["n"]
        by_ward.setdefault(a["r"], []).append((loose(base), i, a["n"]))
    keihoku = [i for i, a in enumerate(cal["areas"]) if a["n"].startswith("京北")]
    out, miss = [], 0
    for t in towns:
        ward = t.get("city", "").replace("京都市", "")
        name = loose(t["name"])
        if ward == "右京区" and keihoku:
            # 京北地域：e-Stat の町名は旧村の名前（学区）で始まる
            if t["name"].startswith(("黒田", "宇津", "山国", "細野")):
                out.append({"c": keihoku[:1], "r": ward})
                continue
            if t["name"].startswith(("周山", "弓削")):
                out.append({"c": keihoku[1:], "r": ward})
                continue
            if "京北" in t["name"]:
                out.append({"c": keihoku, "r": ward})
                continue
        hits = [(len(b), i) for b, i, _ in by_ward.get(ward, []) if not b.startswith("京北") and name.endswith(b)]
        if hits:
            best = max(h[0] for h in hits)
            out.append({"c": [i for n, i in hits if n == best], "r": ward})
        else:
            miss += 1
            out.append({"c": [], "r": ward})
    print(f"  京都市：町名別一覧表に見つからない町丁 {miss}（候補なし。区から選んでもらう）")
    return out


def extra(cal):
    return {}
