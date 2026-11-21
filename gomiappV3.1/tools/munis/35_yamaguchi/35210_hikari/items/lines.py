import sys, collections
sys.stdout.reconfigure(encoding='utf-8')
def lines(path):
    L = collections.OrderedDict()
    for row in open(path, encoding='utf-8-sig'):
        p = row.rstrip('\n').split('\t')
        if len(p) < 6: continue
        li, x, y, w, h, t = int(p[0]), *map(int, p[1:5]), p[5]
        L.setdefault(li, []).append((x, y, w, h, t))
    out = []
    for li, ws in L.items():
        x0 = min(w[0] for w in ws); y0 = min(w[1] for w in ws)
        x1 = max(w[0]+w[2] for w in ws); y1 = max(w[1]+w[3] for w in ws)
        out.append((x0, y0, x1, y1, ''.join(w[4] for w in ws)))
    return out
if __name__ == '__main__':
    for l in sorted(lines(sys.argv[1]), key=lambda l: (l[1]//12, l[0])):
        print(*l)
