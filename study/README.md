# SSC GD — General Knowledge & General Awareness (PART-B)

Self-contained HTML study resource built from the two candidate-response-sheet PDFs
(`page1-223.pdf`, `page224-445.pdf`).

## What's here
- **`index.html`** — links to all 59 sets.
- **`set_01.html` … `set_59.html`** — each set has its **20 questions** (Q.No 21–40).

Every question shows the **original question and option images** taken directly from the
paper (no OCR), and the **correct answer is highlighted in green** — derived from the
green/yellow answer-key highlight in the source PDFs.

## Coverage
- 59 sets × 20 questions = **1,180 questions**
- All belong to **PART-B: General Knowledge & General Awareness**
- A single correct answer was detected for **every** question (green = selected-correct, yellow = correct option).

## How to view
Download the `study/` folder and open `index.html` in any browser. The files are fully
self-contained (images are embedded), so no internet is required.

## Not included (needs OCR)
Typed-out question text, topic-wise grouping, and written solutions require OCR, which
needs an internet-enabled environment to install. The images here preserve 100% of the
original content in the meantime.

## Reproducing
The extraction/generation scripts are in `../tools/`. Run `python3 generate_html.py`
from the repo root (stdlib only — no external dependencies).
