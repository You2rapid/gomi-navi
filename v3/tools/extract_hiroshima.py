"""広島市のオープンデータ（家庭ごみ収集日程表）から、v3 アプリ用の収集日データを作る。

使い方:
    python tools/extract_hiroshima.py <CSVファイル.zip> index.html

データの入手先（広島広域都市圏・広島県オープンデータポータルサイト）:
    「家庭ごみ収集日程表（R8）」 https://hiroshima-opendata.dataeye.jp/resources/9971
    ライセンス: 公共データ利用規約（PDL1.0）… 出典を書けば商用利用も可

zip の中身:
    1-N家庭ごみ収集日（◯区）.csv … 1日1行、列がグループ（1, 2, …）、値が「可燃」「リプラ」など
    3-N◯区町名.csv                 … 町名, よみ, グループ
index.html の /*HIRO-DATA-START*/ と /*HIRO-DATA-END*/ の間を書き換える。
"""
import csv
import datetime as dt
import io
import json
import re
import sys
import zipfile
from collections import Counter, defaultdict
from pathlib import Path

WARDS = ["中区", "東区", "南区", "西区", "安佐南区", "安佐北区", "安芸区", "佐伯区"]
# CSV の値 → アプリ内の区分コード（1文字にして1日1文字の文字列に詰める）
CODE = {"可燃": "K", "リプラ": "R", "他プラ": "O", "資源": "S", "不燃": "F"}
WD = "月火水木金土日"


def zip_name(info):
    try:
        return info.filename.encode("cp437").decode("cp932")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return info.filename


def read_csv(z, info):
    raw = z.read(info)
    for enc in ("utf-8-sig", "cp932"):
        try:
            return list(csv.reader(io.StringIO(raw.decode(enc))))
        except UnicodeDecodeError:
            pass
    raise ValueError(zip_name(info))


def nth_weekday(d):
    return (d.day - 1) // 7 + 1


def derive_rule(ds):
    """収集日の並びから「毎週月・木曜日」「2週に1回 水曜日」などの基本ルールを推定する。"""
    wd = Counter(d.weekday() for d in ds)
    weekly = sorted(w for w, n in wd.items() if n >= 30)
    if weekly:
        return {"weekly": weekly}, "毎週" + "・".join(WD[w] for w in weekly) + "曜日"
    w, _ = wd.most_common(1)[0]
    same = sorted(d for d in ds if d.weekday() == w)
    gaps = Counter((b - a).days for a, b in zip(same, same[1:]))
    if gaps and gaps.most_common(1)[0][0] == 14:
        # 2週おき（祝日のあとなどで周期がずれることがあるので、日付はカレンダーで確認）
        return {"biweekly": w}, f"2週に1回 {WD[w]}曜日"
    nth = Counter((nth_weekday(d), d.weekday()) for d in ds)
    common = sorted(k for k, n in nth.items() if n >= 7)
    if common:
        w = common[0][1]
        ns = [n for n, ww in common if ww == w]
        return {"nth": ns, "wd": w}, "毎月第" + "・".join(map(str, ns)) + WD[w] + "曜日"
    return {}, ""


def main():
    if len(sys.argv) != 3:
        print(__doc__)
        sys.exit(1)
    zpath, out = Path(sys.argv[1]), Path(sys.argv[2])
    z = zipfile.ZipFile(zpath)
    files = {zip_name(i).split("/")[-1]: i for i in z.infolist() if not i.is_dir()}

    schedules, areas, start = {}, [], None
    for ward in WARDS:
        cal = next(i for n, i in files.items() if "家庭ごみ" in n and f"（{ward}）" in n)
        towns = next(i for n, i in files.items() if n.endswith(f"{ward}町名.csv") and re.match(r"3-\d", n))
        rows = read_csv(z, cal)
        groups = rows[0][2:]
        dates = [dt.date.fromisoformat(r[0].strip("#")) for r in rows[1:]]
        start = start or dates[0]
        assert dates == [dates[0] + dt.timedelta(days=i) for i in range(len(dates))], ward
        for gi, g in enumerate(groups):
            vals = [r[2 + gi].strip() if len(r) > 2 + gi else "" for r in rows[1:]]
            unknown = {v for v in vals if v and v not in CODE}
            assert not unknown, (ward, g, unknown)
            code = "".join(CODE.get(v, ".") for v in vals)
            # 広島市は2週おきの周期が年の途中でずれるため「振替」は判定しない（日付はデータどおり）
            rules = {}
            for cat in CODE:
                ds = [d for d, v in zip(dates, vals) if v == cat]
                if ds:
                    rules[cat] = derive_rule(ds)[1]
            schedules[f"{ward}{g}"] = {"rules": rules, "code": code}
        for r in read_csv(z, towns)[1:]:
            if len(r) >= 3 and r[2].strip():
                areas.append({"r": ward, "n": r[0].strip(), "s": f"{ward}{r[2].strip()}", "y": r[1].strip()})

    missing = {a["s"] for a in areas} - set(schedules)
    assert not missing, missing
    data = {"start": start.isoformat(), "year": start.year, "schedules": schedules, "areas": areas}
    js = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    text = out.read_text(encoding="utf-8")
    new, n = re.subn(r"/\*HIRO-DATA-START\*/.*?/\*HIRO-DATA-END\*/",
                     lambda m: f"/*HIRO-DATA-START*/{js}/*HIRO-DATA-END*/", text, flags=re.S)
    assert n == 1, "index.html に HIRO-DATA の目印が見つかりません"
    out.write_text(new, encoding="utf-8")
    print(f"{len(schedules)} groups / {len(areas)} towns / {len(js)//1024} KB")


if __name__ == "__main__":
    main()
