"""Extract structured text + answer highlights from the SSC GD PDFs."""
import sys, re, json
from pdfparse import PDF, find_dict_value, parse_tounicode, _hex_to_str

REF_RE = re.compile(rb'(\d+)\s+(\d+)\s+R')

def ref_num(token):
    if token is None:
        return None
    m = REF_RE.match(token.strip())
    return int(m.group(1)) if m else None


class Doc:
    def __init__(self, path):
        self.pdf = PDF(path)
        self._tu_cache = {}

    def page_objs_in_order(self):
        """Return page object numbers ordered by the /Pages /Kids tree."""
        pdf = self.pdf
        # find /Type /Pages root with /Kids; gather kids order by walking
        # Simpler: collect all pages, order by object appearance is unreliable.
        # Walk Pages tree.
        roots = [n for n,b in pdf.objs.items() if b'/Type' in b and b'/Pages' in b]
        order = []
        visited = set()
        def walk(num):
            if num in visited: return
            visited.add(num)
            body = pdf.objs.get(num, b'')
            if b'/Page' in body and b'/Pages' not in body and b'/Kids' not in body:
                order.append(num); return
            kids = find_dict_value(body, b'/Kids')
            if kids:
                for m in REF_RE.finditer(kids):
                    walk(int(m.group(1)))
        # find top pages node (one not referenced as a kid) - just walk all roots
        # choose root: the Pages obj referenced by /Root catalog
        cat = [n for n,b in pdf.objs.items() if b'/Type' in b and b'/Catalog' in b]
        started = False
        for c in cat:
            pv = find_dict_value(pdf.objs[c], b'/Pages')
            rn = ref_num(pv)
            if rn:
                walk(rn); started = True
        if not started:
            for r in roots:
                walk(r)
        if not order:
            order = [n for n,b in pdf.objs.items() if b'/Type' in b and b'/Page' in b and b'/Pages' not in b]
        return order

    def font_map(self, page_body):
        """Return {fontname(str): (tounicode_dict)} for a page."""
        pdf = self.pdf
        res = find_dict_value(page_body, b'/Resources')
        rn = ref_num(res)
        if rn is not None:
            res = pdf.objs.get(rn, b'')
        if not res:
            return {}
        fonts = find_dict_value(res, b'/Font')
        fn = ref_num(fonts)
        if fn is not None:
            fonts = pdf.objs.get(fn, b'')
        if not fonts:
            return {}
        out = {}
        for m in re.finditer(rb'/([A-Za-z0-9_.+-]+)\s+(\d+)\s+(\d+)\s+R', fonts):
            name = m.group(1).decode('latin1')
            fontobj = pdf.objs.get(int(m.group(2)), b'')
            tu = self._font_tounicode(fontobj)
            out[name] = tu
        return out

    def _font_tounicode(self, fontobj):
        tuv = find_dict_value(fontobj, b'/ToUnicode')
        tn = ref_num(tuv)
        if tn is None:
            # maybe descendant font (Type0)
            desc = find_dict_value(fontobj, b'/DescendantFonts')
            return {}
        if tn in self._tu_cache:
            return self._tu_cache[tn]
        stream = self.pdf.get_stream(tn)
        cmap = parse_tounicode(stream)
        self._tu_cache[tn] = cmap
        return cmap

    def page_content(self, page_body):
        pdf = self.pdf
        cont = find_dict_value(page_body, b'/Contents')
        data = b''
        if cont is None:
            return b''
        if cont.strip().startswith(b'['):
            for m in REF_RE.finditer(cont):
                s = pdf.get_stream(int(m.group(1)))
                if s: data += s + b'\n'
        else:
            rn = ref_num(cont)
            if rn is not None:
                s = pdf.get_stream(rn)
                if s: data = s
        return data


# ----------------------------- content tokenizer -----------------------------

def tokenize(content):
    """Yield (kind, value). kind in {'num','name','str','hex','arr_str','op','arr'}."""
    i = 0; n = len(content)
    while i < n:
        c = content[i:i+1]
        if c.isspace():
            i += 1; continue
        if c == b'%':
            e = content.find(b'\n', i); i = e+1 if e!=-1 else n; continue
        if c == b'(':  # literal string
            depth = 1; j = i+1; buf = bytearray()
            while j < n and depth > 0:
                ch = content[j:j+1]
                if ch == b'\\':
                    buf += content[j:j+2]; j += 2; continue
                if ch == b'(': depth += 1
                elif ch == b')':
                    depth -= 1
                    if depth == 0: break
                buf += ch; j += 1
            yield ('str', bytes(buf)); i = j+1; continue
        if c == b'<' and content[i+1:i+2] != b'<':  # hex string
            e = content.find(b'>', i)
            yield ('hex', content[i+1:e]); i = e+1; continue
        if content[i:i+2] == b'<<':
            # dict - skip balanced
            depth=0; j=i
            while j < n:
                if content[j:j+2]==b'<<': depth+=1; j+=2; continue
                if content[j:j+2]==b'>>': depth-=1; j+=2
                if depth==0: break
                else: j+=1
            yield ('dict', content[i:j]); i=j; continue
        if c == b'[':  # array
            depth=1; j=i+1
            while j < n and depth>0:
                ch = content[j:j+1]
                if ch==b'[' : depth+=1
                elif ch==b']': depth-=1
                elif ch==b'(':
                    # skip string inside
                    d2=1; j+=1
                    while j<n and d2>0:
                        if content[j:j+1]==b'\\': j+=2; continue
                        if content[j:j+1]==b'(' : d2+=1
                        elif content[j:j+1]==b')': d2-=1
                        j+=1
                    continue
                j+=1
            yield ('arr', content[i:j]); i=j; continue
        if c == b'/':
            m = re.match(rb'/[^\s/<>\[\]()]+', content[i:])
            yield ('name', m.group(0)[1:]); i += m.end(); continue
        m = re.match(rb'[-+]?[0-9]*\.?[0-9]+', content[i:])
        if m:
            yield ('num', float(m.group(0))); i += m.end(); continue
        m = re.match(rb"[A-Za-z'\"*]+[0-9]*", content[i:])
        if m:
            yield ('op', m.group(0)); i += m.end(); continue
        i += 1


def mat_mul(a, b):
    return (
        a[0]*b[0]+a[1]*b[2], a[0]*b[1]+a[1]*b[3],
        a[2]*b[0]+a[3]*b[2], a[2]*b[1]+a[3]*b[3],
        a[4]*b[0]+a[5]*b[2]+b[4], a[4]*b[1]+a[5]*b[3]+b[5],
    )

def decode_hex_codes(hexbytes, tu):
    h = hexbytes.decode('latin1')
    h = re.sub(r'\s', '', h)
    if len(h) % 4 != 0:
        h = h + '0'*(4-len(h)%4)
    out = []
    for i in range(0, len(h), 4):
        code = int(h[i:i+4], 16)
        out.append(tu.get(code, ''))
    return ''.join(out)


def extract_page(doc, page_body):
    fonts = doc.font_map(page_body)
    content = doc.page_content(page_body)
    # graphics state
    ctm = (1,0,0,1,0,0)
    gstack = []
    fill = (0,0,0)
    tm = (1,0,0,1,0,0); tlm = (1,0,0,1,0,0)
    cur_font = None; font_size = 0; leading = 0
    frags = []   # (x, y, text, font, color)
    rects = []   # (x0,y0,x1,y1, color)
    operands = []
    pending_rect = None
    for kind, val in tokenize(content):
        if kind in ('num','name','str','hex','arr','dict'):
            operands.append((kind, val)); continue
        op = val
        if op == b'q':
            gstack.append((ctm, fill))
        elif op == b'Q':
            if gstack: ctm, fill = gstack.pop()
        elif op == b'cm' and len(operands)>=6:
            m = tuple(o[1] for o in operands[-6:])
            ctm = mat_mul(m, ctm)
        elif op in (b'rg',) and len(operands)>=3:
            fill = tuple(o[1] for o in operands[-3:])
        elif op == b'g' and len(operands)>=1:
            v=operands[-1][1]; fill=(v,v,v)
        elif op == b'k' and len(operands)>=4:
            c,m_,y,k=[o[1] for o in operands[-4:]]
            fill=((1-c)*(1-k),(1-m_)*(1-k),(1-y)*(1-k))
        elif op == b're' and len(operands)>=4:
            x,y,w,h = [o[1] for o in operands[-4:]]
            # transform corners by ctm
            pts=[(x,y),(x+w,y),(x,y+h),(x+w,y+h)]
            tx=[p[0]*ctm[0]+p[1]*ctm[2]+ctm[4] for p in pts]
            ty=[p[0]*ctm[1]+p[1]*ctm[3]+ctm[5] for p in pts]
            pending_rect=(min(tx),min(ty),max(tx),max(ty))
        elif op in (b'f',b'F',b'f*',b'b',b'B') :
            if pending_rect is not None:
                rects.append((*pending_rect, fill))
                pending_rect=None
        elif op == b'n':
            pending_rect=None
        elif op == b'BT':
            tm=(1,0,0,1,0,0); tlm=(1,0,0,1,0,0)
        elif op == b'Tf' and len(operands)>=2:
            cur_font = operands[-2][1].decode('latin1') if operands[-2][0]=='name' else None
            font_size = operands[-1][1]
        elif op == b'TL' and operands:
            leading = operands[-1][1]
        elif op == b'Td' and len(operands)>=2:
            tx,ty=operands[-2][1],operands[-1][1]
            tlm=mat_mul((1,0,0,1,tx,ty), tlm); tm=tlm
        elif op == b'TD' and len(operands)>=2:
            tx,ty=operands[-2][1],operands[-1][1]
            leading=-ty
            tlm=mat_mul((1,0,0,1,tx,ty), tlm); tm=tlm
        elif op == b'Tm' and len(operands)>=6:
            tm=tuple(o[1] for o in operands[-6:]); tlm=tm
        elif op == b'T*':
            tlm=mat_mul((1,0,0,1,0,-leading), tlm); tm=tlm
        elif op in (b'Tj', b"'", b'"'):
            if op==b"'":
                tlm=mat_mul((1,0,0,1,0,-leading), tlm); tm=tlm
            tu = fonts.get(cur_font, {})
            txt=''
            if operands:
                k,v=operands[-1]
                if k=='hex': txt=decode_hex_codes(v, tu)
                elif k=='str': txt=v.decode('latin1')
            if txt:
                trm=mat_mul(tm, ctm)
                frags.append((trm[4], trm[5], txt, cur_font, fill))
        elif op == b'TJ' and operands:
            k,v=operands[-1]
            if k=='arr':
                tu=fonts.get(cur_font,{})
                txt=''
                for mm in re.finditer(rb'<([0-9A-Fa-f\s]+)>|\(([^)]*)\)', v):
                    if mm.group(1) is not None:
                        txt+=decode_hex_codes(mm.group(1), tu)
                    elif mm.group(2) is not None:
                        txt+=mm.group(2).decode('latin1')
                if txt:
                    trm=mat_mul(tm,ctm)
                    frags.append((trm[4],trm[5],txt,cur_font,fill))
        operands=[]
    return frags, rects


def frags_to_lines(frags, ytol=3):
    # sort by y desc (top first), then x
    frags=sorted(frags, key=lambda f:(-round(f[1]/ytol), f[0]))
    lines=[]; cur=[]; cury=None
    for f in frags:
        y=f[1]
        if cury is None or abs(y-cury)<=ytol:
            cur.append(f); cury=y if cury is None else cury
        else:
            lines.append(cur); cur=[f]; cury=y
    if cur: lines.append(cur)
    out=[]
    for ln in lines:
        ln=sorted(ln, key=lambda f:f[0])
        text=''.join(f[2] for f in ln)
        ys=sum(f[1] for f in ln)/len(ln)
        xs=min(f[0] for f in ln)
        out.append({'y':ys,'x':xs,'text':text,'frags':ln})
    return out


if __name__ == '__main__':
    path=sys.argv[1]
    pageidx=int(sys.argv[2]) if len(sys.argv)>2 else 0
    doc=Doc(path)
    order=doc.page_objs_in_order()
    print(f'pages: {len(order)}', file=sys.stderr)
    pb=doc.pdf.objs[order[pageidx]]
    frags,rects=extract_page(doc, pb)
    lines=frags_to_lines(frags)
    for ln in lines:
        print(f"[{ln['y']:7.1f}] {ln['text']}")
    print('---- RECTS (colored fills) ----')
    for r in rects:
        col=r[4]
        # flag green/yellow
        tag=''
        rr,gg,bb=col
        if gg>0.6 and rr<0.7 and bb<0.6: tag='GREEN?'
        if rr>0.7 and gg>0.7 and bb<0.6: tag='YELLOW?'
        if tag:
            print(f'  rect y={r[1]:.0f}..{r[3]:.0f} x={r[0]:.0f}..{r[2]:.0f} color={col} {tag}')
