"""「今いる場所から探す」用の地図データを、県ごとに作る。

使い方（gomi フォルダで実行。ふだんは tools/update_year.py から呼ばれる）:
  python gomiappV3.1/tools/build_geo.py              ← すべての県
  python gomiappV3.1/tools/build_geo.py 35           ← 県コードを指定
  python gomiappV3.1/tools/build_geo.py 35 --list    ← 確認用に「町 → 地区の候補」の一覧も出す（gomiappV3.1/geo/<県>_check.txt）

できるもの:
  gomiappV3.1/geo/<県コード>_<県>.json … その県の自治体の町丁ごとの境目（形を少し簡単にして、10万分の1度の整数・差分で保存）と、
                                 アプリの地区との対応（自治体ごとの tools/munis/<県>/<自治体>/geo.py で決める）
  gomiappV3.1/geo/index.json           … 県の一覧と範囲（アプリは、現在地をふくむ県のファイルだけを読む）

地図は e-Stat「統計地理情報システム」の境界データ（国勢調査 令和2年 小地域（町丁・字等別）、世界測地系 緯度経度、KML）。
元データ/<県>/<自治体>/地図/r2ka<自治体コード>.kml に置く（ダウンロードした .kmz は zip なので、中の .kml を取り出してこの名前にする）。
出典：政府統計の総合窓口（e-Stat）国勢調査（令和2年）町丁・字等別境界データ を加工して作成。
"""
import json
import math
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)
sys.path.insert(0, str(Path(__file__).resolve().parent / "lib"))
import munis as M  # noqa: E402
from geo import TOL, bbox, encode, parse_kml, simplify  # noqa: E402

SOURCE = "e-Stat 国勢調査（令和2年）町丁・字等別境界データを加工"


def build_pref(pref, ms, check=False):
    cities, all_towns = {}, []
    for m in ms:
        mod = m.module("geo")
        kml = m.src_dir / "地図" / f"r2ka{m.code}.kml"
        if not mod:
            print(f"  {m}：geo.py がないので、今いる場所から探すの対象外")
            continue
        if not kml.exists():
            raise SystemExit(f"{m}：地図がありません（{kml}）")
        cal = m.read("calendar")
        towns = [t for t in parse_kml(kml) if t["name"]]
        info = mod.town_info(towns, cal)
        for t in towns:
            t["rings"] = [simplify(rg, TOL) for rg in t["rings"]]
        cities[m.code] = (m, towns, info, mod.extra(cal), cal)
        all_towns += towns
    if not cities:
        return None
    xs = [p[0] for t in all_towns for r in t["rings"] for p in r]
    ys = [p[1] for t in all_towns for r in t["rings"] for p in r]
    base = [math.floor(min(xs) * 10) / 10, math.floor(min(ys) * 10) / 10]   # 座標の基準（10万分の1度の整数にするときに引く）
    out = {"base": base, "source": SOURCE, "cities": {}}
    lines = []
    for code, (m, towns, info, extra, cal) in cities.items():
        ts = [{"n": t["name"], **inf, "b": bbox(t["rings"], base), "p": [encode(rg, base) for rg in t["rings"]]} for t, inf in zip(towns, info)]
        out["cities"][code] = {"towns": ts, **extra}
        print(f"  {m}：町丁 {len(ts)}")
        for t in ts:
            if "c" in t:
                lines.append(f"{m.name} {t['n']}\t{t.get('r', '')}\t{' / '.join(cal['areas'][j]['n'] for j in t['c'])}")
    fn = f"{pref['code']}_{pref['slug']}.json"
    (M.GEO / fn).write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    if check:
        (M.GEO / f"{pref['code']}_check.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return {"code": pref["code"], "name": pref["name"], "file": fn,
            "bbox": [round(min(xs), 4), round(min(ys), 4), round(max(xs), 4), round(max(ys), 4)]}


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    M.GEO.mkdir(exist_ok=True)
    idx_path = M.GEO / "index.json"
    index = json.loads(idx_path.read_text(encoding="utf-8")) if idx_path.exists() else {"prefs": []}
    have = {p["code"]: p for p in index["prefs"]}
    for pref in M.prefs():
        if args and pref["code"] not in args:
            continue
        print(f"== {pref['name']}")
        r = build_pref(pref, [m for m in M.munis() if m.pref == pref["code"]], "--list" in sys.argv)
        if r:
            have[pref["code"]] = r
    index = {"source": SOURCE, "prefs": [have[k] for k in sorted(have)]}
    idx_path.write_text(json.dumps(index, ensure_ascii=False, indent=1), encoding="utf-8")
    print("wrote", idx_path)


if __name__ == "__main__":
    main()
