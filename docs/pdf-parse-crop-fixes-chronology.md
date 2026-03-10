# PDF Parse/Crop Fix Chronology

## Scope

This document records the sequence of fixes applied while resolving real-world PDF parsing and cropping failures found across multiple subjects. The goal was not to make the parser universally perfect, but to close the issue patterns that repeatedly appeared in actual usage and to leave behind only the durable logic and minimal regression coverage.

## 2026-03-09: Baseline parse-lab review

Observed failure groups from real PDFs:

- Alpha / subitem formatting collapsed into one line
  - examples: `a)`, `b)`, `가.`, `나.`
- Label-only answer color detection failed
  - the option number was blue, but the body text was black
- Decimal prefixes were misread as option labels
  - example: `4.4` being parsed as option `4)`
- Late-label / long-option boundaries failed
  - the start of the next option was absorbed into stem or previous option
- Mapping / compound-style questions were treated as ordinary multiple choice
  - `[보기]`, `A:`, `B:`, `가.`, `나.` style layouts

Fixes introduced in `app/services/pdf_lab_parser.py`:

- subitem-aware formatting preservation
- label-only key detection propagation
- decimal guard for option matching
- continuation repair heuristics for long options
- mapping choice-bank promotion and answer extraction

Regression coverage was added in `tests/test_pdf_lab_parser.py`.

## 2026-03-09: Boxed panel and banner structure preservation

Additional failures found in `23년 생리학 3차`:

- boxed lab / result panels were flattened into stem text
- question-start banner boxes were merged with the next sentence
- panel boundaries were lost after text row extraction

Fixes introduced in `app/services/pdf_lab_parser.py`:

- vector-line-based panel detection
- event tagging with:
  - `inside_panel`
  - `panel_id`
  - `panel_kind`
  - `panel_bbox`
- block-aware content model:
  - `stem_text`
  - `panel_text`
  - `banner_text`
  - `stem_image`
  - `panel_image`
- final rendering changed from flat line join to block rendering with paragraph separation

Representative regression coverage:

- Q33 boxed panel
- Q36 mid-stem lab panel
- Q73 question-start banner

## 2026-03-10: Panel-aware crop union

Parser-side structure preservation fixed text semantics, but crop generation still used only content-derived bounds inside the detected question segment. This caused a separate class of failures:

- panel text was present, but the panel border / outer box was not fully included in the crop
- banner boxes could be clipped because text-only content bounds were narrower than the actual visual panel

Fixes introduced in `app/routes/crop.py`:

- added PyMuPDF drawing-based panel detection mirroring parser logic
- added panel-aware union during crop bbox selection
- crop bbox now unions:
  - content text bbox
  - image bbox
  - overlapping detected panel bbox
- added a center-inside fallback so small text inside a large panel still expands the crop to panel bounds

Regression coverage added in `tests/test_pdf_crop_panel.py`:

- synthetic panel union test
- representative PDF crop guards for Q33 / Q36 / Q73

## 2026-03-10: Legacy backend rollout

The old HTML management upload path was not using the same parser entrypoint as the newer API path.

Changes:

- `app/services/pdf_parser_factory.py`
  - `legacy` mode now resolves to `app/services/pdf_lab_parser.parse_pdf_to_lab_questions`
- `app/routes/manage.py`
  - legacy upload flow now uses `pdf_parser_factory.parse_pdf(...)`

Result:

- legacy backend and newer API-backed upload flow now share the same legacy parser behavior
- crop generation remains shared through `app.services.pdf_cropper` and `app.routes.crop`

## Final status

As of this cleanup point:

- the repeatedly observed real-world parse failures have been addressed
- boxed panel and banner structure are preserved
- crop output includes panel regions for the representative cases that were actually failing
- remaining future work should be case-driven only when a new PDF pattern appears

## Cleanup policy

The large intermediate experiment bundles and review-session artifacts used during investigation are intentionally removed from the repository working set. The durable assets that remain are:

- parser/crop code changes
- regression tests
- this chronology document
