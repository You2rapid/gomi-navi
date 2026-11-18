# アプリアイコン（PNG）を生成する。
# 使い方: python tools/make_icons.py   （必要: pip install pymupdf）
import os
import pymupdf

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "icons")
os.makedirs(OUT, exist_ok=True)

GREEN = "#2f8f5b"
DARK = "#246f47"


def bin_shape(scale, cx=256, cy=262):
    """白いごみ箱（中心 cx,cy、scale=1 で高さ約 300px）"""
    s = scale
    def X(v): return cx + v * s
    def Y(v): return cy + v * s
    return f"""
  <g fill="#ffffff">
    <rect x="{X(-34)}" y="{Y(-150)}" width="{68*s}" height="{28*s}" rx="{10*s}"/>
    <rect x="{X(-120)}" y="{Y(-128)}" width="{240*s}" height="{34*s}" rx="{14*s}"/>
    <path d="M{X(-100)} {Y(-80)} L{X(100)} {Y(-80)} L{X(86)} {Y(140)} Q{X(84)} {Y(158)} {X(66)} {Y(158)} L{X(-66)} {Y(158)} Q{X(-84)} {Y(158)} {X(-86)} {Y(140)} Z"/>
  </g>
  <g stroke="{GREEN}" stroke-width="{16*s}" stroke-linecap="round">
    <line x1="{X(-44)}" y1="{Y(-44)}" x2="{X(-40)}" y2="{Y(118)}"/>
    <line x1="{X(0)}" y1="{Y(-44)}" x2="{X(0)}" y2="{Y(118)}"/>
    <line x1="{X(44)}" y1="{Y(-44)}" x2="{X(40)}" y2="{Y(118)}"/>
  </g>"""


def svg(rounded, scale):
    bg = (f'<rect width="512" height="512" rx="112" fill="{GREEN}"/>' if rounded
          else f'<rect width="512" height="512" fill="{GREEN}"/>')
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="512" height="512" viewBox="0 0 512 512">
  {bg}
  <circle cx="256" cy="256" r="{236 if rounded else 256}" fill="{DARK}" opacity="0.18"/>
  {bin_shape(scale)}
</svg>"""


def render(svg_text, size, name, transparent=False):
    doc = pymupdf.open(stream=svg_text.encode("utf-8"), filetype="svg")
    page = doc[0]
    pix = page.get_pixmap(matrix=pymupdf.Matrix(size / 512, size / 512), alpha=transparent)
    pix.save(os.path.join(OUT, name))
    print("wrote", name, pix.width, "x", pix.height)


# 通常アイコン（Android / ブラウザ用）：角丸
render(svg(True, 1.0), 192, "icon-192.png", transparent=True)
render(svg(True, 1.0), 512, "icon-512.png", transparent=True)
# マスカブル（Android が丸や角丸に切り抜く用）：全面塗り＋安全領域内に縮小
render(svg(False, 0.78), 512, "icon-maskable-512.png")
render(svg(False, 0.78), 192, "icon-maskable-192.png")
# iPhone 用（iOS が自動で角を丸めるので正方形・全面塗り）
render(svg(False, 0.9), 180, "apple-touch-icon.png")
# ファビコン
render(svg(True, 1.0), 32, "favicon-32.png", transparent=True)
with open(os.path.join(OUT, "icon.svg"), "w", encoding="utf-8") as f:
    f.write(svg(True, 1.0))
