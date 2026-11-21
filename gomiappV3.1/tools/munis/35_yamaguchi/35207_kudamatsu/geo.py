"""山口県 下松市（35207）：e-Stat の町丁 → 西地区・東地区。
オープンデータ「【下松市】ゴミ収集地区一覧」（CC BY 4.0。元データ/35_山口県/35207_下松市/オープンデータ/garbage_collection_area.csv）
の町名と地区から決める。「岩徳線以北／以南」で分かれる大字（切山・来巻・山田）は、2つの地区の候補を出す。
一覧は python gomiappV3.1/tools/update_opendata.py 35207 で新しくする。

このファイルのきまり（tools/build_geo.py から使う）:
  town_info(towns, cal) … e-Stat の町丁（towns：名前 name・代表点 x, y・形 rings）ごとに、アプリの地区との対応を返す
                           （c：地区の候補の番号の一覧、r：地域、side：線と関係なく決まっている地区 など）
  extra(cal)            … 自治体ぜんたいの追加データ（境目の線など。なければ {}）
地図（KML）は 元データ/<県>/<自治体>/地図/r2ka<自治体コード>.kml
"""
import re
import sys
import unicodedata
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "lib"))
import munis as M  # noqa: E402

AREA_CSV = M.munis(["35207"])[0].src_dir / "オープンデータ" / "garbage_collection_area.csv"
# 一覧と e-Stat で書き方がちがう町名（一覧 → e-Stat）
ALIAS = {"籐光町": "藤光町"}
KANJI = "〇一二三四五六七八九"


def kanji_num(s):
    """一 → 1、十二 → 12"""
    if "十" in s:
        a, _, b = s.partition("十")
        return (KANJI.index(a) if a else 1) * 10 + (KANJI.index(b) if b else 0)
    return int("".join(str(KANJI.index(ch)) for ch in s))


def area_table():
    """一覧 → [(町名, 丁目の集合 or None, 地区)]"""
    import csv, io
    raw = AREA_CSV.read_bytes()
    text = next(raw.decode(e) for e in ("utf-8-sig", "cp932") if _ok(raw, e))
    out = []
    for r in csv.DictReader(io.StringIO(text)):
        name = unicodedata.normalize("NFKC", r["ゴミの収集地区_地区名"]).replace("(大字)", "大字")
        name = re.sub(r"\s*岩徳線以[北南]$", "", name).strip()
        district = r["ゴミの収集地区_収集地区"].strip()
        m = re.match(r"^(.*?)(\d+)(?:丁目)?(?:([・~～])(\d+))?丁目$", name)
        if m:
            base, a = m.group(1), int(m.group(2))
            b = int(m.group(4)) if m.group(4) else a
            chome = set(range(a, b + 1)) if m.group(3) in ("~", "～") else {a, b}
        else:
            base, chome = name, None
        out.append((ALIAS.get(base, base), chome, district))
    return out


def _ok(raw, enc):
    try:
        raw.decode(enc)
        return True
    except UnicodeDecodeError:
        return False


def town_info(towns, cal):
    idx = {a["n"]: i for i, a in enumerate(cal["areas"])}
    table = area_table()
    out, missing = [], []
    for t in towns:
        m = re.match(rf"^(.*?)([{KANJI}十]+)丁目$", t["name"])
        base, n = (m.group(1), kanji_num(m.group(2))) if m else (t["name"], None)
        found = sorted({d for b, ch, d in table if b == base and (ch is None or n in ch)}, key=lambda d: idx[d])
        if not found:
            missing.append(t["name"])
        out.append({"c": [idx[d] for d in found]})
    if missing:
        print("  ！ 下松市：収集地区一覧に見つからない町：" + "、".join(sorted(set(missing))))
    return out


def extra(cal):
    return {}
