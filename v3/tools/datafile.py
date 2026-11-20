"""data/ フォルダの JS ファイル（毎年4月に変わるデータ）の読み書き。

data/calendar_shunan.js などは次の形をしている:
    // 説明
    window.GOMI_CAL = /*CAL-DATA-START*/{...JSON...}/*CAL-DATA-END*/;
"""
import json
import re
from pathlib import Path

V3 = Path(__file__).resolve().parent.parent      # v3 フォルダ
DATA = V3 / "data"
ROOT = V3.parent                                  # gomi フォルダ（元データ/ がある所）

# 市 → (ファイル名, 変数名, 目印, カレンダーの名前)
CALENDARS = {
    "shunan": ("calendar_shunan.js", "GOMI_CAL", "CAL", "周南市「ごみ収集カレンダー」"),
    "kudamatsu": ("calendar_kudamatsu.js", "GOMI_CAL_KUDAMATSU", "KUDA", "下松市「家庭ごみ収集カレンダー」（西地区・東地区）"),
    "hikari": ("calendar_hikari.js", "GOMI_CAL_HIKARI", "HIKARI", "光市「ごみ収集カレンダー」（7地区）"),
}


def nendo(year):
    return f"令和{year - 2018}年度（{year}年4月〜{year + 1}年3月）"


def write_calendar(city, data, tool, path=None):
    fn, var, mark, title = CALENDARS[city]
    path = Path(path) if path else DATA / fn
    text = (f"// {title} {nendo(data['year'])}の収集日\n"
            f"// 市のPDFから自動で作ったファイルです。手で直さず、tools/update_year.py で作り直してください（{tool} を使います）。\n"
            f"window.{var} = /*{mark}-DATA-START*/" + json.dumps(data, ensure_ascii=False, separators=(",", ":"))
            + f"/*{mark}-DATA-END*/;\n")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")
    return path


def read_calendar(city, path=None):
    fn, var, mark, _ = CALENDARS[city]
    text = (Path(path) if path else DATA / fn).read_text(encoding="utf-8")
    m = re.search(rf"/\*{mark}-DATA-START\*/(.*?)/\*{mark}-DATA-END\*/", text, re.S)
    return json.loads(m.group(1))


def write_holidays(year, holidays, year_end, path=None):
    path = Path(path) if path else DATA / "holidays.js"
    text = (f"// {nendo(year)}の祝日・休日と年末年始\n"
            "// 内閣府「国民の祝日」CSV から自動で作ったファイルです。手で直さず、tools/update_year.py で作り直してください。\n"
            "window.GOMI_HOLIDAYS = " + json.dumps({"year": year, "holidays": holidays, "yearEnd": year_end}, ensure_ascii=False) + ";\n")
    path.write_text(text, encoding="utf-8", newline="\n")
    return path
