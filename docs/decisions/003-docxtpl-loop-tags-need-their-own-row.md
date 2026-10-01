# 003 — docxtpl `{%tr %}`/`{%p %}` tags need their own dedicated row/paragraph

**Status:** accepted · **Date:** 2026-10-01

## Context
Tokenizing the report template's repeating tables (features, exit criteria, exceptions,
approvals) and multi-line cells (PR links, version numbers, comments) needs docxtpl's
row-loop (`{%tr for %}`/`{%tr endfor %}`) and paragraph-loop (`{%p for %}`/`{%p endfor %}`)
tags. The natural-looking layout — put the `for` tag at the start of the template row/cell
and the `endfor` tag at the end of the same row — renders with `jinja2.exceptions.
TemplateSyntaxError: Encountered unknown tag 'endfor'`.

Reading docxtpl's `patch_xml` (`docxtpl/template.py`) explains why: for `y` in `tr`/`p` (and
`tc`/`r`), it matches `<w:{y}>...{%{y} ...%}...</w:{y}>` **non-greedily** and replaces the
*entire* row/paragraph element with just the tag text, discarding everything else in that
row/paragraph — including a second tag in the same row/paragraph. Putting both `for` and
`endfor` in the same row means the `for` match consumes through to `</w:tr>`, taking the
`endfor` tag (and all the real data) down with it.

## Decision
Every `{%tr %}`/`{%p %}` loop is built as three siblings: a row/paragraph holding only the
`for` tag, the template content row/paragraph (plain `{{ }}` tags, no `tr`/`p` prefix), and a
row/paragraph holding only the `endfor` tag. `docx_tokenizer.py`'s `_wrap_row_as_loop` and
`_wrap_paragraph_as_loop` clone the template row/paragraph to get matching structure
(column count, etc.) for the two marker rows, then clear them down to just the tag.

Verified with an isolated minimal docxtpl repro (a 4-row table, `for`/data/`endfor` as three
rows) before touching the real tokenizer — cheaper to confirm the mechanism on a throwaway
file than to debug it through the full template's complexity.

## Consequences
- `docx_tokenizer.py` inserts two extra rows/paragraphs per loop construct; they render into
  nothing once the tags collapse, so the visible output is exactly the repeated content —
  but anyone reading `templates/tokenized/QA_Test_Report_Template.docx` in Word will see
  these marker rows/paragraphs in the *editable* source (they only vanish after a docxtpl
  render), which could confuse a future manual edit unless this doc (or the tokenizer's
  module docstring, which also explains this) is read first.
- Any future hand-edit of the tokenized template that adds a new loop must follow the same
  three-sibling pattern — a `for`/`endfor` pair sharing one row/paragraph with real content
  will silently destroy that content the same way.
