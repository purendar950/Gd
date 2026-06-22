import os, base64, html
from build_final import extract_file, correct_index

OUT='Gd/study'
os.makedirs(OUT, exist_ok=True)
LET=['A','B','C','D']

def b64(doc, obj):
    raw=doc.pdf.get_stream(obj) or b''
    return base64.b64encode(raw).decode('ascii')

def img_tag(doc, im, cls):
    return f'<img class="{cls}" src="data:image/jpeg;base64,{b64(doc, im["obj"])}" alt="">'

allsets=[]; docs={}
for tag,path in [('F1','Gd/page1-223.pdf'),('F2','Gd/page224-445.pdf')]:
    doc,sets,bg=extract_file(path, tag)
    docs[tag]=doc
    for s in sets: allsets.append(s)
total=len(allsets)

# ---------- 1) plain-text solutions file ----------
lines=[]
lines.append("SSC GD - GENERAL KNOWLEDGE & GENERAL AWARENESS (PART-B)")
lines.append(f"{total} sets x 20 questions = {total*20} questions")
lines.append("")
lines.append("Each entry lists the VERIFIED correct answer (from the green/yellow answer key in the PDF).")
lines.append("The 'Solution' field is left blank to be filled with the explanation once the")
lines.append("question text is OCR'd (needs an internet-enabled session to install OCR).")
lines.append("="*70)
for i,s in enumerate(allsets):
    setno=i+1
    lines.append("")
    lines.append(f"=== SET {setno:02d}  (General Knowledge & General Awareness)  [source {s['file']}] ===")
    for q in s['questions']:
        ci=correct_index(q)
        ans=LET[ci-1] if isinstance(ci,int) else '?'
        lines.append(f"Q.No {q['qno']:>2} | Correct Answer: {ans} | Solution: ____________________________________")
with open(os.path.join(OUT,'solutions.txt'),'w') as f:
    f.write("\n".join(lines)+"\n")

# ---------- 2) HTML with a Solution section per question ----------
CSS = """
:root{--green:#1f9d3b;--greenbg:#e7f7ec;--bd:#dfe3e8;--sol:#fff8e6;--solbd:#f0d98a}
*{box-sizing:border-box}body{font-family:-apple-system,Segoe UI,Roboto,Arial,sans-serif;margin:0;background:#f4f6f8;color:#1c2430}
header{background:#15314f;color:#fff;padding:18px 22px}header h1{margin:0;font-size:20px}header p{margin:4px 0 0;opacity:.85;font-size:13px}
.wrap{max-width:900px;margin:0 auto;padding:18px}
.q{background:#fff;border:1px solid var(--bd);border-radius:10px;padding:16px 18px;margin:0 0 16px}
.qhead{font-weight:700;color:#15314f;font-size:14px;margin-bottom:8px}
.stem img{display:block;max-width:100%;height:auto;margin:2px 0}.stem{margin-bottom:12px}
.dia img{max-width:320px;height:auto;border:1px solid var(--bd);border-radius:6px;margin:8px 0}
.opt{display:flex;align-items:center;gap:10px;border:1px solid var(--bd);border-radius:8px;padding:8px 12px;margin:7px 0}
.opt.correct{background:var(--greenbg);border-color:var(--green)}
.olabel{font-weight:700;width:24px;height:24px;border-radius:50%;border:1px solid #c4ccd6;display:flex;align-items:center;justify-content:center;font-size:13px;flex:0 0 auto;color:#374a5e}
.opt.correct .olabel{background:var(--green);color:#fff;border-color:var(--green)}
.opt img{height:auto;max-width:100%;display:block}.tick{margin-left:auto;color:var(--green);font-weight:700;font-size:13px}
.sol{margin-top:10px;background:var(--sol);border:1px solid var(--solbd);border-radius:8px;padding:10px 12px;font-size:13.5px}
.sol .ans{font-weight:700;color:#15314f}.sol .ans b{color:var(--green)}
.sol .txt{margin-top:6px;color:#6b5d2a;font-style:italic}
.nav a{color:#fff;text-decoration:none;font-size:13px;margin-right:14px;border:1px solid rgba(255,255,255,.4);padding:4px 10px;border-radius:6px}.nav{margin-top:10px}
"""
def render(doc, s, setno, prev, nxt):
    p=[f"<!doctype html><html lang='en'><head><meta charset='utf-8'>",
       "<meta name='viewport' content='width=device-width,initial-scale=1'>",
       f"<title>Set {setno} - Solutions</title><style>{CSS}</style></head><body>"]
    nav="<div class='nav'><a href='index.html'>All Sets</a>"
    if prev: nav+=f"<a href='{prev}'>&larr; Prev</a>"
    if nxt: nav+=f"<a href='{nxt}'>Next &rarr;</a>"
    nav+="</div>"
    p.append(f"<header><h1>Set {setno} of {total} &mdash; Questions &amp; Solutions</h1>"
             f"<p>SSC GD &middot; PART-B General Knowledge &amp; General Awareness &middot; 20 questions</p>{nav}</header>")
    p.append("<div class='wrap'>")
    for q in s['questions']:
        ci=correct_index(q); ans=LET[ci-1] if isinstance(ci,int) else '?'
        p.append("<div class='q'>")
        p.append(f"<div class='qhead'>Q.No {q['qno']}</div><div class='stem'>")
        for st in q['stem']:
            im=st[0] if isinstance(st,tuple) else st
            p.append(img_tag(doc, im,'s'))
        p.append("</div>")
        for d,_pg in q['diagrams']:
            p.append(f"<div class='dia'>{img_tag(doc,d,'d')}</div>")
        for idx,(im,tagm,pg) in enumerate(q['options']):
            corr=(isinstance(ci,int) and ci==idx+1)
            cls='opt correct' if corr else 'opt'
            tick="<span class='tick'>&#10003;</span>" if corr else ""
            p.append(f"<div class='{cls}'><div class='olabel'>{LET[idx]}</div>{img_tag(doc,im,'o')}{tick}</div>")
        p.append("<div class='sol'>"
                 f"<div class='ans'>Correct Answer: <b>{ans}</b></div>"
                 "<div class='txt'>Solution explanation pending (requires question text via OCR / internet-enabled session).</div>"
                 "</div>")
        p.append("</div>")
    p.append("</div></body></html>")
    return "\n".join(p)

for i,s in enumerate(allsets):
    setno=i+1
    fn=f"sol_set_{setno:02d}.html"
    prev=f"sol_set_{setno-1:02d}.html" if setno>1 else None
    nxt=f"sol_set_{setno+1:02d}.html" if setno<total else None
    open(os.path.join(OUT,fn),'w').write(render(docs[s['file']], s, setno, prev, nxt))

tot=sum(os.path.getsize(os.path.join(OUT,f)) for f in os.listdir(OUT) if f.startswith('sol_'))
print(f"wrote solutions.txt and {total} sol_set_*.html ({tot/1e6:.1f} MB)")
print("answer-key sample (set 1):")
print("\n".join(lines[7:30]))
