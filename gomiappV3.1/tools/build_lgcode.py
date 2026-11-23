"""全国地方公共団体コード（都道府県・市区町村の番号）の一覧を作る。データ管理の元にする。

使い方（gomi フォルダで実行）:
  python gomiappV3.1/tools/build_lgcode.py

元のデータは総務省「全国地方公共団体コード」の Excel（市町村の合併・名前の変更があると更新される）。
  https://www.soumu.go.jp/denshijiti/code.html
  ・都道府県コード及び市区町村コード（例：000925835.xlsx）… 今ある団体と、政令指定都市の区
  ・改正一覧表（例：000875488.xlsx）… 平成17年4月1日からの合併・名前の変更など
保存先：元データ/全国/地方公共団体コード/<いつ現在か>/ に、ファイル名に「改正一覧」を入れずに団体の表、入れて改正一覧を置く。
新しい表が出たら、新しい日付のフォルダを作って置き、このスクリプトを実行しなおす（一番新しいフォルダを使う）。
利用条件：総務省のホームページは「公共データ利用規約（第1.0版）」（出典を書けば商用でも使える）。

できるもの:
  元データ/全国/地方公共団体コード/lgcode.json … プログラム（道具）で使う一覧（このパソコンだけ。アプリでは使わない）
      "prefs":   [{"code": "35", "name": "山口県", "yomi": "やまぐちけん"}]
      "munis":   [{"code": 5けた, "code6": 検査数字つき6けた, "pref": 県コード, "name": 名前, "yomi": よみ, "kind": 種類,
                   "gun": 郡（町村だけ）, "city": 政令指定都市の区のときは市のコード}]
         kind … "city"＝市、"designated"＝政令指定都市、"ward"＝政令指定都市の区、"special"＝東京23区、"town"＝町、"village"＝村
      "history": [{"date": 日付, "pref": 県コード, "reason": 理由, "old": [{"code","name","yomi","gone"}], "new": [{"code","name","yomi"}]}]
      "moved":   {なくなったコード: [いまのコード, ...]}   古いデータのコードを今のコードに読みかえるときに使う
  元データ/全国/地方公共団体コード/lgcode.csv  … Excel で見る用（同じ一覧に、アプリで使っているかの列をつけたもの）
"""
import csv
import json
import re
import sys
import unicodedata
from datetime import date, timedelta
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)
sys.path.insert(0, str(Path(__file__).resolve().parent / "lib"))
import munis as M  # noqa: E402
import xlsx  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
SRC_DIR = ROOT / "元データ" / "全国" / "地方公共団体コード"
APP = ROOT / "gomiappV3.1"
OUT_JSON = SRC_DIR / "lgcode.json"
OUT_CSV = SRC_DIR / "lgcode.csv"
ZIP_DIR = APP / "zip"
SOURCE = "総務省「全国地方公共団体コード」（都道府県コード及び市区町村コード・改正一覧表）を加工"
KIND_JA = {"pref": "都道府県", "city": "市", "designated": "政令指定都市", "ward": "区（政令指定都市）",
           "special": "特別区", "town": "町", "village": "村"}


def hira(s):
    """半角カナ・カタカナ → ひらがな"""
    s = unicodedata.normalize("NFKC", s)
    return "".join(chr(ord(c) - 0x60) if "ァ" <= c <= "ヶ" else c for c in s)


def check_digit(c5):
    total = sum(int(d) * w for d, w in zip(c5, (6, 5, 4, 3, 2)))
    return str((11 - total % 11) % 10)


ERA = {"H": 1988, "R": 2018, "S": 1925}


def to_date(v):
    v = (v or "").strip()
    if not v:
        return ""
    m = re.fullmatch(r"([HRS])(\d+)\.(\d+)\.(\d+)", v)
    if m:
        return date(ERA[m.group(1)] + int(m.group(2)), int(m.group(3)), int(m.group(4))).isoformat()
    if re.fullmatch(r"\d+(\.0)?", v):   # Excel の日付（1899-12-30 からの日数）
        return (date(1899, 12, 30) + timedelta(days=int(float(v)))).isoformat()
    return v


def latest():
    ds = sorted(p for p in SRC_DIR.glob("*") if p.is_dir() and list(p.glob("*.xlsx"))) if SRC_DIR.exists() else []
    if not ds:
        raise SystemExit(f"総務省の Excel がありません（{SRC_DIR}/<日付>/ に置いてください）")
    d = ds[-1]
    lists = [p for p in d.glob("*.xlsx") if "改正一覧" not in p.name]
    hist = [p for p in d.glob("*.xlsx") if "改正一覧" in p.name]
    if len(lists) != 1:
        raise SystemExit(f"{d}：団体の表（改正一覧ではない .xlsx）を1つだけ置いてください")
    return d, lists[0], (hist[0] if hist else None)


def read_list(path, problems):
    sh = xlsx.sheets(path)
    main = next(v for k, v in sh.items() if "政令" not in k)
    desig = next((v for k, v in sh.items() if "政令" in k), [])
    prefs, munis = [], {}
    for r in main[1:]:
        if not r or not re.fullmatch(r"\d{6}", r[0]):
            continue
        c6, pref_n, name, pref_k, kana = (r + [""] * 5)[:5]
        c5 = c6[:5]
        if check_digit(c5) != c6[5]:
            problems.append(f"検査数字が合わない：{c6} {pref_n}{name}")
        if not name:
            prefs.append({"code": c5[:2], "name": pref_n, "yomi": hira(pref_k)})
            continue
        if c5[:2] == "13" and "101" <= c5[2:] <= "123":
            kind = "special"
        else:
            kind = {"市": "city", "町": "town", "村": "village"}.get(name[-1])
            if not kind:
                problems.append(f"市町村の種類がわからない：{c6} {name}")
        munis[c5] = {"code": c5, "code6": c6, "pref": c5[:2], "name": name, "yomi": hira(kana), "kind": kind}
    cities = {}
    for r in desig[1:]:
        if not r or not re.fullmatch(r"\d{6}", r[0]):
            continue
        c6, _, name, _, kana = (r + [""] * 5)[:5]
        c5 = c6[:5]
        if check_digit(c5) != c6[5]:
            problems.append(f"検査数字が合わない：{c6} {name}")
        if c5 in munis:   # 市そのもの
            munis[c5]["kind"] = "designated"
            cities[c5] = munis[c5]["name"]
            continue
        city = next((c for c, n in cities.items() if name.startswith(n) and c[:2] == c5[:2]), None)
        if not city:
            problems.append(f"区の市がわからない：{c6} {name}")
        munis[c5] = {"code": c5, "code6": c6, "pref": c5[:2], "name": name, "yomi": hira(kana), "kind": "ward", "city": city}
    return prefs, munis


def read_history(path, codes):
    """改正一覧表を、1つの出来事（合併・市制など）ごとにまとめる。県名が書いてある行から次の出来事。"""
    rows = xlsx.sheets(path)
    rows = next(iter(rows.values()))
    events, prev, pref = [], [""] * 14, ""
    for r in rows[4:]:
        r = (r + [""] * 14)[:14]
        r = [prev[i] if v == "〃" else v for i, v in enumerate(r)]
        prev = r
        if not any(r[4:13]):
            continue
        if r[4]:
            pref = r[4]
            events.append({"pref_name": pref, "rows": []})
        events[-1]["rows"].append(r)
    out = []
    for ev in events:
        old, new, reason, day = [], [], [], ""
        for r in ev["rows"]:
            oc, on, ok, mark, nc, nn, nk, why, when = r[5], r[6], r[7], r[8], r[9], r[10], r[11], r[12], r[13]
            if why:
                reason.append(why.replace("\n", ""))
            day = day or to_date(when)
            if re.fullmatch(r"\d{6}", oc):
                gone = mark == "欠番"
                old.append({"code": oc[:5], "name": on, "yomi": ok, "gone": gone})
                if not gone:   # 同左（コードは変わらない。名前だけ変わることがある）
                    new.append({"code": oc[:5], "name": on if nn in ("同左", "") else nn, "yomi": ok if nk in ("同左", "") else nk})
            if re.fullmatch(r"\d{6}", nc):
                new.append({"code": nc[:5], "name": nn, "yomi": nk})
        pc = next((c for c, n in codes.items() if n == ev["pref_name"]), "")
        out.append({"date": day, "pref": pc, "reason": "".join(dict.fromkeys(reason)), "old": old, "new": new})
    return out


def moved_codes(history, munis):
    """なくなったコード → 今のコード。古い順に読み、そのあとまたなくなったら先までたどる。"""
    moved = {}
    for ev in sorted(history, key=lambda e: e["date"]):
        gone = [o["code"] for o in ev["old"] if o["gone"]]
        to = [n["code"] for n in ev["new"]]
        # 政令指定都市になったときなどは区もいっしょにできるので、区でないもの（市）があれば市にする
        main = [c for c in to if not (c in munis and munis[c]["kind"] == "ward")]
        to = main or to
        for g in gone:
            if g not in to:
                moved[g] = to
    def follow(c, seen=()):
        if c in munis or c not in moved or c in seen:
            return [c]
        return list(dict.fromkeys(x for t in moved[c] for x in follow(t, seen + (c,))))
    return {c: follow(c) for c in sorted(moved)}


def add_gun(munis, problems):
    """郵便番号データの市区町村名（「猿島郡境町」など）から郡を入れ、郵便番号データとも照らし合わせる。"""
    if not ZIP_DIR.exists():
        problems.append("郵便番号データ（zip/）がないので、郡が入らず、照らし合わせもできません（build_zip.py を先に）")
        return
    seen = set()
    for f in sorted(ZIP_DIR.glob("[0-9][0-9]_*.json")):
        for c, v in json.loads(f.read_text(encoding="utf-8"))["cities"].items():
            seen.add(c)
            m = munis.get(c)
            if not m:
                problems.append(f"郵便番号データにあるのに、コード表にない：{c} {v['n']}")
                continue
            n = v["n"]
            if n == m["name"]:
                continue
            head = n[: -len(m["name"])] if n.endswith(m["name"]) else ""
            if head.endswith("郡") and m["kind"] in ("town", "village"):
                m["gun"] = head
            else:
                problems.append(f"郵便番号データと名前がちがう：{c} コード表「{m['name']}」郵便「{n}」")
    for c, m in munis.items():
        # 政令指定都市そのものは、郵便番号データでは区に分かれている
        if c not in seen and m["kind"] != "designated":
            problems.append(f"コード表にあるのに、郵便番号データにない：{c} {m['name']}")


def main():
    d, list_path, hist_path = latest()
    print(f"元データ：{d}")
    problems = []
    prefs, munis = read_list(list_path, problems)
    add_gun(munis, problems)
    pref_names = {p["code"]: p["name"] for p in prefs}
    history = read_history(hist_path, pref_names) if hist_path else []
    moved = moved_codes(history, munis)
    for c, to in moved.items():
        if any(t not in munis for t in to):
            problems.append(f"なくなったコードの行き先が今の表にない：{c} → {to}")

    # アプリで使っている自治体と照らし合わせる
    app = {m.code: m for m in M.munis()}
    for c, m in app.items():
        x = munis.get(c)
        if not x:
            problems.append(f"アプリの自治体がコード表にない：{c} {m.name}")
        elif x["name"] != m.name or (m.yomi and x["yomi"] != m.yomi):
            problems.append(f"アプリの名前・よみがコード表とちがう：{c} アプリ「{m.name}（{m.yomi}）」表「{x['name']}（{x['yomi']}）」")

    order = ["code", "code6", "pref", "name", "yomi", "kind", "gun", "city"]
    ms = [{k: m[k] for k in order if m.get(k)} for _, m in sorted(munis.items())]
    out = {"source": SOURCE, "updated": d.name, "prefs": prefs, "munis": ms, "history": history, "moved": moved}
    OUT_JSON.write_text(json.dumps(out, ensure_ascii=False, indent=0).replace("\n", "").replace(",{", ",\n{").replace("[{", "[\n{"),
                        encoding="utf-8")
    with OUT_CSV.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["コード", "コード（6けた）", "都道府県", "種類", "郡", "名前", "よみ", "政令指定都市", "アプリ"])
        for p in prefs:
            w.writerow([p["code"] + "000", p["code"] + "000" + check_digit(p["code"] + "000"), p["name"], "都道府県", "", p["name"], p["yomi"], "", ""])
        for m in ms:
            w.writerow([m["code"], m["code6"], pref_names[m["pref"]], KIND_JA.get(m["kind"], ""), m.get("gun", ""), m["name"], m["yomi"],
                        munis[m["city"]]["name"] if m.get("city") else "", "使っている" if m["code"] in app else ""])

    count = {k: sum(m["kind"] == k for m in ms) for k in KIND_JA if k != "pref"}
    print(f"都道府県 {len(prefs)}、" + "、".join(f"{KIND_JA[k]} {v}" for k, v in count.items()))
    print(f"改正の出来事 {len(history)}（{history[-1]['date'] if history else ''}〜）、なくなったコード {len(moved)}")
    print(f"できたもの：{OUT_JSON.relative_to(ROOT)}、{OUT_CSV.relative_to(ROOT)}")
    for p in problems:
        print("  確かめること：", p)
    print(f"確かめること {len(problems)}件")


if __name__ == "__main__":
    main()
