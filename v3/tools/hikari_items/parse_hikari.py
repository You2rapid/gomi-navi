"""光市ごみ分別事典（50音順分別早見表）の OCR 結果を品目表にする"""
import sys, json, re, glob, os, collections, pymupdf
sys.stdout.reconfigure(encoding='utf-8'); sys.stderr.reconfigure(encoding='utf-8')
sys.path.insert(0, os.path.dirname(__file__))
from lines import lines

Z = os.path.join(os.path.dirname(__file__), 'hikari', 'z')

def cy(l): return (l[1] + l[3]) / 2

def parse_half(path, dbg=False):
    L = lines(path)
    hdr = {k: next((l for l in L if k in l[4]), None) for k in ('材質', '区分', '出し方')}
    if not all(hdr.values()):
        return []
    top = max(h[3] for h in hdr.values()) + 5
    mat_x = hdr['材質'][0] + 124
    name_x = mat_x - 320
    cat_c = (hdr['区分'][0] + hdr['区分'][2]) / 2
    note_x = hdr['出し方'][0] - 205
    names, mats, cats, notes = [], [], [], []
    for l in L:
        x0, y0, x1, y1, t = l
        if y0 < top or (y1 - y0) > 80:      # 見出し・横の50音インデックス
            continue
        if re.fullmatch(r'\d{1,2}', t) and y0 > 3200:  # ページ番号
            continue
        if x0 >= note_x - 25:
            notes.append(l)
        elif abs((x0 + x1) / 2 - cat_c) < 170 and x0 > mat_x + 150:
            cats.append(l)
        elif abs(x0 - mat_x) < 30:
            mats.append(l)
        elif name_x - 60 <= x0 < mat_x - 40 and (y1 - y0) <= 45:
            names.append(l)
        else:
            print('??', os.path.basename(path), l, file=sys.stderr)
    cats.sort(key=cy); names.sort(key=cy); mats.sort(key=cy); notes.sort(key=lambda l: (l[1], l[0]))
    mc = []
    for l in sorted(cats, key=lambda l: (l[1], l[0])):
        if mc and abs(l[1] - mc[-1][1]) < 12:
            p = mc[-1]; mc[-1] = (min(p[0], l[0]), min(p[1], l[1]), max(p[2], l[2]), max(p[3], l[3]), p[4] + l[4])
        else:
            mc.append(l)
    cats = sorted(mc, key=cy)
    # 2行に折り返した品名をつなぐ
    nm = []
    for l in names:
        if nm and l[1] - nm[-1][3] < 25:
            p = nm[-1]; nm[-1] = (min(p[0], l[0]), p[1], max(p[2], l[2]), l[3], p[4] + l[4])
        else:
            nm.append(l)
    # 同じ高さの注意書き（横に分かれた）をつなぎ、行間の狭いものは1つの塊にする
    nb = []
    for l in notes:
        if nb and abs(l[1] - nb[-1][-1][1]) < 12:
            p = nb[-1][-1]; nb[-1][-1] = (p[0], min(p[1], l[1]), max(p[2], l[2]), max(p[3], l[3]), p[4] + l[4])
        elif nb and l[1] - nb[-1][-1][3] < 20:
            nb[-1].append(l)
        else:
            nb.append([l])
    rows = [{'y': cy(c), 'cat': c[4], 'mat': '', 'note': '', 'top': c[1], 'bot': c[3]} for c in cats]
    if not rows:
        return []
    for m in mats:
        r = min(rows, key=lambda r: abs(r['y'] - cy(m)))
        if abs(r['y'] - cy(m)) < 30: r['mat'] = m[4]
        else: print('mat?', os.path.basename(path), m, file=sys.stderr)
    for b in nb:
        y0, y1 = b[0][1], b[-1][3]; text = ''.join(l[4] for l in b)
        hit = [r for r in rows if y0 - 15 <= r['y'] <= y1 + 15]
        if not hit: hit = [min(rows, key=lambda r: abs(r['y'] - (y0 + y1) / 2))]
        for r in hit: r['note'] = (r['note'] + text) if r['note'] else text
    # 品目ごとに背景色（白・水色）が交互になっているので、色のまとまりで品目を分ける
    pm = pymupdf.Pixmap(path.replace('.tsv', ''))
    def bg(y):
        cs = [pm.pixel(int(name_x - dx), int(y)) for dx in (8, 15, 22)]
        return max(set(cs), key=cs.count)
    groups = []
    for r in rows:
        b = bg(r['y'])
        if groups and groups[-1]['bg'] == b and r['top'] - groups[-1]['rows'][-1]['bot'] < 90:
            groups[-1]['rows'].append(r)
        else:
            groups.append({'bg': b, 'rows': [r]})
    out = []
    for g in groups:
        y0 = g['rows'][0]['top'] - 45; y1 = g['rows'][-1]['bot'] + 45
        ns = [n for n in nm if y0 <= cy(n) <= y1]
        if not ns:
            print('no name', os.path.basename(path), int(g['rows'][0]['top']), [r['cat'] for r in g['rows']], file=sys.stderr)
        name = ''.join(n[4] for n in ns) if ns else '?'
        for n in ns: nm.remove(n)
        for r in g['rows']:
            out.append({'name': name, **{k: r[k] for k in ('mat', 'cat', 'note')}, 'src': os.path.basename(path), 'y': int(r['y'])})
    for n in nm:
        print('unused name', os.path.basename(path), n, file=sys.stderr)
    return out

if __name__ == '__main__':
    allr = []
    for f in sorted(glob.glob(os.path.join(Z, 't*.png.tsv'))):
        b = os.path.basename(f)
        if b < 't08_1' or b >= 't24_1.png.tsv' and b > 't24_1': pass
        if not ('t08_1' <= b[:5] <= 't24_1'): continue
        allr += parse_half(f)
    json.dump(allr, open(os.path.join(Z, 'raw_items.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=0)
    print(len(allr))
    print(collections.Counter(r['cat'] for r in allr).most_common())
