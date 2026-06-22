import os, base64, html
from build_final import extract_file, correct_index

OUT='Gd/study'
os.makedirs(OUT, exist_ok=True)
LETTERS=['A','B','C','D']

def b64(doc, obj):
    raw=doc.pdf.get_stream(obj) or b''
    return base64.b64encode(raw).decode('ascii')

def img_tag(doc, im, cls):
    return f'<img class="{cls}" src="data:image/jpeg;base64,{b64(doc, im["obj"])}" alt="">'

CSS = """
:root{--green:#1f9d3b;--greenbg:#e7f7ec;--bd:#dfe3e8;}
*{box-sizing:border-box}
body{font-family:-apple-system,Segoe UI,Roboto,Arial,sans-serif;margin:0;background:#f4f6f8;color:#1c2430}
header{background:#15314f;color:#fff;padding:18px 22px}
header h1{margin:0;font-size:20px}
header p{margin:4px 0 0;opacity:.85;font-size:13px}
.wrap{max-width:900px;margin:0 auto;padding:18px}
.legend{display:flex;gap:18px;font-size:13px;margin:10px 0 22px;flex-wrap:wrap}
.legend span{display:inline-flex;align-items:center;gap:6px}
.dot{width:14px;height:14px;border-radius:3px;display:inline-block}
.q{background:#fff;border:1px solid var(--bd);border-radius:10px;padding:16px 18px;margin:0 0 16px;box-shadow:0 1px 2px rgba(0,0,0,.04)}
.qhead{font-weight:700;color:#15314f;font-size:14px;margin-bottom:8px}
.stem img{display:block;max-width:100%;height:auto;margin:2px 0;image-rendering:auto}
.stem{margin-bottom:12px}
.dia{margin:8px 0}
.dia img{max-width:320px;height:auto;border:1px solid var(--bd);border-radius:6px}
.opt{display:flex;align-items:center;gap:10px;border:1px solid var(--bd);border-radius:8px;padding:8px 12px;margin:7px 0;background:#fff}
.opt.correct{background:var(--greenbg);border-color:var(--green)}
.olabel{font-weight:700;width:24px;height:24px;border-radius:50%;border:1px solid #c4ccd6;display:flex;align-items:center;justify-content:center;font-size:13px;flex:0 0 auto;color:#374a5e}
.opt.correct .olabel{background:var(--green);color:#fff;border-color:var(--green)}
.opt img{height:auto;max-width:100%;display:block}
.tick{margin-left:auto;color:var(--green);font-weight:700;font-size:13px;white-space:nowrap}
.ansline{margin-top:10px;font-size:13px;color:#15314f}
.ansline b{color:var(--green)}
footer{max-width:900px;margin:0 auto;padding:10px 18px 40px;color:#7b8794;font-size:12px}
.nav{margin:10px 0 0}
.nav a{color:#fff;text-decoration:none;font-size:13px;margin-right:14px;border:1px solid rgba(255,255,255,.4);padding:4px 10px;border-radius:6px}
"""

def render_set(doc, s, set_no, total_sets, prev_link, next_link):
    subj=s['part'][1] if s['part'] else 'General Knowledge and General Awareness'
    parts=[f"<!doctype html><html lang='en'><head><meta charset='utf-8'>",
           f"<meta name='viewport' content='width=device-width,initial-scale=1'>",
           f"<title>Set {set_no} - SSC GD GK/GA</title><style>{CSS}</style></head><body>"]
    nav=f"<div class='nav'><a href='index.html'>All Sets</a>"
    if prev_link: nav+=f"<a href='{prev_link}'>&larr; Prev</a>"
    if next_link: nav+=f"<a href='{next_link}'>Next &rarr;</a>"
    nav+="</div>"
    parts.append(f"<header><h1>Set {set_no} of {total_sets}</h1>"
                 f"<p>SSC GD &middot; PART-B &middot; {html.escape(subj)} &middot; 20 Questions</p>{nav}</header>")
    parts.append("<div class='wrap'>")
    parts.append("<div class='legend'>"
                 "<span><i class='dot' style='background:#1f9d3b'></i> Correct answer (green/yellow in source)</span>"
                 "<span>Questions &amp; options are the original images from the paper</span></div>")
    for q in s['questions']:
        ci=correct_index(q)
        parts.append("<div class='q'>")
        parts.append(f"<div class='qhead'>Q.No {q['qno']}</div>")
        parts.append("<div class='stem'>")
        for st in q['stem']:
            parts.append(img_tag(doc, st[0] if isinstance(st,tuple) else st, 'stemimg'))
        parts.append("</div>")
        for d,_pg in q['diagrams']:
            parts.append(f"<div class='dia'>{img_tag(doc, d, 'diaimg')}</div>")
        for i,(im,tagm,pg) in enumerate(q['options']):
            correct = (isinstance(ci,int) and ci==i+1) or tagm in ('G','Y')
            cls='opt correct' if correct else 'opt'
            tick="<span class='tick'>&#10003; Correct</span>" if correct else ""
            optimg=img_tag(doc, im, 'optimg') if im else '<i>(option image missing)</i>'
            parts.append(f"<div class='{cls}'><div class='olabel'>{LETTERS[i]}</div>{optimg}{tick}</div>")
        if isinstance(ci,int):
            parts.append(f"<div class='ansline'>Correct option: <b>{LETTERS[ci-1]}</b></div>")
        parts.append("</div>")
    parts.append("</div>")
    parts.append(f"<footer>Source: {s['file']} &middot; generated from candidate response sheet (images preserved, no OCR).</footer>")
    parts.append("</body></html>")
    return "\n".join(parts)

def main():
    allsets=[]
    docs={}
    for tag,path in [('F1','Gd/page1-223.pdf'),('F2','Gd/page224-445.pdf')]:
        doc,sets,bg=extract_file(path, tag)
        docs[tag]=doc
        for s in sets: allsets.append(s)
    total=len(allsets)
    index=["<!doctype html><html lang='en'><head><meta charset='utf-8'>",
           "<meta name='viewport' content='width=device-width,initial-scale=1'>",
           f"<title>SSC GD GK/GA - {total} Sets</title><style>{CSS}"
           ".grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(150px,1fr));gap:12px}"
           ".card{background:#fff;border:1px solid var(--bd);border-radius:10px;padding:16px;text-decoration:none;color:#15314f;font-weight:600;text-align:center}"
           ".card:hover{border-color:#15314f}</style></head><body>"]
    index.append(f"<header><h1>SSC GD &mdash; General Knowledge &amp; General Awareness</h1>"
                 f"<p>{total} sets &middot; 20 questions each &middot; {total*20} questions &middot; correct answers highlighted</p></header>")
    index.append("<div class='wrap'><div class='grid'>")
    for i,s in enumerate(allsets):
        set_no=i+1
        fn=f"set_{set_no:02d}.html"
        prev_link=f"set_{set_no-1:02d}.html" if set_no>1 else None
        next_link=f"set_{set_no+1:02d}.html" if set_no<total else None
        h=render_set(docs[s['file']], s, set_no, total, prev_link, next_link)
        with open(os.path.join(OUT, fn),'w') as f: f.write(h)
        index.append(f"<a class='card' href='{fn}'>Set {set_no}</a>")
    index.append("</div></div>")
    index.append("<footer>Each set links to its 20 questions with the correct option highlighted in green.</footer></body></html>")
    with open(os.path.join(OUT,'index.html'),'w') as f: f.write("\n".join(index))
    # size report
    tot=sum(os.path.getsize(os.path.join(OUT,f)) for f in os.listdir(OUT))
    print(f"generated {total} set files + index in {OUT}/  (total {tot/1e6:.1f} MB)")

if __name__=='__main__':
    main()
