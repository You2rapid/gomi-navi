import sys, json, os
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lines import lines
out = []
for half in ('t25_0', 't25_1'):
    L = lines(f'hikari/z/{half}.png.tsv')
    hd = next((l for l in L if '雑がみ事典' in l[4] or '注意点' in l[4]), None)
    cats = [l for l in L if l[4] in ('可燃ごみ', '雑がみ', '可燃こみ', '雑かみ', '古紙類', '新聞', '雑誌', 'ダンボール') or ('雑が' in l[4] and len(l[4]) <= 4)]
    if not cats: print('no cats', half); continue
    cx = min(c[0] for c in cats)
    for c in cats:
        y = (c[1] + c[3]) / 2
        row = [l for l in L if abs((l[1] + l[3]) / 2 - y) < 14 and l is not c and l[3] - l[1] < 45]
        name = ''.join(l[4] for l in sorted(row, key=lambda l: l[0]) if l[0] < cx - 50 and l[2] - l[0] > 45)
        note = ''.join(l[4] for l in sorted(row, key=lambda l: l[0]) if l[0] > c[2])
        out.append({'name': name, 'cat': c[4], 'note': note, 'src': half, 'y': int(y)})
json.dump(out, open('hikari/z/zatsu.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=0)
print(len(out))
for r in out: print(r['name'], '|', r['cat'], '|', r['note'])
