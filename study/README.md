# SSC GD — General Knowledge & General Awareness (PART-B)

Self-contained HTML study resource built from the two candidate-response-sheet PDFs
(`page1-223.pdf`, `page224-445.pdf`) using OCR + authored solutions.

## What's here
- **`index.html`** — landing page with a **by-topic** grid and a **by-set** grid, plus
  a running count of how many questions have detailed solutions so far.
- **`sets/set_01.html … set_59.html`** — per-set view. Each set has its **20 questions**
  (Q.No 21–40) showing:
  - the **OCR'd question text** (English or Hindi) and the four options as text,
  - the **original question/diagram image** from the paper (embedded),
  - the **correct answer highlighted in green**, and
  - a **detailed solution**: why the correct option is right, **why each of the other
    three options is wrong**, and a relevant extra fact.
- **`topics/<topic>.html`** — the same questions grouped **topic-wise** (History,
  Geography, Polity & Constitution, Economy, Science & Technology, Sports, Art & Culture,
  Books & Authors, Awards & Honours, Schemes & Government, Current Affairs, Static GK).

A plain-text version of all solutions is generated at `../solutions.txt`.

## Coverage
- 59 sets × 20 questions = **1,180 questions**, all **PART-B: GK & General Awareness**.
- Language split: **396 English, 784 Hindi** questions.
- A single correct answer was detected for **every** question from the green/yellow
  answer-key highlight in the source PDFs (green = selected-correct, yellow = correct
  option). The detected answer is **cross-checked** against the answer determined from
  general knowledge while authoring solutions; mismatches are logged in
  `../data/cross_check.txt` (currently **0**).

## Progress (delivered in batches of 5 sets)
Detailed solutions are added incrementally. Sets without authored solutions still show
the OCR'd text, options and the correct answer, with a "solution coming in a later
batch" note. See the by-set grid on `index.html` for current status.

## How to view
Download the `study/` folder and open `index.html` in any browser. The files are fully
self-contained (images embedded), so no internet is required.

## Reproducing
Scripts are in `../tools/` (run from the repo's parent dir, i.e. `cd /path/to/Gd/..`):
- `tools/ocr_extract.py` — OCR every question (English + Hindi), pick the higher-confidence
  result, and cache to `data/ocr_cache.json`. Requires `pytesseract`, `Pillow`, and a
  `tesseract` binary with `eng` + `hin` language data.
- `tools/topics.py` — keyword-based GK topic classifier.
- `tools/generate_solutions.py` — builds the per-set + topic HTML, `index.html`, the
  `solutions.txt` file, and the answer cross-check report. Authored solutions live in
  `../solutions/set_NN.json`.
