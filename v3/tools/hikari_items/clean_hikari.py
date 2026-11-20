"""OCR で読んだ光市の早見表を整える（区分の名寄せ・読み落としの補い・誤読の直し）"""
import sys, json, re, os, collections
sys.stdout.reconfigure(encoding='utf-8')
Z = os.path.join(os.path.dirname(__file__), 'hikari', 'z')
items = json.load(open(os.path.join(Z, 'raw_items.json'), encoding='utf-8'))

# OCR が品名を読めなかった品目（画像で確認）
NONAME = ["鏡", "鏡台", "釘", "碁石", "ござ", "碁盤", "CD（コンパクトディスク CD-R・CD-RWも含む）", "シーツ", "たる", "土", "時計",
          "ナット", "鍋", "縄", "ネジ", "笛", "ミシン", "ミニカー", "綿"]
groups = []
for i, r in enumerate(items):
    if r['name'] == '?':
        if groups and groups[-1][-1] == i - 1 and items[i - 1]['src'] == r['src']: groups[-1].append(i)
        else: groups.append([i])
assert len(groups) == len(NONAME)
for g, n in zip(groups, NONAME):
    for i in g: items[i]['name'] = n
for r in items:
    if r['name'] == '時計' and '小型' in r['cat']: r['mat'] = '置時計・掛け時計・柱時計・目覚まし時計など'

# 区分の文字が小さくて読めなかった行（画像で確認して補う）
ADD = [
    ("t09_0.png.tsv", 1815, "生花用吸水性スポンジ（緑色のスポンジ状のもの）", "", "陶磁器", ""),
    ("t09_1.png.tsv", 1976, "うちわ", "骨組みがプラスチック製", "他プラ", "紙の部分は必ず切り離して、可燃ごみへ"),
    ("t10_1.png.tsv", 2135, "温度計", "電池を使用しないもの", "陶磁器", "水銀を使用するものは、販売店等にご相談ください。環境事業課窓口でも回収しています。"),
    ("t15_0.png.tsv", 2533, "醤油、ソース等調味料の容器", "弁当用の魚型や角型等を購入したもの", "他プラ", "中身を使いきりましょう。"),
    ("t18_0.png.tsv", 1894, "デッキブラシ", "", "他プラ", "柄の部分が木製のものは1m以内に切ってください。"),
    ("t18_1.png.tsv", 1416, "電池", "ボタン電池・充電式電池", "×", "販売店の回収ボックス等をご利用ください。環境事業課窓口でも回収しています。"),
    ("t20_1.png.tsv", 1893, "ビニール袋", "商品として購入したもの", "他プラ", ""),
    ("t22_0.png.tsv", 618, "ペットボトル（本体）", "PETマークのついているもの", "ペット", "色つきのものは、その他プラスチック類へ"),
    ("t22_0.png.tsv", 697, "ペットボトル（本体）", "PETマークのついていないもの", "他プラ", ""),
    ("t23_0.png.tsv", 1176, "まくら", "ウレタン・プラスチック部分", "他プラ", ""),
    ("t24_0.png.tsv", 1974, "ラップ", "食品販売時に包装されているもの", "容プラ", "水で洗っても簡単に汚れが取れない場合は、可燃ごみで出すことができます。"),
    ("t24_0.png.tsv", 2054, "ラップ", "ラップそのものを商品として購入したもの", "他プラ", ""),
]
for src, y, n, m, c, d in ADD:
    items.append({'name': n, 'mat': m, 'cat': c, 'note': d, 'src': src, 'y': y, 'fixed': True})
items.sort(key=lambda r: (r['src'], r['y']))
for r in items:
    if r['name'] == '酒ハック': r['cat'] = '可燃'
    if r['name'] == '座卓': r['cat'] = '可燃粗大'

def catkey(t):
    if t in ("陶磁器", "他プラ", "容プラ", "×", "ペット", "可燃", "可燃粗大"): return t
    if '陶磁' in t or 'ゴム' in t: return '陶磁器'
    if '容器' in t or '包装' in t: return '容プラ'
    if 'その他' in t: return '他プラ'
    if '粗' in t: return '可燃粗大'
    if '可燃' in t: return '可燃'
    if '家電' in t: return '小型家電'
    if '金属' in t: return '金属'
    if 'びん' in t or '缶' in t: return 'びん缶'
    if 'ペット' in t: return 'ペット'
    if '有害' in t: return '有害'
    if '収集しない' in t: return '×'
    if '古紙' in t or '古布' in t: return '古紙古布'
    return None

bad = [r for r in items if not catkey(r['cat'])]
for r in bad: print('BADCAT', r)
items = [r for r in items if catkey(r['cat'])]
for r in items: r['c'] = catkey(r['cat'])
json.dump(items, open(os.path.join(Z, 'items1.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=0)
print(len(items), collections.Counter(r['c'] for r in items))
