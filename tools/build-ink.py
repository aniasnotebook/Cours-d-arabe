# Builds lecons-ink.js: each card of chapters 3 to 5 as the fonts draw it, glyph by glyph, with the class of its letter's
# place in the word. Shaping by HarfBuzz (the same engine as the browsers), on the app's own font files.
import json, re, sys, subprocess
import uharfbuzz as hb
from fontTools.ttLib import TTFont
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.boundsPen import BoundsPen
# Run from anywhere: python3 tools/build-ink.py  (needs: pip install uharfbuzz fonttools brotli, and node)
import os, tempfile
APP=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))+'/'
FONTS=['AmiriQuran-400-arabic','ScheherazadeNew-400-arabic','Amiri-700-arabic']
TMP=tempfile.mkdtemp()
F=[]
for n in FONTS:
    t=TTFont(APP+'fonts/'+n+'.woff2'); t.flavor=None; t.save(f'{TMP}/{n}.ttf'); t=TTFont(f'{TMP}/{n}.ttf')
    blob=hb.Blob.from_file_path(f'{TMP}/{n}.ttf'); hf=hb.Font(hb.Face(blob))
    F.append(dict(tt=t,gs=t.getGlyphSet(),order=t.getGlyphOrder(),hf=hf,upm=t['head'].unitsPerEm))
MARK=re.compile('[ً-ٰٟۖ-ࣰۭ-ࣿ]')
NOJOIN="اأإآٱدذرزوؤةىء"
def place(base,i):
    jn=lambda c: c=='ـ' or c not in NOJOIN
    fp=i>0 and jn(base[i-1]) and base[i]!='ء'; tn=i<len(base)-1 and jn(base[i]) and base[i+1]!='ء'
    return 'm' if fp and tn else 'f' if fp else 'i' if tn else 's'
used=[{} for _ in F]
def path(fi,gid):
    if gid not in used[fi]:
        f=F[fi]; pen=SVGPathPen(f['gs'],ntos=lambda v: str(round(v))); f['gs'][f['order'][gid]].draw(pen); used[fi][gid]=pen.getCommands()
    return used[fi][gid]
def bounds(fi,gid):
    f=F[fi]; bp=BoundsPen(f['gs']); f['gs'][f['order'][gid]].draw(bp); return bp.bounds
def ismark(fi,gid):
    g=F[fi]['tt']['GDEF'].table.GlyphClassDef.classDefs
    return g.get(F[fi]['order'][gid])==3
def word(w, fonts):
    """w: one word; fonts: font index per character."""
    units=[]; base=''
    for i,c in enumerate(w):
        if MARK.match(c) and units: units[-1].append(i)
        else: units.append([i]); base+=c
    cls={}; stroke={}
    for k,u in enumerate(units):
        c=place(base,k)
        if w[u[0]]=='ـ' and len(u)==1 and k>0: c=cls[units[k-1][0]]   # a bare joining stroke goes with the letter before
        for i in u: cls[i]=c
        if w[u[0]]=='ـ' and k>0: stroke[u[0]]=cls[units[k-1][0]]   # the stroke itself is the letter before stretched; only its signs are this unit
    segs=[]   # (font, first char, last char) in logical order
    for i,fi in enumerate(fonts):
        if segs and segs[-1][0]==fi: segs[-1][2]=i
        else: segs.append([fi,i,i])
    runs=[]
    for fi,a,b in segs:
        # Each font shapes its own part, with a zero-width joiner where the word goes on in the other font: what the
        # browser does for a word split between two fonts (the cards' html joins them the same way).
        f=F[fi]; pre=a>0; post=b<len(w)-1
        cps=([0x200d] if pre else [])+[ord(c) for c in w[a:b+1]]+([0x200d] if post else [])
        buf=hb.Buffer(); buf.add_codepoints(cps); buf.guess_segment_properties()
        hb.shape(f['hf'],buf,{}); s=1000/f['upm']; x=0; gl=[]
        for info,pos in zip(buf.glyph_infos,buf.glyph_positions):
            ci=info.cluster-(1 if pre else 0)+a
            if a<=ci<=b and cps[info.cluster]!=0x200d: gl.append((info.codepoint,(x+pos.x_offset)*s,pos.y_offset*s,stroke[ci] if ci in stroke and not ismark(fi,info.codepoint) else cls.get(ci,'s'),pos.x_advance*s))
            x+=pos.x_advance
        if not gl: continue
        minx=min(g[1] for g in gl); width=sum(g[4] for g in gl)
        runs.append((fi,gl,minx,width))
    total=sum(r[3] for r in runs); right=total; out=[]; top=-1e9; bot=1e9
    for fi,gl,minx,width in runs:   # logical order: right to left
        shift=right-width-minx; right-=width
        for gid,x,y,c,adv in gl:
            out.append([fi,gid,round(x+shift),round(y),c]); path(fi,gid)
            bb=bounds(fi,gid)
            if bb:
                s=1000/F[fi]['upm']; pad=40
                top=max(top,(bb[3])*s+y+pad); bot=min(bot,bb[1]*s+y-pad)
    if top<-1e8: top,bot=700,-300
    return [round(total),round(top),round(bot),out]
def text(t, fontof):
    words=[]; k=0
    for w in t.split(' '):
        if not w: k+=1; continue
        words.append(word(w,[fontof(k+i,c) for i,c in enumerate(w)])); k+=len(w)+1
    return words
# The cards, as the app loads them.
js=open(APP+'lecons-data.js').read()
items=json.loads(subprocess.run(['node','-e',js.replace('const ','var ')+';console.log(JSON.stringify(BOOK_ITEMS))'],capture_output=True,text=True).stdout)
INK={}
for it in items:
    key=f"b{it['pg']}:{it['n']}"; t=it['t']
    if it.get('h'):   # spans: <span class="ar sh">…</span><span class="am">…</span>
        spans=re.findall(r'<span class="([^"]*)">([^<]*)</span>',it['h'])
        fl=[]
        for c,tx in spans: fl+= [2 if 'am' in c else 1 if 'sh' in c else 0]*len(tx)
        assert ''.join(tx for _,tx in spans)==t,(key)
        fo=lambda i,c,fl=fl: fl[i]
    elif it.get('m')=='sq':
        g=list(t); last=len(g)-1
        while last>0 and MARK.match(g[last]): last-=1
        fo=lambda i,c,last=last: 1 if i<last else 0
    elif it.get('f')=='s': fo=lambda i,c: 1
    else: fo=lambda i,c: 0
    INK[key]=[t,text(t,fo)]   # with its text: a card changed since is drawn as plain text until rebuilt
for t in ['الٓمٓ','بَ','أَحَدٌ','حمٓ','بَ بٍ بَٰ بَا أَبۡ أَبَّ','أَبَدًا','خَوۡفٍ','أَنۡتَ','أَ حَ دٌ']:
    INK['t:'+t]=[t,text(t,lambda i,c: 0)]
P=[{str(g):d for g,d in u.items()} for u in used]
SW=[round(F[i]['upm']/32,1) for i in range(len(F))]; SW[2]=0   # Amiri has a real bold: no stroke added
out='// Built by build-ink.py from the app\'s fonts (HarfBuzz shaping): each card of chapters 3 to 5 glyph by glyph.\n'
out+='const INK_PATHS = '+json.dumps(P,ensure_ascii=False,separators=(',',':'))+';\nconst INK_SCALE = '+json.dumps([1000/F[i]['upm'] for i in range(len(F))])+';\nconst INK_STROKE = '+json.dumps(SW)+';\nconst INK = '+json.dumps(INK,ensure_ascii=False,separators=(',',':'))+';\n'
open(APP+'lecons-ink.js','w').write(out)
print(len(out)//1024,'KB', sum(len(u) for u in used),'glyphs')
