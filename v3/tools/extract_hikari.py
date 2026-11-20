"""光市「令和8年度 ごみ収集カレンダー」（地区ごとのPDF）から収集日を取り出す。

使い方:
  python tools/extract_hikari.py <PDFのフォルダ> hikari.json
  （できた JSON を index.html の window.GOMI_CAL_HIKARI に貼り付ける）

フォルダには市のサイト（ごみ収集カレンダーのページ）からダウンロードした
081gomicalendermurozumi.pdf 〜 087gomicalenderyamato.pdf の7つを置く。
PDF の文字は図形（アウトライン）なので、
  ・収集の札：色つき（または白）の四角形の色と、中の文字の形（図形の数）で種類を見分ける
  ・日付：マスの左上の数字の形（図形の数）を読み、曜日が列と合うものを選ぶ
読めないものがあれば止まる（どの月も全部の日がそろっているかも確かめる）。
"""
import pymupdf, json, sys, glob, os, datetime, collections, itertools
sys.stdout.reconfigure(encoding='utf-8')

DIGIT = {7: '17', 10: '2', 17: '3', 14: '4', 15: '5', 13: '69', 16: '8', 12: '0'}   # 図形の数 → 数字（1と7、6と9は同じ数）
WHITE = (1.0, 1.0, 1.0)

def kind(fill, glyphs):
    n = len(glyphs); g0 = glyphs[0] if glyphs else 0
    if fill is None:
        return '可燃' if g0 == 14 else '有害' if g0 == 27 else None
    f = tuple(round(c, 2) for c in fill)
    if f == (1.0, 0.94, 0.0): return '容プラ'
    if f == (0.0, 0.45, 0.74): return '他プラ'
    if f == (0.93, 0.0, 0.55): return '可燃粗大'
    if f == (0.96, 0.44, 0.13): return '古紙古布'
    if f == (0.93, 0.11, 0.14): return '陶磁器'
    if f == (0.0, 0.65, 0.31):
        if n == 3: return '金属'
        if n == 5: return 'びん缶'
        if n == 6 and g0 == 18: return 'ペット'
        if n == 6 and g0 == 16: return '小型家電'
    return None

def page_data(page, months):
    ds = page.get_drawings()
    fills = [d for d in ds if d['type'] == 'f']
    cells = [d['rect'] for d in fills if d['fill'] == WHITE and 18 < d['rect'].width < 45 and 18 < d['rect'].height < 50]
    digs = [d for d in fills if 1 < d['rect'].width < 6.5 and 4 < d['rect'].height < 8 and d['fill'] != WHITE]
    strokes = [d for d in ds if d['type'] == 's' and 30 < d['rect'].width < 42 and 5 < d['rect'].height < 9.5]
    labels = []
    for s in strokes:
        r = s['rect']; fill = None
        for f in fills:
            fr = f['rect']
            if abs(fr.x0 - r.x0) < .3 and abs(fr.y0 - r.y0) < .3 and abs(fr.width - r.width) < .5 and abs(fr.height - r.height) < .5:
                fill = f['fill']; break
        g = sorted([f for f in fills if r.contains(f['rect']) and f['rect'].width < 8], key=lambda f: f['rect'].x0)
        k = kind(fill, [len(f['items']) for f in g])
        if not k: raise SystemExit(f'unknown label {fill} {[len(f["items"]) for f in g]}')
        labels.append((r, k))
    W, H = page.rect.width, page.rect.height
    digs = [d for d in digs if not any(r.contains(d['rect']) for r, k in labels) and 6.2 < d['rect'].height < 7.3 and len(d['items']) in DIGIT]
    out = {}
    for qi, (yy, mm) in enumerate(months):
        qx, qy = qi % 2, qi // 2
        blk = [c for c in cells if (c.x0 >= W / 2) == bool(qx) and (c.y0 >= H / 2) == bool(qy)]
        xs = sorted({round(c.x0) for c in blk if c.width > 25})
        cols = []
        for x in xs:
            if not cols or x - cols[-1] > 10: cols.append(x)
        if len(cols) != 7: raise SystemExit(f'cols {mm}: {cols}')
        for c in blk:
            g = sorted([d for d in digs if c.x0 - .5 <= d['rect'].x0 <= c.x0 + 14 and c.y0 - .5 <= d['rect'].y0 <= c.y1 - 5], key=lambda d: (round(d['rect'].y0), d['rect'].x0))
            if not g: continue
            # 1つのマスに2つの日付（例：24/31）がある場合は、数字の行ごとに分ける
            rows = []
            for d in g:
                if rows and abs(d['rect'].y0 - rows[-1][0]['rect'].y0) < 3: rows[-1].append(d)
                else: rows.append([d])
            col = min(range(7), key=lambda i: abs(cols[i] - c.x0))
            for ri, rg in enumerate(rows):
                rg.sort(key=lambda d: d['rect'].x0)
                opts = [DIGIT.get(len(d['items']), '') for d in rg]
                cands = []
                for t in itertools.product(*opts):
                    d = int(''.join(t))
                    try: dt = datetime.date(yy, mm, d)
                    except ValueError: continue
                    if (dt.weekday() + 1) % 7 == col: cands.append(dt)
                if len(cands) != 1:
                    raise SystemExit(f'date? {mm} col{col} {[len(d["items"]) for d in rg]} {cands}')
                dt = cands[0]
                top = rg[0]['rect'].y0 - 1 if ri else c.y0
                bot = rows[ri + 1][0]['rect'].y0 - 1 if ri + 1 < len(rows) else c.y1
                sub = pymupdf.Rect(c.x0, top, c.x1, bot)
                ks = [k for r, k in labels if sub.contains(pymupdf.Point((r.x0 + r.x1) / 2, (r.y0 + r.y1) / 2))]
                if dt in out: raise SystemExit(f'dup {dt}')
                out[dt] = ks
        n = sum(1 for d in out if d.month == mm)
        last = (datetime.date(yy + (mm == 12), mm % 12 + 1, 1) - datetime.timedelta(days=1)).day
        if n != last: raise SystemExit(f'{yy}-{mm}: {n} days found (expected {last})')
    used = sum(len(v) for v in out.values())
    if used != len(labels): raise SystemExit(f'labels outside cells: {len(labels) - used}')
    return out

MONTHS = [[(2026, 4), (2026, 5), (2026, 6), (2026, 7)], [(2026, 8), (2026, 9), (2026, 10), (2026, 11)], [(2026, 12), (2027, 1), (2027, 2), (2027, 3)]]
ORDER = ['可燃', '容プラ', '他プラ', 'ペット', 'びん缶', '金属', '小型家電', '古紙古布', '可燃粗大', '有害', '陶磁器']
WD = '日月火水木金土'
# 地区（ファイル名, 地区名, 読み, 住所）。大和地区だけ出す時刻が朝7時30分まで
AREAS = [
    ('murozumi', '室積地区', 'むろづみちく', '室積1〜8丁目・市延・大町・沖田・新開1〜2丁目・中央町・西ノ庄・東ノ庄・神田・正木・松原・千坊台1〜3丁目・大字室積村の一部・光井1丁目の一部'),
    ('mitsui', '光井地区', 'みついちく', '光井1〜9丁目・中央1〜6丁目・大字光井・大字室積村の一部'),
    ('shimata', '島田地区', 'しまたちく', '島田1〜7丁目・大字島田の一部'),
    ('asaekita', '浅江地区（JR線路から北側）', 'あさえちく', '協和町・宝町・中村町・虹ケ丘1〜7丁目・丸山町・宮ノ下町・和田町・大字浅江・光ケ丘'),
    ('asaeminami', '浅江地区（JR線路から南側）', 'あさえちく', '虹ケ浜1〜3丁目・浅江1〜7丁目・木園1丁目・花園1・2丁目'),
    ('mishima', '三島・周防・中島田地区', 'みしま・すおう・なかしまたちく', '大字三井・三井1〜8丁目・岩狩1〜3丁目・大字小周防・大字立野・上島田1〜9丁目・中島田1〜3丁目・大字島田の一部'),
    ('yamato', '大和地区', 'やまとちく', '大字岩田・大字岩田立野・大字塩田・大字三輪・大字束荷'),
]
CUT = {'yamato': [7, 30]}

def rules_and_moved(days):
    # 区分ごとに「毎週◯曜日」「月2回 ◯曜日」などにまとめる。いつもとちがう曜日の日は「振替」とする
    occ = collections.defaultdict(list)
    for d, ks in days.items():
        for c in ks: occ[c].append(d)
    rules, moved = {}, collections.defaultdict(list)
    for c in ORDER:
        ds = occ.get(c)
        if not ds: continue
        wds = collections.Counter((d.weekday() + 1) % 7 for d in ds)
        main = sorted(w for w, n in wds.items() if n >= len(ds) * 0.25)
        for d in ds:
            if (d.weekday() + 1) % 7 not in main: moved[d.isoformat()].append(c)
        wtxt = '・'.join(WD[w] for w in main)
        per = sum(wds[w] for w in main) / len(main)
        nth = collections.Counter((d.day - 1) // 7 + 1 for d in ds if (d.weekday() + 1) % 7 in main)
        if per >= 40: rules[c] = f'毎週{wtxt}曜日'
        elif len(main) == 1 and len(nth) <= 2 and all(n >= 10 for n in nth.values()):
            rules[c] = f"毎月第{'・'.join(map(str, sorted(nth)))}{wtxt}曜日"
        else:
            n = round(len(ds) / 12)
            rules[c] = f'月{n}回 {wtxt}曜日'
    return rules, {k: sorted(v, key=ORDER.index) for k, v in sorted(moved.items())}

if __name__ == '__main__':
    files = {os.path.basename(f)[3:-4].replace('gomicalender', ''): f for f in glob.glob(os.path.join(sys.argv[1], '08*gomicalender*.pdf'))}
    res = {'year': 2026, 'schedules': {}, 'areas': []}
    for key, name, yomi, desc in AREAS:
        doc = pymupdf.open(files[key]); days = {}
        for i in range(3): days.update(page_data(doc[i], MONTHS[i]))
        days = {d: ks for d, ks in days.items() if ks}
        rules, moved = rules_and_moved(days)
        res['schedules'][name] = {'rules': rules, 'days': {d.isoformat(): sorted(ks, key=ORDER.index) for d, ks in sorted(days.items())},
                                  'moved': moved, **({'cut': CUT[key]} if key in CUT else {})}
        res['areas'].append({'r': '', 'n': name, 's': name, 'y': yomi, 'd': desc})
        print(name, len(days), rules, len(moved), file=sys.stderr)
    with open(sys.argv[2], 'w', encoding='utf-8') as f:
        f.write(json.dumps(res, ensure_ascii=False, separators=(',', ':')))
