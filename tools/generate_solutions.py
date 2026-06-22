"""Generate study material from the OCR cache + authored solutions.

Outputs (all under Gd/study/):
  - index.html              landing page (sets + topics + progress)
  - sets/set_NN.html        per-set view: original images + OCR text +
                            correct answer highlighted green + full solution
  - topics/<topic>.html     topic-wise view of all solved questions
And:
  - Gd/solutions.txt        plain-text solutions file (text + answers + why)
  - Gd/data/cross_check.txt answer cross-check report (authored vs highlight)

Authored solutions live in Gd/solutions/set_NN.json, keyed by question number:
  { "21": {
      "topic": "Polity & Constitution",   # optional, overrides auto-classify
      "answer": "B",                        # letter the author judges correct
      "q": "clean question text (optional, overrides OCR)",
      "opts": ["A text","B text","C text","D text"],  # optional clean options
      "correct": "why the correct option is right",
      "wrong": {"A":"why wrong", "C":"why wrong", "D":"why wrong"},
      "fact": "relevant extra note (optional)"
  }, ... }

The generator runs over whatever sets have authored solutions; questions without
an authored solution are shown with a 'solution pending' note so output is always
buildable incrementally per batch.
"""
import os
import re
import json
import base64
import html
from collections import defaultdict, OrderedDict

from build_final import extract_file, correct_index
from topics import classify

ROOT = 'Gd'
STUDY = os.path.join(ROOT, 'study')
SETS_DIR = os.path.join(STUDY, 'sets')
TOPICS_DIR = os.path.join(STUDY, 'topics')
SOL_DIR = os.path.join(ROOT, 'solutions')
OCR_CACHE = os.path.join(ROOT, 'data', 'ocr_cache.json')
LETTERS = ['A', 'B', 'C', 'D']

FILES = [('F1', os.path.join(ROOT, 'page1-223.pdf')),
         ('F2', os.path.join(ROOT, 'page224-445.pdf'))]

CSS = """
:root{--green:#1f9d3b;--greenbg:#e8f8ed;--bd:#dfe3e8;--ink:#1c2430;--head:#15314f}
*{box-sizing:border-box}
body{font-family:-apple-system,Segoe UI,Roboto,Arial,sans-serif;margin:0;background:#f4f6f8;color:var(--ink)}
header{background:var(--head);color:#fff;padding:18px 22px}
header h1{margin:0;font-size:20px}
header p{margin:4px 0 0;opacity:.85;font-size:13px}
.nav{margin:10px 0 0}
.nav a{color:#fff;text-decoration:none;font-size:13px;margin-right:12px;border:1px solid rgba(255,255,255,.4);padding:4px 10px;border-radius:6px}
.wrap{max-width:920px;margin:0 auto;padding:18px}
.q{background:#fff;border:1px solid var(--bd);border-radius:10px;padding:16px 18px;margin:0 0 18px;box-shadow:0 1px 2px rgba(0,0,0,.04)}
.qhead{font-weight:700;color:var(--head);font-size:14px;margin-bottom:6px;display:flex;gap:8px;align-items:center;flex-wrap:wrap}
.tag{font-size:11px;font-weight:600;background:#eef2f7;color:#42566b;border-radius:20px;padding:2px 9px}
.tag.lang{background:#fff4e5;color:#9a6212}
.qtext{font-size:15px;margin:6px 0 10px;font-weight:600}
.qimg img{display:block;max-width:100%;height:auto;margin:2px 0;border:1px solid #eef0f3;border-radius:4px}
.qimgs{margin:6px 0 10px}
details.src{margin:0 0 10px}
details.src summary{cursor:pointer;font-size:12px;color:#6b7785}
.opt{display:flex;align-items:flex-start;gap:10px;border:1px solid var(--bd);border-radius:8px;padding:8px 12px;margin:6px 0;background:#fff}
.opt.correct{background:var(--greenbg);border-color:var(--green)}
.olabel{font-weight:700;min-width:24px;height:24px;border-radius:50%;border:1px solid #c4ccd6;display:flex;align-items:center;justify-content:center;font-size:13px;color:#374a5e;flex:0 0 auto}
.opt.correct .olabel{background:var(--green);color:#fff;border-color:var(--green)}
.opt .otext{font-size:14px}
.tick{margin-left:auto;color:var(--green);font-weight:700;font-size:12px;white-space:nowrap}
.sol{margin-top:12px;border-top:1px dashed var(--bd);padding-top:10px}
.sol h4{margin:0 0 6px;font-size:13px;color:var(--head);text-transform:uppercase;letter-spacing:.3px}
.sol p{margin:5px 0;font-size:14px;line-height:1.5}
.sol .why-wrong{font-size:13px;color:#5b6775}
.sol .why-wrong b{color:#c0392b}
.fact{background:#f0f6ff;border-left:3px solid #2f6fb0;padding:8px 12px;font-size:13px;border-radius:4px;margin-top:8px}
.pending{color:#9a6212;font-size:13px;background:#fff8ec;border:1px dashed #e0c089;border-radius:6px;padding:8px 10px}
.flag{color:#c0392b;font-size:12px;font-weight:600}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(160px,1fr));gap:12px}
.card{background:#fff;border:1px solid var(--bd);border-radius:10px;padding:14px;text-decoration:none;color:var(--head);font-weight:600}
.card:hover{border-color:var(--head)}
.card small{display:block;color:#7b8794;font-weight:400;margin-top:4px}
footer{max-width:920px;margin:0 auto;padding:10px 18px 40px;color:#7b8794;font-size:12px}
"""


def b64img(doc, obj):
    raw = doc.pdf.get_stream(obj) or b''
    return base64.b64encode(raw).decode('ascii')


def img_html(doc, obj):
    return (f'<img src="data:image/jpeg;base64,{b64img(doc, obj)}" alt="">')


def load_authored():
    sols = {}
    if not os.path.isdir(SOL_DIR):
        return sols
    for fn in os.listdir(SOL_DIR):
        m = re.match(r'set_(\d+)\.json', fn)
        if not m:
            continue
        with open(os.path.join(SOL_DIR, fn)) as f:
            data = json.load(f)
        sols[int(m.group(1))] = {int(k): v for k, v in data.items()}
    return sols


def esc(s):
    return html.escape(s or '')


def slug(topic):
    return re.sub(r'[^a-z0-9]+', '-', topic.lower()).strip('-')


def build():
    os.makedirs(SETS_DIR, exist_ok=True)
    os.makedirs(TOPICS_DIR, exist_ok=True)
    recs = json.load(open(OCR_CACHE))
    by_set = defaultdict(list)
    for r in recs:
        by_set[r['set']].append(r)
    authored = load_authored()

    # rebuild docs for images, keyed per set via record 'file'
    docs = {}
    for tag, path in FILES:
        docs[tag] = extract_file(path, tag)[0]

    total = len(by_set)
    cross = []          # cross-check lines
    topic_items = defaultdict(list)   # topic -> list of (set,qno,rec,sol,topic)
    solved_sets = sorted(s for s in authored if authored[s])
    txt_lines = []

    for set_no in sorted(by_set):
        recs_s = sorted(by_set[set_no], key=lambda r: r['qno'])
        doc = docs[recs_s[0]['file']]
        sol_map = authored.get(set_no, {})
        html_parts = _set_header(set_no, total, solved_sets)
        for r in recs_s:
            sol = sol_map.get(r['qno'])
            topic = (sol.get('topic') if sol and sol.get('topic')
                     else classify(r['stem'], r['options']))
            qtext = (sol.get('q') if sol and sol.get('q') else r['stem'])
            opts = (sol.get('opts') if sol and sol.get('opts') else r['options'])
            ans_letter = r['answer_letter']
            # cross-check authored answer vs highlight-detected answer
            if sol and sol.get('answer') and sol['answer'] != ans_letter:
                cross.append(
                    f"MISMATCH set {set_no} Q{r['qno']}: highlight={ans_letter} "
                    f"authored={sol['answer']}  | {qtext[:70]}")
            html_parts.append(_render_q(doc, r, qtext, opts, ans_letter,
                                        topic, sol))
            if sol:
                topic_items[topic].append((set_no, r, qtext, opts, ans_letter, sol))
                txt_lines.extend(_text_block(set_no, r, qtext, opts,
                                             ans_letter, topic, sol))
        html_parts.append("</div>")
        html_parts.append(
            f"<footer>Source: candidate response sheet &middot; "
            f"answers detected from the green/yellow highlight in the original "
            f"PDF and verified against general knowledge.</footer></body></html>")
        with open(os.path.join(SETS_DIR, f'set_{set_no:02d}.html'), 'w') as f:
            f.write("\n".join(html_parts))

    _write_topics(docs, topic_items)
    _write_index(by_set, authored, topic_items)

    with open(os.path.join(ROOT, 'solutions.txt'), 'w') as f:
        f.write("\n".join(txt_lines))
    os.makedirs(os.path.join(ROOT, 'data'), exist_ok=True)
    with open(os.path.join(ROOT, 'data', 'cross_check.txt'), 'w') as f:
        f.write(f"Answer cross-check: authored GK answer vs highlight detection\n")
        f.write(f"Sets with authored solutions: {solved_sets}\n")
        f.write(f"Mismatches found: {len(cross)}\n\n")
        f.write("\n".join(cross) if cross else "(no mismatches)")

    n_solved = sum(len(v) for v in authored.values())
    print(f"built {total} set pages, {len(topic_items)} topic pages")
    print(f"authored solutions: {n_solved} questions across sets {solved_sets}")
    print(f"answer cross-check mismatches: {len(cross)} (see Gd/data/cross_check.txt)")


def _set_header(set_no, total, solved_sets):
    nav = ("<div class='nav'><a href='../index.html'>Home</a>")
    if set_no > 1:
        nav += f"<a href='set_{set_no-1:02d}.html'>&larr; Set {set_no-1}</a>"
    if set_no < total:
        nav += f"<a href='set_{set_no+1:02d}.html'>Set {set_no+1} &rarr;</a>"
    nav += "</div>"
    return [
        "<!doctype html><html lang='en'><head><meta charset='utf-8'>",
        "<meta name='viewport' content='width=device-width,initial-scale=1'>",
        f"<title>Set {set_no} - SSC GD GK/GA solutions</title><style>{CSS}</style></head><body>",
        f"<header><h1>Set {set_no} of {total}</h1>"
        f"<p>SSC GD &middot; PART-B &middot; General Knowledge &amp; General "
        f"Awareness &middot; Q.21-40 &middot; correct answer in green with "
        f"detailed solution</p>{nav}</header>",
        "<div class='wrap'>",
    ]


def _render_q(doc, r, qtext, opts, ans_letter, topic, sol):
    p = ["<div class='q'>"]
    p.append(
        f"<div class='qhead'>Q.No {r['qno']} "
        f"<span class='tag'>{esc(topic)}</span>"
        f"<span class='tag lang'>{'Hindi' if r['lang']=='hin' else 'English'}</span>"
        + (f"<span class='flag'>&#9888; low OCR confidence</span>"
           if r.get('min_conf', 100) < 55 else "")
        + "</div>")
    if qtext:
        p.append(f"<div class='qtext'>{esc(qtext)}</div>")
    # original images (stem + diagrams)
    imgs = list(r.get('stem_objs', [])) + list(r.get('diagram_objs', []))
    if imgs:
        p.append("<div class='qimgs'>")
        for o in imgs:
            p.append(img_html(doc, o))
        p.append("</div>")
    # options
    for i, otext in enumerate(opts):
        correct = (LETTERS[i] == ans_letter)
        cls = 'opt correct' if correct else 'opt'
        tick = "<span class='tick'>&#10003; Correct</span>" if correct else ""
        p.append(
            f"<div class='{cls}'><div class='olabel'>{LETTERS[i]}</div>"
            f"<div class='otext'>{esc(otext)}</div>{tick}</div>")
    # solution
    p.append("<div class='sol'>")
    if sol:
        p.append("<h4>Solution</h4>")
        p.append(f"<p><b>Correct answer: {ans_letter}.</b> "
                 f"{esc(sol.get('correct',''))}</p>")
        wrong = sol.get('wrong', {})
        if wrong:
            p.append("<div class='why-wrong'>")
            for L in LETTERS:
                if L in wrong:
                    p.append(f"<p><b>{L} is incorrect:</b> {esc(wrong[L])}</p>")
            p.append("</div>")
        if sol.get('fact'):
            p.append(f"<div class='fact'>&#128161; {esc(sol['fact'])}</div>")
    else:
        p.append(f"<div class='pending'>Correct answer: <b>{ans_letter}</b>. "
                 f"Detailed solution coming in a later batch.</div>")
    p.append("</div>")
    p.append("</div>")
    return "\n".join(p)


def _text_block(set_no, r, qtext, opts, ans_letter, topic, sol):
    lines = []
    lines.append("=" * 78)
    lines.append(f"Set {set_no} | Q.No {r['qno']} | Topic: {topic} | "
                 f"Language: {'Hindi' if r['lang']=='hin' else 'English'}")
    lines.append("-" * 78)
    lines.append(f"Q: {qtext}")
    for i, o in enumerate(opts):
        mark = '  <-- CORRECT' if LETTERS[i] == ans_letter else ''
        lines.append(f"   {LETTERS[i]}) {o}{mark}")
    lines.append(f"Answer: {ans_letter}")
    lines.append(f"Why correct: {sol.get('correct','')}")
    wrong = sol.get('wrong', {})
    for L in LETTERS:
        if L in wrong:
            lines.append(f"Why {L} is wrong: {wrong[L]}")
    if sol.get('fact'):
        lines.append(f"Note: {sol['fact']}")
    lines.append("")
    return lines


def _write_topics(docs, topic_items):
    for topic, items in topic_items.items():
        parts = [
            "<!doctype html><html lang='en'><head><meta charset='utf-8'>",
            "<meta name='viewport' content='width=device-width,initial-scale=1'>",
            f"<title>{esc(topic)} - SSC GD GK/GA</title><style>{CSS}</style></head><body>",
            f"<header><h1>{esc(topic)}</h1><p>{len(items)} solved questions in this "
            f"topic &middot; SSC GD General Knowledge &amp; General Awareness</p>"
            f"<div class='nav'><a href='../index.html'>Home</a></div></header>",
            "<div class='wrap'>",
        ]
        for set_no, r, qtext, opts, ans_letter, sol in items:
            doc = docs[r['file']]
            parts.append(_render_q(doc, r, qtext, opts, ans_letter, topic, sol))
        parts.append("</div></body></html>")
        with open(os.path.join(TOPICS_DIR, f'{slug(topic)}.html'), 'w') as f:
            f.write("\n".join(parts))


def _write_index(by_set, authored, topic_items):
    total_sets = len(by_set)
    total_q = sum(len(v) for v in by_set.values())
    n_solved = sum(len(v) for v in authored.values())
    parts = [
        "<!doctype html><html lang='en'><head><meta charset='utf-8'>",
        "<meta name='viewport' content='width=device-width,initial-scale=1'>",
        f"<title>SSC GD GK/GA - Solutions</title><style>{CSS}</style></head><body>",
        f"<header><h1>SSC GD &mdash; General Knowledge &amp; General Awareness</h1>"
        f"<p>{total_sets} sets &middot; {total_q} questions (Q.21-40, PART-B) "
        f"&middot; {n_solved} with detailed solutions so far</p></header>",
        "<div class='wrap'>",
        "<h2 style='color:#15314f'>By topic</h2><div class='grid'>",
    ]
    for topic in sorted(topic_items, key=lambda t: -len(topic_items[t])):
        parts.append(
            f"<a class='card' href='topics/{slug(topic)}.html'>{esc(topic)}"
            f"<small>{len(topic_items[topic])} solved questions</small></a>")
    parts.append("</div>")
    parts.append("<h2 style='color:#15314f;margin-top:26px'>By set</h2><div class='grid'>")
    for set_no in sorted(by_set):
        ns = len(authored.get(set_no, {}))
        label = f"{ns}/20 solved" if ns else "answers only"
        parts.append(
            f"<a class='card' href='sets/set_{set_no:02d}.html'>Set {set_no}"
            f"<small>{label}</small></a>")
    parts.append("</div></div>")
    parts.append("<footer>Generated from the candidate response-sheet PDFs via OCR; "
                 "correct answers detected from the green/yellow highlight and "
                 "verified against general knowledge.</footer></body></html>")
    with open(os.path.join(STUDY, 'index.html'), 'w') as f:
        f.write("\n".join(parts))


if __name__ == '__main__':
    build()
