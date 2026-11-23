"""全国の郵便番号一覧を、県ごとのファイルに分けて作る（郵便番号から自治体と町を探す用）。

使い方（gomi フォルダで実行）:
  python gomiappV3.1/tools/build_zip.py              ← 元データにある一番新しい郵便番号データから作る
  python gomiappV3.1/tools/build_zip.py --download   ← 日本郵便から最新のデータをダウンロードしてから作る

元のデータは日本郵便「住所の郵便番号（1レコード1行、UTF-8形式）」utf_ken_all.zip（毎月末ごろ更新）。
  https://www.post.japanpost.jp/service/search/zipcode/download/utf-zip.html
保存先：元データ/全国/郵便番号/<更新日>/utf_ken_all.zip（と、中の utf_ken_all.csv）
日本郵便は郵便番号データの著作権を主張せず、自由に配布してよいとしている（utf-readme.html）。

できるもの:
  gomiappV3.1/zip/<県コード>_<県>.json … その県の郵便番号の一覧
      "cities": {自治体コード: {"n": 市区町村名, "k": 読み}}
      "zips":   {郵便番号7けた: [{"c": 自治体コード, "t": 町域名, "k": 読み, "s": かっこの中（あるときだけ）, "x": 特別な行（あるときだけ）}]}
         1つの郵便番号に町がいくつもあるときは、リストに複数入る。
         同じ町でも丁目や番地で郵便番号が分かれるときは、それぞれの郵便番号に入る（"s" にどの丁目か書いてある）。
         "x" は町を決められない行： "rest"＝その市の「以下に掲載がない場合」、"banchi"＝市の次にすぐ番地がくる、"all"＝市（町・村）全体が1つの番号
           （これらの行は "t" を空にしている）
  gomiappV3.1/zip/index.json         … 県の一覧（ファイル名・件数）と、郵便番号の上3けた → 県コード（アプリはこれで読む県のファイルを決める）
"""
import csv
import io
import json
import re
import sys
import zipfile
from datetime import date
from pathlib import Path
from urllib.request import Request, urlopen

sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)

ROOT = Path(__file__).resolve().parents[2]
SRC_DIR = ROOT / "元データ" / "全国" / "郵便番号"
OUT_DIR = ROOT / "gomiappV3.1" / "zip"
URL = "https://www.post.japanpost.jp/service/search/zipcode/download/utf/zip/utf_ken_all.zip"
SOURCE = "日本郵便 郵便番号データ（住所の郵便番号 1レコード1行 UTF-8形式）を加工"

PREFS = [
    ("01", "北海道", "hokkaido"), ("02", "青森県", "aomori"), ("03", "岩手県", "iwate"), ("04", "宮城県", "miyagi"),
    ("05", "秋田県", "akita"), ("06", "山形県", "yamagata"), ("07", "福島県", "fukushima"), ("08", "茨城県", "ibaraki"),
    ("09", "栃木県", "tochigi"), ("10", "群馬県", "gunma"), ("11", "埼玉県", "saitama"), ("12", "千葉県", "chiba"),
    ("13", "東京都", "tokyo"), ("14", "神奈川県", "kanagawa"), ("15", "新潟県", "niigata"), ("16", "富山県", "toyama"),
    ("17", "石川県", "ishikawa"), ("18", "福井県", "fukui"), ("19", "山梨県", "yamanashi"), ("20", "長野県", "nagano"),
    ("21", "岐阜県", "gifu"), ("22", "静岡県", "shizuoka"), ("23", "愛知県", "aichi"), ("24", "三重県", "mie"),
    ("25", "滋賀県", "shiga"), ("26", "京都府", "kyoto"), ("27", "大阪府", "osaka"), ("28", "兵庫県", "hyogo"),
    ("29", "奈良県", "nara"), ("30", "和歌山県", "wakayama"), ("31", "鳥取県", "tottori"), ("32", "島根県", "shimane"),
    ("33", "岡山県", "okayama"), ("34", "広島県", "hiroshima"), ("35", "山口県", "yamaguchi"), ("36", "徳島県", "tokushima"),
    ("37", "香川県", "kagawa"), ("38", "愛媛県", "ehime"), ("39", "高知県", "kochi"), ("40", "福岡県", "fukuoka"),
    ("41", "佐賀県", "saga"), ("42", "長崎県", "nagasaki"), ("43", "熊本県", "kumamoto"), ("44", "大分県", "oita"),
    ("45", "宮崎県", "miyazaki"), ("46", "鹿児島県", "kagoshima"), ("47", "沖縄県", "okinawa"),
]


def download():
    req = Request(URL, headers={"User-Agent": "Mozilla/5.0 (gomi-calendar data tool)"})
    with urlopen(req, timeout=60) as r:
        data = r.read()
        mod = r.headers.get("Last-Modified")
    # 日付は日本郵便のファイルの更新日（わからなければ今日）
    from email.utils import parsedate_to_datetime
    day = parsedate_to_datetime(mod).date() if mod else date.today()
    d = SRC_DIR / day.isoformat()
    d.mkdir(parents=True, exist_ok=True)
    (d / "utf_ken_all.zip").write_bytes(data)
    print(f"ダウンロード：{d / 'utf_ken_all.zip'}（{len(data):,} バイト）")
    return d


def latest():
    ds = sorted(p for p in SRC_DIR.glob("*") if (p / "utf_ken_all.zip").exists()) if SRC_DIR.exists() else []
    if not ds:
        raise SystemExit(f"郵便番号データがありません。--download をつけて実行してください（保存先 {SRC_DIR}）")
    return ds[-1]


def read_rows(d):
    with zipfile.ZipFile(d / "utf_ken_all.zip") as z:
        name = next(n for n in z.namelist() if n.lower().endswith(".csv"))
        text = z.read(name).decode("utf-8")
    return list(csv.reader(io.StringIO(text)))


def special(town, city):
    """町を決められない行なら種類を返す。"""
    if town == "以下に掲載がない場合":
        return "rest"
    if town.endswith("の次に番地がくる場合"):
        return "banchi"
    # 「利島村一円」のような市町村全体の行（滋賀県多賀町の「一円」は本当の町名なので、市町村名で始まるものだけ）
    if town.endswith("一円") and len(town) > 2 and city.endswith(town[:-2]):
        return "all"
    return None


PAREN = re.compile(r"^(.*?)（(.*)）$")


def main():
    d = download() if "--download" in sys.argv else latest()
    print(f"元データ：{d}")
    rows = read_rows(d)
    names = {c: (n, s) for c, n, s in PREFS}
    prefs = {c: {"cities": {}, "zips": {}} for c, _, _ in PREFS}
    head3 = {}
    problems = []
    for r in rows:
        if len(r) < 15:
            problems.append(f"列が足りない行：{r}")
            continue
        code, z7, city_k, town_k, pref_n, city, town = r[0], r[2], r[4], r[5], r[6], r[7], r[8]
        if r[13] == "2":   # 廃止のデータ
            continue
        pc = code[:2]
        if pc not in prefs or names[pc][0] != pref_n:
            problems.append(f"県が合わない行：{r}")
            continue
        p = prefs[pc]
        p["cities"].setdefault(code, {"n": city, "k": city_k})
        e = {"c": code}
        x = special(town, city)
        if x:
            e.update({"t": "", "k": "", "x": x})
        else:
            m = PAREN.match(town)
            mk = PAREN.match(town_k)
            if m:
                e.update({"t": m.group(1), "k": mk.group(1) if mk else town_k, "s": m.group(2)})
            else:
                e.update({"t": town, "k": town_k})
        lst = p["zips"].setdefault(z7, [])
        if e not in lst:
            lst.append(e)
        head3.setdefault(z7[:3], set()).add(pc)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    updated = d.name
    index = {"source": SOURCE, "updated": updated, "prefs": [], "head3": {}}
    total = 0
    for c, n, s in PREFS:
        p = prefs[c]
        f = f"{c}_{s}.json"
        out = {"pref": c, "name": n, "source": SOURCE, "updated": updated,
               "cities": dict(sorted(p["cities"].items())), "zips": dict(sorted(p["zips"].items()))}
        (OUT_DIR / f).write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
        nz = len(p["zips"])
        total += nz
        index["prefs"].append({"code": c, "name": n, "file": f, "zips": nz, "cities": len(p["cities"])})
        print(f"  {c} {n}：郵便番号 {nz:,}、市区町村 {len(p['cities'])}")
    # 上3けたが2つ以上の県にまたがることがあるので、県コードはリストにする
    index["head3"] = {h: sorted(v) for h, v in sorted(head3.items())}
    (OUT_DIR / "index.json").write_text(json.dumps(index, ensure_ascii=False, indent=1), encoding="utf-8")
    multi = {h: v for h, v in index["head3"].items() if len(v) > 1}
    print(f"全国：郵便番号 {total:,}（元の行 {len(rows):,}）。上3けたが県をまたぐもの {len(multi)}：{multi}")
    for pr in problems[:20]:
        print("  確かめること：", pr)
    print(f"確かめること {len(problems)}件")


if __name__ == "__main__":
    main()
