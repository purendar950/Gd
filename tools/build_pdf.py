"""Build a single combined PDF of all 59 sets with detailed solutions.

Reads data/ocr_cache.json + authored solutions in solutions/set_NN.json and
renders Gd/SSC_GD_GK_Solutions.pdf via WeasyPrint.

- All explanations are in English; Hindi question text is rendered with the
  Noto Sans Devanagari font.
- Each question shows: question text, the original stem/diagram image from the
  paper, the four options (correct one highlighted green), and the full solution
  (why correct, why each other option is wrong, extra fact).
- Questions not yet authored show the detected correct answer with a note.
- A PDF outline (bookmarks) is generated per set for easy navigation.
"""
import os
import re
import json
import base64
import html
from collections import defaultdict

from build_final import extract_file
from topics import classify

ROOT = 'Gd'
OCR_CACHE = os.path.join(ROOT, 'data', 'ocr_cache.json')
SOL_DIR = os.path.join(ROOT, 'solutions')
OUT_PDF = os.path.join(ROOT, 'SSC_GD_GK_Solutions.pdf')
LETTERS = ['A', 'B', 'C', 'D']
FILES = [('F1', os.path.join(ROOT, 'page1-223.pdf')),
         ('F2', os.path.join(ROOT, 'page224-445.pdf'))]

PDF_CSS = """
@page { size: A4; margin: 16mm 14mm 18mm 14mm;
  @bottom-center { content: "SSC GD - GK & General Awareness - PART-B"; font-size:8px; color:#888; }
  @bottom-right { content: counter(page); font-size:9px; color:#555; } }
@page :first { @bottom-center { content: ""; } @bottom-right { content: ""; } }
* { box-sizing:border-box; }
body { font-family:"Noto Sans","Noto Sans Devanagari",sans-serif; color:#1c2430; font-size:10.5px; line-height:1.45; }
h1.cover { font-size:30px; color:#15314f; margin:60mm 0 6px; text-align:center; }
.cover-sub { text-align:center; color:#42566b; font-size:13px; }
.cover-meta { text-align:center; color:#7b8794; font-size:11px; margin-top:18px; }
.set { page-break-before: always; }
.set-h { background:#15314f; color:#fff; padding:7px 12px; border-radius:6px; font-size:14px; font-weight:700; margin:0 0 10px; bookmark-level:1; bookmark-label:content(); }
.q { border:1px solid #dfe3e8; border-radius:7px; padding:9px 11px; margin:0 0 9px; page-break-inside: avoid; }
.qhead { font-weight:700; color:#15314f; font-size:10.5px; margin-bottom:3px; }
.tag { font-size:8.5px; font-weight:600; background:#eef2f7; color:#42566b; border-radius:10px; padding:1px 7px; margin-left:5px; }
.qtext { font-weight:700; margin:3px 0 5px; font-size:11px; }
.qimg { margin:3px 0 6px; }
.qimg img { max-width:84%; max-height:120px; border:1px solid #eef0f3; }
.opt { border:1px solid #dfe3e8; border-radius:5px; padding:3px 8px; margin:3px 0; }
.opt.correct { background:#e8f8ed; border-color:#1f9d3b; }
.opt .l { font-weight:700; display:inline-block; min-width:15px; }
.opt.correct .l { color:#1f9d3b; }
.opt .tick { color:#1f9d3b; font-weight:700; font-size:9px; float:right; }
.sol { border-top:1px dashed #dfe3e8; margin-top:7px; padding-top:5px; }
.sol .h { font-size:9px; font-weight:700; color:#15314f; text-transform:uppercase; letter-spacing:.3px; }
.sol p { margin:3px 0; }
.sol .ww { color:#5b6775; font-size:9.7px; }
.sol .ww b { color:#b03a2e; }
.fact { background:#f0f6ff; border-left:2px solid #2f6fb0; padding:4px 8px; font-size:9.5px; margin-top:5px; }
.pending { color:#9a6212; background:#fff8ec; border:1px dashed #e0c089; border-radius:5px; padding:5px 8px; font-size:9.7px; }
.toc { page-break-after: always; }
.toc h2 { color:#15314f; }
.toc-row { font-size:10px; padding:2px 0; border-bottom:1px dotted #e0e4e8; }
"""


def esc(s):
    return html.escape(s or '')


def b64(doc, obj):
    raw = doc.pdf.get_stream(obj) or b''
    return base64.b64encode(raw).decode('ascii')


def load_authored():
    sols = {}
    if os.path.isdir(SOL_DIR):
        for fn in os.listdir(SOL_DIR):
            m = re.match(r'set_(\d+)\.json', fn)
            if m:
                with open(os.path.join(SOL_DIR, fn)) as f:
                    sols[int(m.group(1))] = {int(k): v for k, v in json.load(f).items()}
    return sols


def build(include_images=True):
    recs = json.load(open(OCR_CACHE))
    by_set = defaultdict(list)
    for r in recs:
        by_set[r['set']].append(r)
    authored = load_authored()
    docs = {tag: extract_file(path, tag)[0] for tag, path in FILES}

    total_sets = len(by_set)
    total_q = len(recs)
    n_solved = sum(len(v) for v in authored.values())

    parts = ["<!doctype html><html lang='en'><head><meta charset='utf-8'>",
             f"<style>{PDF_CSS}</style></head><body>"]
    # cover
    parts.append(
        f"<h1 class='cover'>SSC GD<br>General Knowledge &amp; General Awareness</h1>"
        f"<div class='cover-sub'>PART-B &middot; Questions 21-40 &middot; with detailed solutions</div>"
        f"<div class='cover-meta'>{total_sets} sets &middot; {total_q} questions &middot; "
        f"{n_solved} with full solutions<br>Correct answers shown in green. "
        f"Explanations in English; original Hindi question text retained.</div>")

    for set_no in sorted(by_set):
        recs_s = sorted(by_set[set_no], key=lambda r: r['qno'])
        doc = docs[recs_s[0]['file']]
        sol_map = authored.get(set_no, {})
        parts.append(f"<div class='set'><div class='set-h' "
                     f"id='set{set_no}'>Set {set_no} of {total_sets}</div>")
        for r in recs_s:
            sol = sol_map.get(r['qno'])
            topic = (sol.get('topic') if sol and sol.get('topic')
                     else classify(r['stem'], r['options']))
            qtext = (sol.get('q') if sol and sol.get('q') else r['stem'])
            opts = (sol.get('opts') if sol and sol.get('opts') else r['options'])
            ans = r['answer_letter']
            parts.append("<div class='q'>")
            parts.append(f"<div class='qhead'>Q.No {r['qno']}"
                         f"<span class='tag'>{esc(topic)}</span>"
                         f"<span class='tag'>{'Hindi' if r['lang']=='hin' else 'English'}</span></div>")
            if qtext:
                parts.append(f"<div class='qtext'>{esc(qtext)}</div>")
            if include_images:
                imgs = list(r.get('diagram_objs', [])) or list(r.get('stem_objs', []))
                # show diagram if present (carries the question), else stem image
                for o in imgs[:1]:
                    parts.append(f"<div class='qimg'><img src='data:image/jpeg;base64,{b64(doc,o)}'></div>")
            for i, o in enumerate(opts):
                cor = (LETTERS[i] == ans)
                cls = 'opt correct' if cor else 'opt'
                tick = "<span class='tick'>&#10003;</span>" if cor else ""
                parts.append(f"<div class='{cls}'><span class='l'>{LETTERS[i]}.</span> "
                             f"{esc(o)}{tick}</div>")
            parts.append("<div class='sol'>")
            if sol:
                parts.append(f"<div class='h'>Solution &mdash; correct answer: {ans}</div>")
                parts.append(f"<p>{esc(sol.get('correct',''))}</p>")
                wrong = sol.get('wrong', {})
                if wrong:
                    parts.append("<div class='ww'>")
                    for L in LETTERS:
                        if L in wrong:
                            parts.append(f"<p><b>{L} is incorrect:</b> {esc(wrong[L])}</p>")
                    parts.append("</div>")
                if sol.get('fact'):
                    parts.append(f"<div class='fact'>{esc(sol['fact'])}</div>")
            else:
                parts.append(f"<div class='pending'>Correct answer: <b>{ans}</b>. "
                             f"Detailed solution to be added.</div>")
            parts.append("</div></div>")
        parts.append("</div>")
    parts.append("</body></html>")

    from weasyprint import HTML
    HTML(string="\n".join(parts)).write_pdf(OUT_PDF)
    size = os.path.getsize(OUT_PDF)
    print(f"wrote {OUT_PDF} ({size/1024/1024:.1f} MB), {total_sets} sets, "
          f"{total_q} questions, {n_solved} solved")


if __name__ == '__main__':
    build()
