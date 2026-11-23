"""Excel（.xlsx）の表を読む（openpyxl なしで、文字と数字だけ）。

  sheets(path)            → {シート名: [[セルの文字, ...], ...]}
"""
import re
import zipfile
import xml.etree.ElementTree as ET

NS = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
      "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships"}
REL = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"


def _col(ref):
    n = 0
    for ch in re.match(r"[A-Z]+", ref).group(0):
        n = n * 26 + ord(ch) - 64
    return n - 1


def _text(si):
    return "".join(t.text or "" for t in si.iter(f"{{{NS['m']}}}t") if not _in_phonetic(si, t))


def _in_phonetic(si, t):
    # ふりがな（rPh）の中の文字は使わない
    for rph in si.iter(f"{{{NS['m']}}}rPh"):
        if t in list(rph.iter()):
            return True
    return False


def sheets(path):
    with zipfile.ZipFile(path) as z:
        shared = []
        if "xl/sharedStrings.xml" in z.namelist():
            shared = [_text(si) for si in ET.fromstring(z.read("xl/sharedStrings.xml")).findall("m:si", NS)]
        rels = {r.get("Id"): r.get("Target") for r in ET.fromstring(z.read("xl/_rels/workbook.xml.rels"))}
        out = {}
        for s in ET.fromstring(z.read("xl/workbook.xml")).find("m:sheets", NS):
            target = rels[s.get(REL)].lstrip("/")
            target = target if target.startswith("xl/") else "xl/" + target
            rows = []
            for row in ET.fromstring(z.read(target)).iter(f"{{{NS['m']}}}row"):
                vals = []
                for c in row.findall("m:c", NS):
                    i = _col(c.get("r"))
                    v = c.find("m:v", NS)
                    if c.get("t") == "s" and v is not None:
                        val = shared[int(v.text)]
                    elif c.get("t") == "inlineStr":
                        val = "".join(t.text or "" for t in c.iter(f"{{{NS['m']}}}t"))
                    else:
                        val = v.text if v is not None else ""
                    vals += [""] * (i - len(vals) + 1)
                    vals[i] = (val or "").strip()
                rows.append(vals)
            out[s.get("name")] = rows
        return out
