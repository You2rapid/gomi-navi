"""新しい年度のごみ収集カレンダーなどを、市のサイトから 元データ/<年度>年度/ にダウンロードする。

使い方（gomi フォルダで実行）:
  python v3/tools/download_sources.py 2027          ← 令和9年度のファイルを保存
  python v3/tools/download_sources.py 2027 --list   ← 見つかったファイルの一覧だけ出す（保存しない）

市のサイトのページから、年度の入ったリンク（例：「令和9年度ごみ収集カレンダー（徳山）」「r9nishia4.pdf」）を探す。
見つからないときは、まだ新しい年度のカレンダーが出ていないか、市のページのつくりが変わっている。
そのときは、下の「ダウンロード元」のページをブラウザで開いて、手で保存する
（保存する名前は tools/update_year.py の CITIES と、tools/年度更新の手順.md を参照）。
"""
import html
import re
import sys
import time
import urllib.request
from pathlib import Path
from urllib.parse import urljoin

sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)
sys.path.insert(0, str(Path(__file__).resolve().parent))
from datafile import ROOT  # noqa: E402

UA = {"User-Agent": "Mozilla/5.0 (gomi-calendar updater)"}
# ダウンロード元
HOLIDAY_CSV = "https://www8.cao.go.jp/chosei/shukujitsu/syukujitsu.csv"          # 内閣府「国民の祝日」
SHUNAN_INDEX = "https://www.city.shunan.lg.jp/soshiki/19/"                        # 周南市 リサイクル推進課
SHUNAN_PAGES = {"徳山": "tokuyama.html", "新南陽": "shinnanyo.html", "熊毛": "kumage.html", "鹿野": "kano.html"}
SHUNAN_PDFS = {  # (どのページ, リンクの文字) → 保存する名前
    ("徳山", "A日程"): "A.pdf", ("徳山", "B日程"): "B.pdf", ("徳山", "C日程"): "C.pdf", ("徳山", "D日程"): "D.pdf",
    ("徳山", "E日程"): "E.pdf", ("徳山", "F日程"): "F.pdf", ("徳山", "G日程"): "G.pdf", ("徳山", "H日程"): "H.pdf",
    ("徳山", "大津島"): "otsushima.pdf", ("徳山", "徳山山間"): "tokuyama_sankan.pdf", ("新南陽", "和田山間"): "wada_sankan.pdf",
}
KUDAMATSU_PAGE = "https://www.city.kudamatsu.lg.jp/kankyou/seikatsu/kankyou/kannrikakari/gomikarenda.html"
HIKARI_PAGE = "https://www.city.hikari.lg.jp/kurashi_tetsuzuki/gomi/bunbetu/8851.html"
HIKARI_KEYS = ["murozumi", "mitsui", "shimata", "asaekita", "asaeminami", "mishima", "yamato"]


def get(url):
    time.sleep(0.5)   # 市のサーバーに負担をかけないよう、少し間をあける
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60) as r:
        return r.read()


def text(raw):
    for enc in ("utf-8", "cp932"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            pass
    return raw.decode("utf-8", "replace")


def links(page_html, base):
    out = []
    for href, label in re.findall(r'<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>', page_html, re.S):
        label = re.sub(r"<[^>]+>|\s+", " ", html.unescape(label)).strip()
        out.append((urljoin(base, html.unescape(href)), label))
    return out


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if not args:
        raise SystemExit(__doc__)
    year = int(args[0]); reiwa = year - 2018
    only_list = "--list" in sys.argv
    dest = ROOT / "元データ" / f"{year}年度"
    todo, problems = [], []   # (URL, 保存先, 生のHTMLを保存するなら中身)

    # 祝日
    todo.append((HOLIDAY_CSV, dest / "祝日" / "syukujitsu.csv", None))

    # 周南市：課のページから「令和○年度ごみ収集カレンダー（徳山）」などのページを探す
    idx = text(get(SHUNAN_INDEX))
    for region, fn in SHUNAN_PAGES.items():
        hit = [u for u, t in links(idx, SHUNAN_INDEX) if f"令和{reiwa}年度ごみ収集カレンダー（{region}）" in t]
        if not hit:
            problems.append(f"周南市：「令和{reiwa}年度ごみ収集カレンダー（{region}）」のページが {SHUNAN_INDEX} に見つかりません")
            continue
        raw = get(hit[0])
        todo.append((hit[0], dest / "周南市" / fn, raw))
        for (pg, label), pdf in SHUNAN_PDFS.items():
            if pg != region:
                continue
            found = [u for u, t in links(text(raw), hit[0]) if u.lower().endswith(".pdf") and t.startswith(label)]
            if found:
                todo.append((found[0], dest / "周南市" / pdf, None))
            else:
                problems.append(f"周南市：{hit[0]} に「{label}」のPDFが見つかりません")

    # 下松市：r○nishia4.pdf / r○higashia4.pdf（A4・月ごとの版）
    page = text(get(KUDAMATSU_PAGE))
    for key, fn in (("nishi", "nishi.pdf"), ("higashi", "higashi.pdf")):
        found = [u for u, _ in links(page, KUDAMATSU_PAGE) if re.search(rf"/r{reiwa}{key}a4\.pdf$", u, re.I)]
        if found:
            todo.append((found[0], dest / "下松市" / fn, None))
        else:
            others = sorted({u.rsplit("/", 1)[-1] for u, _ in links(page, KUDAMATSU_PAGE) if key in u and u.endswith(".pdf")})
            problems.append(f"下松市：r{reiwa}{key}a4.pdf が {KUDAMATSU_PAGE} に見つかりません（あったもの：{', '.join(others) or 'なし'}）")

    # 光市：○○1gomicalendermurozumi.pdf など（先頭の2けたが令和の年）
    page = text(get(HIKARI_PAGE))
    for key in HIKARI_KEYS:
        found = [u for u, _ in links(page, HIKARI_PAGE) if re.search(rf"/{reiwa:02d}\dgomicalender{key}\.pdf$", u, re.I)]
        if found:
            todo.append((found[0], dest / "光市" / f"{key}.pdf", None))
        else:
            others = sorted({u.rsplit("/", 1)[-1] for u, _ in links(page, HIKARI_PAGE) if key in u})
            problems.append(f"光市：{reiwa:02d}?gomicalender{key}.pdf が {HIKARI_PAGE} に見つかりません（あったもの：{', '.join(others) or 'なし'}）")

    for url, path, raw in todo:
        print(f"{'見つけた' if only_list else '保存'}: {path.relative_to(ROOT)}  ←  {url}")
        if only_list:
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw if raw is not None else get(url))
    if problems:
        print("\n見つからなかったもの（まだ新しい年度の分が出ていないか、市のページが変わっています）:")
        for p in problems:
            print("  ・", p)
        raise SystemExit(1)
    print("\nぜんぶ見つかりました。" + ("" if only_list else f"次は python v3/tools/update_year.py {year}"))


if __name__ == "__main__":
    main()
