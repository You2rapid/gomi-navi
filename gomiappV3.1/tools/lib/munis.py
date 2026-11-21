"""自治体の一覧と、ファイルの置き場所・データファイルの読み書き（道具みんなで使う）。

置き場所のきまり（例：山口県 周南市 = 県コード 35・自治体コード 35215）
  アプリのデータ   gomiappV3.1/data/35_yamaguchi/35215_shunan/  city.js・items.js・calendar.js
  地図             gomiappV3.1/geo/35_yamaguchi.json（県ごと）・v3/geo/index.json（県の一覧と範囲）
  作る道具         gomiappV3.1/tools/munis/35_yamaguchi/35215_shunan/  calendar.py・geo.py など
  元データ         gomi/元データ/35_山口県/35215_周南市/  2026年度/・分別の冊子/・地図/
  祝日（全国共通） gomi/元データ/全国/2026年度/syukujitsu.csv

自治体の一覧は gomiappV3.1/data/municipalities.js（アプリと同じものを読む）。
"""
import importlib.util
import json
import re
from pathlib import Path

V3 = Path(__file__).resolve().parents[2]       # アプリのフォルダ（gomiappV3.1）
ROOT = V3.parent                                # gomi フォルダ
DATA = V3 / "data"
GEO = V3 / "geo"
TOOLS = V3 / "tools"
SOURCES = ROOT / "元データ"


def _between(text, mark):
    m = re.search(rf"/\*{mark}-START\*/(.*?)/\*{mark}-END\*/", text, re.S)
    if not m:
        raise ValueError(f"/*{mark}-START*/ が見つかりません")
    return m


class Muni:
    def __init__(self, m, pref):
        self.code, self.name, self.slug, self.yomi = m["code"], m["name"], m["slug"], m.get("yomi", "")
        self.pref, self.pref_name, self.pref_slug = pref["code"], pref["name"], pref["slug"]
        self.path = f"{self.pref}_{self.pref_slug}/{self.code}_{self.slug}"          # data/ と tools/munis/ の中の場所
        self.data_dir = DATA / self.path
        self.tool_dir = TOOLS / "munis" / self.path
        self.src_dir = SOURCES / f"{self.pref}_{self.pref_name}" / f"{self.code}_{self.name}"   # 元データ

    def __repr__(self):
        return f"{self.pref_name} {self.name}（{self.code}）"

    def year_dir(self, year):
        return self.src_dir / f"{year}年度"

    def module(self, name):
        """tools/munis/<県>/<自治体>/<name>.py を読み込む（なければ None）"""
        f = self.tool_dir / f"{name}.py"
        if not f.exists():
            return None
        spec = importlib.util.spec_from_file_location(f"muni_{self.code}_{name}", f)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod

    # ---- データファイル ----
    def read(self, kind):
        """kind: city / items / calendar"""
        mark = {"city": "CITY", "items": "ITEMS", "calendar": "CAL"}[kind]
        return json.loads(_between((self.data_dir / f"{kind}.js").read_text(encoding="utf-8"), mark).group(1))

    def write_calendar(self, data, path=None):
        path = Path(path) if path else self.data_dir / "calendar.js"
        text = (f"// {self.pref_name} {self.name}（{self.code}） {nendo(data['year'])}の収集日\n"
                f"// 市のPDF・オープンデータから自動で作ったファイルです。手で直さず、tools/update_year.py で作り直してください"
                f"（tools/munis/{self.path}/calendar.py を使います）。\n"
                f'gomiData("{self.code}", "calendar", /*CAL-START*/' + json.dumps(data, ensure_ascii=False, separators=(",", ":"))
                + "/*CAL-END*/);\n")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8", newline="\n")
        return path


def registry():
    text = (DATA / "municipalities.js").read_text(encoding="utf-8")
    return json.loads(_between(text, "MUNIS").group(1))


def munis(codes=None):
    reg = registry()
    prefs = {p["code"]: p for p in reg["prefs"]}
    out = [Muni(m, prefs[m["pref"]]) for m in reg["munis"]]
    if codes:
        out = [m for m in out if m.code in codes or m.name in codes]
    return out


def prefs():
    return registry()["prefs"]


def nendo(year):
    return f"令和{year - 2018}年度（{year}年4月〜{year + 1}年3月）"


def holiday_csv(year):
    return SOURCES / "全国" / f"{year}年度" / "syukujitsu.csv"


def write_holidays(year, holidays, year_end, path=None):
    path = Path(path) if path else DATA / "holidays.js"
    text = (f"// {nendo(year)}の祝日・休日と年末年始（全国共通）\n"
            "// 内閣府「国民の祝日」CSV から自動で作ったファイルです。手で直さず、tools/update_year.py で作り直してください。\n"
            "window.GOMI_HOLIDAYS = " + json.dumps({"year": year, "holidays": holidays, "yearEnd": year_end}, ensure_ascii=False) + ";\n")
    path.write_text(text, encoding="utf-8", newline="\n")
    return path


def read_calendar_file(path):
    return json.loads(_between(Path(path).read_text(encoding="utf-8"), "CAL").group(1))
