"""ごみ出しカレンダー（gomiappV3.1）のアプリアイコンを作る（A-1：うすいマス目のカレンダーと緑のごみ箱）。

使い方（gomi フォルダで実行）:
  python gomiappV3.1/tools/make_icons.py
  必要: pip install pymupdf

できるもの（gomiappV3.1/icons/）:
  icon.svg               元の絵（ブラウザで見られる）
  icon-192.png・icon-512.png                 ホーム画面用（角が丸い）
  icon-maskable-192.png・icon-maskable-512.png Android 用（四角いっぱい。丸や角丸に切り抜かれても欠けないよう、絵を少し小さく）
  apple-touch-icon.png   iPhone 用（180×180。角は iPhone が丸める）
  favicon-32.png         ブラウザのタブ用（小さいので、マス目を省いた絵）
ストア版（gomiapp-store/assets/。gomiapp-store で npx @capacitor/assets generate を実行すると、iPhone・Android のアイコンになる）:
  icon-only.png（1024×1024・四角いっぱい）、icon-foreground.png（絵だけ・まわり透明）、icon-background.png（緑だけ）

絵は 120×120 の座標で描いている。色や大きさを変えたいときは、下の数字を直して実行する。
"""
from pathlib import Path

import pymupdf

OUT = Path(__file__).resolve().parents[1] / "icons"

GREEN = "#2f8f5b"      # 背景・ごみ箱
DARK = "#1f5e3c"       # カレンダーのリング
YELLOW = "#f5c800"     # カレンダーの見出し
WHITE = "#ffffff"
LINE = "#e6e3db"       # うすいマス目
BIN_SCALE = 1.05       # ごみ箱の大きさ


def bin_shape(cx, cy, s):
    """緑のごみ箱（白い縦の線2本）"""
    return f'''<g transform="translate({cx} {cy}) scale({s})">
<rect x="-17" y="-26" width="34" height="6" rx="3" fill="{GREEN}"/>
<rect x="-6" y="-31" width="12" height="6" rx="2.5" fill="{GREEN}"/>
<path d="M-14 -17 H14 L11.5 13 Q11 17 7 17 H-7 Q-11 17 -11.5 13 Z" fill="{GREEN}"/>
<rect x="-6.5" y="-11" width="3.4" height="22" rx="1.7" fill="{WHITE}"/>
<rect x="3.1" y="-11" width="3.4" height="22" rx="1.7" fill="{WHITE}"/>
</g>'''


def art(grid=True):
    """背景の上にのる絵（カレンダーとごみ箱）"""
    parts = [
        f'<rect x="18" y="24" width="84" height="80" rx="12" fill="{WHITE}"/>',
        f'<path d="M30 24 H90 Q102 24 102 36 V44 H18 V36 Q18 24 30 24 Z" fill="{YELLOW}"/>',
        f'<rect x="35" y="15" width="8" height="18" rx="4" fill="{DARK}"/>',
        f'<rect x="77" y="15" width="8" height="18" rx="4" fill="{DARK}"/>',
    ]
    if grid:   # うすいマス目（ごみ箱のうしろは白く抜く）
        parts.append(f'<g stroke="{LINE}" stroke-width="1.6">'
                     '<line x1="18" y1="64" x2="102" y2="64"/><line x1="18" y1="84" x2="102" y2="84"/>'
                     '<line x1="39" y1="44" x2="39" y2="104"/><line x1="60" y1="44" x2="60" y2="104"/><line x1="81" y1="44" x2="81" y2="104"/></g>')
        parts.append(f'<rect x="40" y="44" width="40" height="60" fill="{WHITE}"/>')
    parts.append(bin_shape(60, 78, BIN_SCALE))
    return "".join(parts)


def svg(size, shape, scale=1.0, grid=True):
    """shape: round（角丸・まわり透明）／square（四角いっぱい）／art（絵だけ・まわり透明）／bg（緑だけ）。scale で絵だけを小さくする"""
    bg = {"round": f'<rect width="120" height="120" rx="26" fill="{GREEN}"/>', "art": ""}.get(shape, f'<rect width="120" height="120" fill="{GREEN}"/>')
    off = 60 * (1 - scale)
    body = "" if shape == "bg" else f'<g transform="translate({off:.2f} {off:.2f}) scale({scale})">{art(grid)}</g>'
    return f'<svg xmlns="http://www.w3.org/2000/svg" width="{size}" height="{size}" viewBox="0 0 120 120">{bg}{body}</svg>'


def png(path, size, shape, scale=1.0, grid=True):
    doc = pymupdf.open("svg", svg(size, shape, scale, grid).encode())
    page = doc[0]
    pix = page.get_pixmap(matrix=pymupdf.Matrix(size / page.rect.width, size / page.rect.height), alpha=shape in ("round", "art"))
    pix.save(path)


def main():
    OUT.mkdir(exist_ok=True)
    (OUT / "icon.svg").write_text(svg(512, "round"), encoding="utf-8")
    png(OUT / "icon-192.png", 192, "round")
    png(OUT / "icon-512.png", 512, "round")
    # Android の maskable は、真ん中の円（直径80%）の外が切られることがあるので、絵を小さく
    png(OUT / "icon-maskable-192.png", 192, "square", scale=0.78)
    png(OUT / "icon-maskable-512.png", 512, "square", scale=0.78)
    png(OUT / "apple-touch-icon.png", 180, "square")
    png(OUT / "favicon-32.png", 32, "round", grid=False)
    for f in sorted(OUT.iterdir()):
        print(f.name, f.stat().st_size)
    # ストア版（gomiapp-store があるときだけ）。Android のアイコンは丸などに切り抜かれるので、絵だけのものは小さめに
    store = OUT.parents[1] / "gomiapp-store" / "assets"
    if store.parent.exists():
        store.mkdir(exist_ok=True)
        png(store / "icon-only.png", 1024, "square")
        png(store / "icon-foreground.png", 1024, "art", scale=0.62)
        png(store / "icon-background.png", 1024, "bg")
        for f in sorted(store.iterdir()):
            print("gomiapp-store/assets/" + f.name, f.stat().st_size)


if __name__ == "__main__":
    main()
