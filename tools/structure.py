import sys, re, json
from extract import Doc, extract_page, frags_to_lines, tokenize, ref_num, mat_mul
from pdfparse import find_dict_value

def is_green(c):
    r,g,b=c; return g>0.4 and r<0.55 and b<0.55 and g> r+0.15 and g> b+0.15
def is_yellow(c):
    r,g,b=c; return r>0.7 and g>0.6 and b<0.55
def is_red(c):
    r,g,b=c; return r>0.6 and g<0.45 and b<0.45

def image_placements(doc, pb):
    res=find_dict_value(pb,b'/Resources'); rn=ref_num(res)
    if rn: res=doc.pdf.objs.get(rn,b'')
    xo=find_dict_value(res,b'/XObject'); xn=ref_num(xo)
    if xn: xo=doc.pdf.objs.get(xn,b'')
    xmap={}
    for m in re.finditer(rb'/([A-Za-z0-9_.+-]+)\s+(\d+)\s+(\d+)\s+R', xo or b''):
        xmap[m.group(1).decode()]=int(m.group(2))
    content=doc.page_content(pb)
    ctm=(1,0,0,1,0,0); stack=[]; operands=[]; placements=[]
    for kind,val in tokenize(content):
        if kind in ('num','name','str','hex','arr','dict'):
            operands.append((kind,val)); continue
        op=val
        if op==b'q': stack.append(ctm)
        elif op==b'Q':
            if stack: ctm=stack.pop()
        elif op==b'cm' and len(operands)>=6:
            ctm=mat_mul(tuple(o[1] for o in operands[-6:]), ctm)
        elif op==b'Do' and operands and operands[-1][0]=='name':
            name=operands[-1][1].decode()
            if name in xmap:
                placements.append({'y':ctm[5],'x':ctm[4],'w':ctm[0],'h':ctm[3],'name':name,'obj':xmap[name]})
        operands=[]
    return placements

def analyze(path):
    doc=Doc(path); order=doc.page_objs_in_order()
    pages=[]
    for idx,pn in enumerate(order):
        pb=doc.pdf.objs[pn]
        frags,rects=extract_page(doc, pb)
        lines=frags_to_lines(frags)
        # part header
        part=None
        for ln in lines:
            m=re.search(r'PART-([A-D])\s*\(([^)]+)\)', ln['text'])
            if m: part=(m.group(1), m.group(2).strip())
        # q numbers with y
        qs=[]
        for ln in lines:
            m=re.search(r'Q\.No:\s*(\d+)', ln['text'])
            if m: qs.append({'qno':int(m.group(1)),'y':ln['y']})
        imgs=image_placements(doc, pb)
        # colored marker rects (left cell, narrow width, x small)
        marks=[]
        for r in rects:
            x0,y0,x1,y1,c=r
            w=x1-x0; h=y1-y0
            if w<60 and 8<h<40 and x0<120:
                if is_green(c): marks.append((y0+ (y1-y0)/2,'G'))
                elif is_yellow(c): marks.append((y0+(y1-y0)/2,'Y'))
                elif is_red(c): marks.append((y0+(y1-y0)/2,'R'))
        pages.append({'page':idx,'part':part,'qs':qs,'nimgs':len(imgs),
                      'marks':marks,
                      'qimg':[i for i in imgs if i['w']>150 and i['h']>24],
                      'optimg':[i for i in imgs if i['w']<=150 and 18<i['h']<28]})
    return doc, order, pages

if __name__=='__main__':
    path=sys.argv[1]
    doc,order,pages=analyze(path)
    # summary
    parts_seen=[]
    allq=[]
    for p in pages:
        if p['part']: parts_seen.append((p['page'],p['part']))
        for q in p['qs']: allq.append(q['qno'])
    print('pages:',len(pages))
    print('PART headers found on pages:', len(parts_seen))
    for pg,pt in parts_seen[:20]:
        print('  page',pg,'PART',pt)
    print('total Q.No labels:', len(allq))
    print('Q.No min/max:', min(allq), max(allq))
    print('distinct Q.No values count:', len(set(allq)))
    # marks summary
    g=sum(sum(1 for m in p['marks'] if m[1]=='G') for p in pages)
    y=sum(sum(1 for m in p['marks'] if m[1]=='Y') for p in pages)
    rr=sum(sum(1 for m in p['marks'] if m[1]=='R') for p in pages)
    print('green marks:',g,'yellow marks:',y,'red marks:',rr)
    nq=sum(len(p['qimg']) for p in pages); no=sum(len(p['optimg']) for p in pages)
    print('question images:',nq,'option images:',no, 'total content imgs (approx):', nq+no)
