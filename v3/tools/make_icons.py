"""v3 のアプリアイコンを作る（カレンダーとウインクするごみ箱、4色のなかま）。

使い方（gomi フォルダで実行）:
  python v3/tools/make_icons.py
  必要: pip install pymupdf

できるもの（v3/icons/）:
  icon.svg               元の絵（ブラウザで見られる）
  icon-192.png・icon-512.png                 ホーム画面用（角が丸い）
  icon-maskable-192.png・icon-maskable-512.png Android 用（四角いっぱい。丸や角丸に切り抜かれても大丈夫なよう、絵を少し小さく）
  apple-touch-icon.png   iPhone 用（180×180。角は iPhone が丸める）
  favicon-32.png         ブラウザのタブ用（小さいので、マス目や曜日を省いた絵）

絵は 120×120 の座標で描いている。曜日の文字は、どのスマホでも同じ形になるよう、PNG に焼き込む。
"""
from pathlib import Path

import pymupdf

OUT = Path(__file__).resolve().parents[1] / "icons"
BIN_SCALE = 1.07   # ごみ箱キャラの大きさ（最初の案の約1.3倍）

GREEN, DARK, WHITE, INK, CHEEK = "#2f8f5b", "#1f5e3c", "#ffffff", "#1f2421", "#f4a0b8"
CELL, TODAY = "#efede7", "#e8f5ee"
C_GREEN, C_YELLOW, C_BLUE, C_RED = "#1fa35c", "#f5c800", "#2ea7e0", "#e5483d"
WEEK = [("日", C_RED), ("月", "#888780"), ("火", "#888780"), ("水", "#888780"), ("木", "#888780"), ("金", "#888780"), ("土", C_BLUE)]
WEEK_X = [20, 33, 46, 60, 74, 87, 100]


def pal(x, y, color, wink=False):
    """4色のなかま（丸い顔）"""
    right_eye = (f'<path d="M{x + 1} {y - 1} Q{x + 2.6} {y - 3} {x + 4.2} {y - 1}" fill="none" stroke="{INK}" stroke-width="1.4" stroke-linecap="round"/>'
                 if wink else f'<circle cx="{x + 2.6}" cy="{y - 1}" r="1.6" fill="{INK}"/>')
    return (f'<circle cx="{x}" cy="{y}" r="8" fill="{color}"/>'
            f'<circle cx="{x - 2.6}" cy="{y - 1}" r="1.6" fill="{INK}"/>{right_eye}'
            f'<path d="M{x - 2.2} {y + 3} Q{x} {y + 4.8} {x + 2.2} {y + 3}" fill="none" stroke="{INK}" stroke-width="1.4" stroke-linecap="round"/>')


def bin_char(cx, cy, s):
    """ウインクするごみ箱（中心 cx, cy・大きさ s）"""
    return f'''<g transform="translate({cx} {cy}) scale({s})">
<g transform="rotate(-14 0 -20)"><rect x="-15" y="-23" width="30" height="5.5" rx="2.75" fill="{DARK}"/><rect x="-5" y="-27" width="10" height="5" rx="2" fill="{DARK}"/></g>
<path d="M-13 -14 H13 L11 14 Q10.6 18 7 18 H-7 Q-10.6 18 -11 14 Z" fill="{GREEN}"/>
<rect x="-9" y="-10" width="3" height="9" rx="1.5" fill="#97c9ad"/>
<ellipse cx="-5" cy="-3" rx="3.2" ry="3.9" fill="{INK}"/><circle cx="-3.9" cy="-4.5" r="1.3" fill="{WHITE}"/>
<path d="M2.5 -2.5 Q5.5 -6 8.5 -2.5" fill="none" stroke="{INK}" stroke-width="2.4" stroke-linecap="round"/>
<circle cx="-9" cy="5" r="3" fill="{CHEEK}"/><circle cx="9" cy="5" r="3" fill="{CHEEK}"/>
<path d="M-4.2 4 Q0 9.5 4.2 4 Z" fill="{INK}"/>
</g>'''


def star(x, y, k=1.0):
    p = " ".join(f"{x + dx * k:.2f} {y + dy * k:.2f}" for dx, dy in [(0, -6), (1.7, -1.7), (6, 0), (1.7, 1.7), (0, 6), (-1.7, 1.7), (-6, 0), (-1.7, -1.7)])
    return f'<path d="M{p} Z" fill="{C_YELLOW}"/>'


def art_simple():
    """ブラウザのタブ用（32px）：細かいマス目や曜日は省いて、カレンダーとごみ箱を大きく"""
    return "".join([
        f'<rect x="12" y="20" width="96" height="88" rx="14" fill="{WHITE}"/>',
        f'<path d="M26 20 H94 Q108 20 108 34 V40 H12 V34 Q12 20 26 20 Z" fill="{DARK}"/>',
        f'<circle cx="30" cy="30" r="7" fill="{C_GREEN}"/><circle cx="50" cy="30" r="7" fill="{C_YELLOW}"/>',
        f'<circle cx="70" cy="30" r="7" fill="{C_BLUE}"/><circle cx="90" cy="30" r="7" fill="{C_RED}"/>',
        bin_char(60, 77, 1.5),
    ])


def art():
    """背景の上にのる絵（120×120 の座標）"""
    cells = []
    for x, rows in ((15, [(56, None), (71, C_GREEN), (86, None), (98, C_RED)]), (95, [(56, None), (71, C_YELLOW), (86, C_BLUE), (98, None)])):
        for y, col in rows:
            h = 6 if y == 98 else 11
            cells.append(f'<rect x="{x}" y="{y}" width="10" height="{h}" rx="2" fill="{col or CELL}"/>')
    return "".join([
        f'<rect x="12" y="26" width="96" height="82" rx="12" fill="{WHITE}"/>',
        f'<path d="M24 26 H96 Q108 26 108 38 V42 H12 V38 Q12 26 24 26 Z" fill="{DARK}"/>',
        pal(27, 24, C_GREEN), pal(47, 21, C_YELLOW, wink=True), pal(73, 21, C_BLUE), pal(93, 24, C_RED),
        *cells,
        f'<rect x="29" y="55" width="62" height="49" rx="8" fill="{TODAY}" stroke="{GREEN}" stroke-width="2.2"/>',
        bin_char(60, 82, BIN_SCALE),
        star(83, 63),
    ])


def svg(size, shape, scale=1.0, with_text=True, simple=False):
    """shape: round（角丸・まわり透明）／square（四角いっぱい）"""
    bg = f'<rect width="120" height="120" rx="26" fill="{GREEN}"/>' if shape == "round" else f'<rect width="120" height="120" fill="{GREEN}"/>'
    text = ""
    if with_text:   # icon.svg だけ。PNG では文字をあとから焼き込む
        text = "".join(f'<text x="{x}" y="51" text-anchor="middle" font-size="7" font-weight="700" fill="{c}" '
                       f'font-family="Hiragino Kaku Gothic ProN, Yu Gothic, Meiryo, sans-serif">{w}</text>' for (w, c), x in zip(WEEK, WEEK_X))
    off = 60 * (1 - scale)
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{size}" height="{size}" viewBox="0 0 120 120">{bg}'
            f'<g transform="translate({off:.2f} {off:.2f}) scale({scale})">{art_simple() if simple else art()}{text}</g></svg>')


def png(path, size, shape, scale=1.0, week=True, simple=False):
    doc = pymupdf.open("svg", svg(size, shape, scale, with_text=False, simple=simple).encode())
    src = doc.convert_to_pdf()
    page_doc = pymupdf.open()
    page = page_doc.new_page(width=120, height=120)
    page.show_pdf_page(page.rect, pymupdf.open("pdf", src), 0)
    if week:   # 曜日（太く見えるよう、ふちどりして書く）
        font = pymupdf.Font("japan")
        off = 60 * (1 - scale)
        for (w, c), x in zip(WEEK, WEEK_X):
            fs = 7 * scale
            tw = font.text_length(w, fontsize=fs)
            rgb = tuple(int(c[i:i + 2], 16) / 255 for i in (1, 3, 5))
            page.insert_text((off + x * scale - tw / 2, off + 51 * scale), w, fontsize=fs, fontname="japan",
                             color=rgb, fill=rgb, render_mode=2, border_width=0.04)
    pix = page.get_pixmap(matrix=pymupdf.Matrix(size / 120, size / 120), alpha=(shape == "round"))
    pix.save(path)


def main():
    OUT.mkdir(exist_ok=True)
    (OUT / "icon.svg").write_text(svg(512, "round"), encoding="utf-8")
    png(OUT / "icon-192.png", 192, "round")
    png(OUT / "icon-512.png", 512, "round")
    # Android の maskable は、真ん中の円（直径80%）の外が切られることがあるので、絵を小さく
    png(OUT / "icon-maskable-192.png", 192, "square", scale=0.7)
    png(OUT / "icon-maskable-512.png", 512, "square", scale=0.7)
    png(OUT / "apple-touch-icon.png", 180, "square")
    png(OUT / "favicon-32.png", 32, "round", week=False, simple=True)
    for f in sorted(OUT.iterdir()):
        print(f.name, f.stat().st_size)


if __name__ == "__main__":
    main()
