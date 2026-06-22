import re, json
from collections import Counter
from extract import Doc, extract_page, frags_to_lines
from structure import image_placements

def is_green(c):
    r,g,b=c; return g>0.35 and r<0.55 and b<0.55 and g>r+0.12 and g>b+0.12
def is_yellow(c):
    r,g,b=c; return r>0.7 and g>0.6 and b<0.55
def is_red(c):
    r,g,b=c; return r>0.6 and g<0.45 and b<0.45

def background_objs(doc, order):
    cnt=Counter()
    for pn in order:
        seen=set()
        for im in image_placements(doc, doc.pdf.objs[pn]):
            if im['obj'] not in seen:
                cnt[im['obj']]+=1; seen.add(im['obj'])
    th=len(order)*0.3
    return {o for o,c in cnt.items() if c>th}

def page_data(doc, pb, bg):
    frags,rects=extract_page(doc, pb)
    lines=frags_to_lines(frags)
    part=None; qnos=[]
    for ln in lines:
        m=re.search(r'PART-([A-D])\s*\(([^)]+)\)', ln['text'])
        if m: part=(m.group(1), m.group(2).strip())
        m=re.search(r'Q\.No:\s*(\d+)', ln['text'])
        if m: qnos.append((int(m.group(1)), ln['y']))
    imgs=[im for im in image_placements(doc, pb) if im['obj'] not in bg]
    col_imgs=sorted([im for im in imgs if 68<=im['x']<=95 and im['h']<45], key=lambda i:-i['y'])
    diagrams=[im for im in imgs if im['h']>=45]
    marks=[]
    for r in rects:
        x0,y0,x1,y1,c=r
        w=x1-x0; h=y1-y0
        if 22<=x0<=76 and w<60 and 8<h<42:
            cy=(y0+y1)/2
            tag='G' if is_green(c) else 'Y' if is_yellow(c) else 'R' if is_red(c) else None
            if tag: marks.append((cy,tag))
    return {'part':part,'qnos':sorted(qnos,key=lambda q:-q[1]),
            'imgs':col_imgs,'diagrams':diagrams,'marks':marks}

def mark_for(marks, im):
    cy=im['y']+im['h']/2
    for my,tag in marks:
        if abs(my-cy)<13:
            return tag
    return None

def extract_file(path, tag):
    doc=Doc(path); order=doc.page_objs_in_order()
    bg=background_objs(doc, order)
    pages=[page_data(doc, doc.pdf.objs[pn], bg) for pn in order]
    # group into sets
    sets=[]; cur=None
    for idx,p in enumerate(pages):
        has21=any(qn==21 for qn,_ in p['qnos'])
        if p['part'] and has21:
            cur={'file':tag,'start_page':idx,'part':p['part'],'page_idxs':[]}
            sets.append(cur)
        if cur is None:
            cur={'file':tag,'start_page':idx,'part':p['part'] or ('B','General Knowledge and General Awareness'),'page_idxs':[]}
            sets.append(cur)
        cur['page_idxs'].append(idx)
    # build a global reading-order stream per set
    for s in sets:
        stream=[]  # (page_idx, y, kind, payload)
        for idx in s['page_idxs']:
            p=pages[idx]
            for qn,qy in p['qnos']:
                stream.append((idx, qy, 'Q', qn))
            for im in p['imgs']:
                stream.append((idx, im['y'], 'img', (im, mark_for(p['marks'], im), idx)))
            for d in p['diagrams']:
                stream.append((idx, d['y'], 'dia', (d, idx)))
        stream.sort(key=lambda t:(t[0], -t[1]))
        questions=[]; cur_q=None
        for idx,y,kind,payload in stream:
            if kind=='Q':
                if cur_q: questions.append(cur_q)
                cur_q={'qno':payload,'page':idx,'imgs':[],'diagrams':[]}
            elif cur_q is not None:
                if kind=='img': cur_q['imgs'].append(payload)
                elif kind=='dia': cur_q['diagrams'].append(payload)
        if cur_q: questions.append(cur_q)
        # finalize each question: bottom 4 imgs = options, rest = stem
        for q in questions:
            ims=q['imgs']  # list of (im, tag, page)
            if len(ims)>=4:
                opts=ims[-4:]; stem=ims[:-4]
            else:
                opts=ims; stem=[]
            q['stem']=stem; q['options']=opts
            del q['imgs']
        s['questions']=questions
    return doc, sets, bg

def correct_index(q):
    ci=[i+1 for i,(im,tag,pg) in enumerate(q['options']) if tag in ('G','Y')]
    return ci[0] if len(ci)==1 else (ci if ci else None)

if __name__=='__main__':
    g={'sets':0,'q':0,'opt4':0,'single':0,'none':0,'multi':0}
    qper=Counter(); optper=Counter()
    for tag,path in [('F1','Gd/page1-223.pdf'),('F2','Gd/page224-445.pdf')]:
        doc,sets,bg=extract_file(path, tag)
        g['sets']+=len(sets)
        for s in sets:
            qper[len(s['questions'])]+=1
            for q in s['questions']:
                g['q']+=1; optper[len(q['options'])]+=1
                if len(q['options'])==4: g['opt4']+=1
                c=correct_index(q)
                if isinstance(c,int): g['single']+=1
                elif c is None: g['none']+=1
                else: g['multi']+=1
    print('stats:', g)
    print('questions per set:', dict(sorted(qper.items())))
    print('options per question:', dict(sorted(optper.items())))
