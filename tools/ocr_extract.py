"""OCR every question stem + 4 option images across both SSC GD PDFs.

Produces a JSON cache: Gd/data/ocr_cache.json with one record per question:
  {set, qno, file, stem, options:[4 texts], answer_index (1-4), answer_letter,
   answer_text, highlight_tag (G/Y), n_stem_imgs, n_diagrams,
   stem_objs, option_objs, diagram_objs}

Run from /projects/sandbox with PYTHONPATH=Gd/tools and
PATH including /projects/sandbox/ocrbin (so the tesseract wrapper resolves).
"""
import io, os, json, sys
from PIL import Image, ImageOps
import pytesseract
from build_final import extract_file, correct_index

FILES = [('F1', 'Gd/page1-223.pdf'), ('F2', 'Gd/page224-445.pdf')]
LETTERS = ['A', 'B', 'C', 'D']
OUT = 'Gd/data/ocr_cache.json'
SETDIR = 'Gd/data/sets'


def _ocr_data(im, psm, lang):
    """Return (text, mean_confidence) using image_to_data."""
    d = pytesseract.image_to_data(
        im, config=f'--psm {psm} --oem 1 -l {lang}',
        output_type=pytesseract.Output.DICT)
    words = []
    confs = []
    for txt, c in zip(d['text'], d['conf']):
        try:
            ci = int(c)
        except (ValueError, TypeError):
            ci = -1
        if ci >= 0 and txt.strip():
            words.append(txt.strip())
            confs.append(ci)
    text = ' '.join(' '.join(words).split())
    mean_conf = sum(confs) / len(confs) if confs else 0.0
    return text, mean_conf


def ocr_image(doc, obj, psm, cache):
    """OCR an image in English and Hindi; pick the higher-confidence result.

    Returns (text, lang, conf) where lang in {'eng','hin',''}.
    """
    if obj in cache:
        return cache[obj]
    raw = doc.pdf.get_stream(obj)
    if not raw:
        cache[obj] = ('', '', 0.0)
        return cache[obj]
    try:
        im = Image.open(io.BytesIO(raw)).convert('L')
    except Exception:
        cache[obj] = ('', '', 0.0)
        return cache[obj]
    w, h = im.size
    im = im.resize((max(1, w * 4), max(1, h * 4)), Image.LANCZOS)
    im = ImageOps.autocontrast(im)
    eng_t, eng_c = _ocr_data(im, psm, 'eng')
    hin_t, hin_c = _ocr_data(im, psm, 'hin')
    if hin_c > eng_c:
        res = (hin_t, 'hin', round(hin_c, 1))
    else:
        res = (eng_t, 'eng', round(eng_c, 1))
    cache[obj] = res
    return res


def im_obj(it):
    return (it[0] if isinstance(it, tuple) else it)['obj']


def main():
    docs = {}
    allsets = []
    for tag, path in FILES:
        doc, sets, bg = extract_file(path, tag)
        docs[tag] = doc
        allsets.extend(sets)

    os.makedirs(SETDIR, exist_ok=True)
    img_cache = {}  # per-doc obj cache shared via (tag,obj)
    total = len(allsets)
    only = None
    if len(sys.argv) > 1 and sys.argv[1].startswith('--only='):
        only = set(int(x) for x in sys.argv[1].split('=', 1)[1].split(','))
    for si, s in enumerate(allsets):
        set_no = si + 1
        if only is not None and set_no not in only:
            continue
        setpath = os.path.join(SETDIR, f'set_{set_no:02d}.json')
        if os.path.exists(setpath) and only is None:
            continue  # resume: skip completed sets
        set_records = []
        doc = docs[s['file']]
        dc = img_cache.setdefault(s['file'], {})
        for q in s['questions']:
            stem_objs = [im_obj(st) for st in q['stem']]
            diagram_objs = [d[0]['obj'] for d in q['diagrams']]
            stem_parts = [ocr_image(doc, o, 6, dc) for o in stem_objs]
            stem_text = ' '.join(t for t, lg, cf in stem_parts).strip()
            # Some questions have their text inside a diagram/figure image
            # (match-the-following tables, assertion-reason, etc.) rather than
            # a separate text image. OCR the diagram(s) as a fallback stem.
            diag_parts = []
            if not stem_text and diagram_objs:
                diag_parts = [ocr_image(doc, o, 6, dc) for o in diagram_objs]
                stem_text = ' '.join(t for t, lg, cf in diag_parts).strip()
            options = []
            opt_langs = []
            opt_confs = []
            opt_objs = []
            ci = correct_index(q)
            ans_idx = ci if isinstance(ci, int) else None
            hl_tag = None
            for i, opt in enumerate(q['options']):
                im = opt[0]
                tagm = opt[1]
                opt_objs.append(im['obj'])
                otext, olang, oconf = ocr_image(doc, im['obj'], 7, dc)
                options.append(otext)
                opt_langs.append(olang)
                opt_confs.append(oconf)
                if tagm in ('G', 'Y'):
                    hl_tag = tagm
            langs = [lg for _, lg, _ in stem_parts] + \
                [lg for _, lg, _ in diag_parts] + opt_langs
            lang = 'hin' if langs.count('hin') > langs.count('eng') else 'eng'
            confs = [cf for _, _, cf in stem_parts] + \
                [cf for _, _, cf in diag_parts] + opt_confs
            min_conf = round(min(confs), 1) if confs else 0.0
            rec = {
                'set': set_no,
                'qno': q['qno'],
                'file': s['file'],
                'lang': lang,
                'min_conf': min_conf,
                'stem': stem_text,
                'options': options,
                'answer_index': ans_idx,
                'answer_letter': LETTERS[ans_idx - 1] if ans_idx else None,
                'answer_text': options[ans_idx - 1] if ans_idx else None,
                'highlight_tag': hl_tag,
                'n_stem_imgs': len(stem_objs),
                'n_diagrams': len(diagram_objs),
                'stem_objs': stem_objs,
                'option_objs': opt_objs,
                'diagram_objs': diagram_objs,
            }
            set_records.append(rec)
        with open(setpath, 'w') as f:
            json.dump(set_records, f, ensure_ascii=False, indent=1)
        sys.stderr.write(f'\rOCR set {set_no}/{total} written ({len(set_records)} Qs)')
        sys.stderr.flush()
    sys.stderr.write('\n')

    # merge all per-set files into one cache
    records = []
    for si in range(total):
        setpath = os.path.join(SETDIR, f'set_{si+1:02d}.json')
        if os.path.exists(setpath):
            with open(setpath) as f:
                records.extend(json.load(f))
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, 'w') as f:
        json.dump(records, f, ensure_ascii=False, indent=1)
    print(f'wrote {len(records)} question records to {OUT}')

    # quick integrity report
    no_ans = [r for r in records if not r['answer_index']]
    empty_stem = [r for r in records if not r['stem']]
    empty_opt = [r for r in records if any(not o for o in r['options'])]
    print(f'sets={total} questions={len(records)}')
    print(f'no answer detected: {len(no_ans)}')
    print(f'empty stem OCR: {len(empty_stem)}')
    print(f'questions with >=1 empty option OCR: {len(empty_opt)}')


if __name__ == '__main__':
    main()
