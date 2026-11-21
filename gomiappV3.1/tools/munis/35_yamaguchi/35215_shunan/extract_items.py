# 周南市「家庭ごみの分別方法」PDFの分別早見表（PDF 22〜46ページ）から品目を抽出する。
# 使い方: python extract_items.py <冊子.pdf> items.json warn.txt gomi_items.js
#   （初版から引き継いだ道具。できた gomi_items.js を make_items.py で items.js にする。手順は make_items.py を見る）
# 必要: pip install pymupdf
import pymupdf, sys, json, re, collections
CATS = {"可燃","紙衣","びん缶","ペット","容プラ","他プラ","不燃","小型家電","処困","粗大","×","家電","―"}
KANA = set("アイウエオカキクケコサシスセソタチツテトナニヌネノハヒフヘホマミムメモヤユヨラリルレロワヲン")
doc = pymupdf.open(sys.argv[1])
items=[]; warn=[]; heads=[(21,0,'ア')]
for pno in range(21, 46):
    p = doc[pno]; W=p.rect.width
    L=[]
    for b in p.get_text("dict")["blocks"]:
        for l in b.get("lines", []):
            segs=[[]]
            for s in l["spans"]:
                st=s["text"].strip()
                if len(st)==1 and st in KANA and s["bbox"][2]<75:
                    if s["bbox"][0]>25: heads.append((pno,l["bbox"][1],st))
                    continue
                if st in CATS or (st and st[0]=="■" and st[1:].strip() in CATS):
                    segs.append([s]); segs.append([])
                else:
                    segs[-1].append(s)
            for sg in segs:
                t=""
                for k,sp in enumerate(sg):
                    if k and sp["bbox"][0]-sg[k-1]["bbox"][2]>6 and sp["text"].strip(): t=t.rstrip()+""
                    t+=sp["text"]
                t=t.strip()
                if not t: continue
                x0=min(s["bbox"][0] for s in sg); x1=max(s["bbox"][2] for s in sg)
                L.append(dict(x0=x0,y=l["bbox"][1],x1=x1,t=t))
    hdr=[l for l in L if l["t"]=="区分"]
    if not hdr: warn.append(f"p{pno+1} no header"); continue
    top=max(h["y"] for h in hdr)+5
    L=[l for l in L if l["y"]>top and l["y"]<W*1.36]
    cats=[l for l in L if l["t"] in CATS]
    cmin=min(c["x0"] for c in cats); cmax=max(c["x1"] for c in cats)
    rest=[l for l in L if l not in cats and not (len(l["t"])==1 and l["t"] in KANA) and not re.fullmatch(r"\d+",l["t"])]
    names=[l for l in rest if l["x1"]<=cmin+3]
    notes=[l for l in rest if l["x0"]>=cmax-6]
    other=[l for l in rest if l not in names and l not in notes]
    for o in other: warn.append(f"p{pno+1} other: {o}")
    mainx=min(n["x0"] for n in names)
    for n in names: n["sub"]= n["x0"]>mainx+45
    rows=sorted([dict(y=c["y"],cat=c["t"],main=None,sub=None,notes=[]) for c in cats],key=lambda r:r["y"])
    for n in names:
        r=min(rows,key=lambda r:abs(r["y"]-n["y"]))
        n["row"]= r if abs(r["y"]-n["y"])<11 else None
    for r in rows:
        ms=sorted([n for n in names if n["row"] is r and not n["sub"]],key=lambda n:n["y"])
        ss=sorted([n for n in names if n["row"] is r and n["sub"]],key=lambda n:n["y"])
        r["main"]="".join(n["t"] for n in ms) or None
        r["sub"]="".join(n["t"] for n in ss) or None
        r["mainy"]=sum(n["y"] for n in ms)/len(ms) if ms else None
    # parent fragments: main lines not near any row, or main lines of rows that have a sub
    frags=[n for n in names if not n["sub"] and (n["row"] is None or n["row"]["sub"])]
    frags.sort(key=lambda n:n["y"])
    for n in names:
        if n["row"] is None and n["sub"]: warn.append(f"p{pno+1} orphan sub {n['t']} y={n['y']:.0f}")
    cands=[]
    for n in frags:
        if cands and n["y"]-cands[-1]["ylast"]<18:
            cands[-1]["t"]+=n["t"]; cands[-1]["ys"].append(n["y"]); cands[-1]["ylast"]=n["y"]
        else: cands.append(dict(t=n["t"],ys=[n["y"]],ylast=n["y"]))
    for c in cands: c["y"]=sum(c["ys"])/len(c["ys"])
    for r in rows:
        if r["main"] and not r["sub"]: r["name"]=r["main"]
        elif not r["sub"]: r["name"]=None
    # contiguous runs of sub rows
    runs=[];cur=[]
    for r in rows:
        if r["sub"]: cur.append(r)
        else:
            if cur: runs.append(cur); cur=[]
    if cur: runs.append(cur)
    for run in runs:
        lo=run[0]["y"]-25; hi=run[-1]["y"]+25
        ps=[c for c in cands if lo<=c["y"]<=hi]
        if not ps:
            warn.append(f"p{pno+1} no parent for run at {run[0]['y']:.0f}"); ps=[dict(t="?",y=run[0]["y"])]
        n=len(run); k=len(ps)
        if k>n: warn.append(f"p{pno+1} more parents than rows at {run[0]['y']:.0f}"); k=n; ps=ps[:n]
        import functools
        @functools.lru_cache(None)
        def dp(i,j):
            if j==k: return (0,()) if i==n else (1e18,())
            best=(1e18,())
            for e in range(i+1,n-(k-j-1)+1):
                ys=[run[t]["y"] for t in range(i,e)]
                c=(sum(ys)/len(ys)-ps[j]["y"])**2
                sub=dp(e,j+1)
                if c+sub[0]<best[0]: best=(c+sub[0],(e,)+sub[1])
            return best
        cost,cuts=dp(0,0)
        st=0
        for j,e in enumerate(cuts):
            for t in range(st,e):
                r=run[t]; r["parent"]=ps[j]["t"]; r["subname"]=r["sub"]; r["name"]=f"{ps[j]['t']}（{r['sub']}）"
            st=e
    for nt in notes:
        r=min(rows,key=lambda r:abs(r["y"]-nt["y"]+2))
        r["notes"].append(nt["t"])
    for r in rows:
        if not r["name"]: warn.append(f"p{pno+1} noname y={r['y']:.0f} {r['cat']} {r['notes']}")
        items.append(dict(page=pno+1,y=round(r["y"]),name=r["name"],parent=r.get("parent"),sub=r.get("subname"),cat=r["cat"],note="".join(r["notes"])))
def clean(t):
    if t is None: return None
    if "" in t:
        a,b=t.split("",1); t=f"{a}（{b.replace(chr(1),'')}）"
    return t
for it in items:
    hs=[h for h in heads if (h[0]+1,h[1])<=(it["page"],it["y"]+6)]
    it["kana"]=hs[-1][2]
    for k in ("name","parent","sub"): it[k]=clean(it[k])
json.dump(items,open(sys.argv[2],"w",encoding="utf-8"),ensure_ascii=False,indent=0)
open(sys.argv[3],"w",encoding="utf-8").write("\n".join(warn))
print(len(items), len(warn))
# ---- アプリ用データ (items.js) を書き出す ----
if len(sys.argv) > 4:
    out = []
    try:  # 漢字の読み（ひらがな）を付けて「でんち」→「電池」のように検索できるようにする
        import pykakasi
        _kks = pykakasi.kakasi()
        yomi = lambda s: "".join(x["hira"] for x in _kks.convert(s))
    except ImportError:
        print("pykakasi が無いため読みデータは付きません（pip install pykakasi）")
        yomi = None
    for it in items:
        nm = it["name"] or ""
        rec = {"n": nm.replace("※", "").replace("■", "").strip(), "c": it["cat"], "k": it["kana"]}
        if it["note"]: rec["d"] = it["note"]
        if "※" in nm: rec["new"] = 1
        if "■" in nm: rec["chg"] = 1
        if yomi and re.search(r"[一-鿿々]", rec["n"]): rec["y"] = yomi(rec["n"])
        out.append(rec)
    js = ("// 周南市「家庭ごみの分別方法」分別早見表より自動抽出（tools/extract_items.py）\n"
          "window.GOMI_ITEMS = " + json.dumps(out, ensure_ascii=False, separators=(",", ":")) + ";\n")
    dst = sys.argv[4]
    if dst.endswith(".html"):
        html = open(dst, encoding="utf-8").read()
        a = html.index("/*DATA-BEGIN*/") + len("/*DATA-BEGIN*/")
        b = html.index("/*DATA-END*/")
        html = html[:a] + "\n" + js + html[b:]
        open(dst, "w", encoding="utf-8").write(html)
    else:
        open(dst, "w", encoding="utf-8").write(js)
