"""Turn the team's raw QA_Test_Report_Template.docx into a docxtpl-tagged working copy
(ADM-TM-2, PRD Appendix C).

This is a one-shot, structural transform — run once (via `app.cli tokenize-report-template`)
to produce `templates/tokenized/QA_Test_Report_Template.docx`, which is then safe to commit
(unlike the raw source template: it carries no bank data once tokenized) and is what
`docx_writer.py` actually renders against.

docxtpl's `{%tr %}`/`{%p %}` row- and paragraph-loop tags each collapse their *entire*
enclosing row/paragraph down to the bare Jinja tag (see docxtpl's `patch_xml`, which matches
`<w:tr>...{%tr ...%}...</w:tr>` non-greedily and replaces the whole thing with just the tag
text). So `{%tr for %}` and `{%tr endfor %}` each need their own dedicated row — putting both
in the same row as the data cells throws the data away. Same for `{%p %}` and paragraphs.
Every loop here is built as three siblings: a for-tag row/paragraph, the template content
row/paragraph, and an endfor-tag row/paragraph.

Three things in the raw template aren't plain text and need surgery rather than a text swap:
- The "Is this build certified for deployment? Yes ☐ No ☐" line is a single flattened
  *image* (screenshot-style), not text. We delete the image and replace it with a real
  Jinja-tagged text run, rendering ☒/☐ per PRD §9.2's "swap to real checkbox text" option.
- The BRD feature table's Implemented?/Functional? checkboxes are small inline images next
  to literal "Yes"/"No" text. Since the whole templated row is rebuilt with fresh cell text
  (PRD Appendix C), those images are simply dropped along with the rest of the sample row.
- The Comments/Observation body text (PRD §3.2's stray "s" included) turns out to be real
  text too, but inside a DrawingML text box anchored to that paragraph rather than a plain
  run — invisible to `paragraph.text`. Clearing that paragraph's runs (which is what turning
  it into the `comments` loop does anyway) removes the text box and the stray "s" together.
- The footer's classification-label text box contains "aPublic" (a stray leading "a", same
  kind of typo) and lives inside its own DrawingML text box — needs a raw XML text-node edit
  since it's in the footer, not the body.

Three of the four Approvals rows also carry real signature images from whoever filled in
this sample — personal data specific to one filled report, dropped along with those rows.
"""

import copy
from pathlib import Path
from typing import cast

import docx
from docx.document import Document
from docx.oxml.ns import qn
from docx.table import Table, _Cell, _Row
from docx.text.paragraph import Paragraph

CERTIFIED_TEXT = (
    "Is this build certified for deployment?\tYes {{ cert_yes_box }}\tNo {{ cert_no_box }}"
)


class DocxTokenizeError(RuntimeError):
    pass


def _set_paragraph_text(paragraph: Paragraph, text: str) -> None:
    for run in list(paragraph.runs):
        run._element.getparent().remove(run._element)
    paragraph.add_run(text)


def _clear_cell_to_single_paragraph(cell: _Cell) -> Paragraph:
    """Drop every paragraph but the first, returning what's left (with its runs intact).

    Some cells in the raw template hold one paragraph per line (e.g. one PR link per
    paragraph) — touching only `cell.paragraphs[0]` leaves the rest of the sample data
    behind, so anything that's about to become simple text or a `{%p %}` loop needs this.
    """
    for extra in cell.paragraphs[1:]:
        extra._element.getparent().remove(extra._element)
    return cast(Paragraph, cell.paragraphs[0])


def _set_cell_text(cell: _Cell, text: str) -> None:
    """Replace a cell's entire content (text + any images) with a single run of `text`."""
    _set_paragraph_text(_clear_cell_to_single_paragraph(cell), text)


def _delete_row(table: Table, index: int) -> None:
    row = table.rows[index]
    row._tr.getparent().remove(row._tr)


def _wrap_row_as_loop(table: Table, row_index: int, for_tag: str, endfor_tag: str) -> None:
    """Clone the template row into a for-tag row before it and an endfor-tag row after it.

    docxtpl collapses each tagged row entirely, so the clones only need to carry the tag
    text in one cell — the rest of their (cloned, otherwise-irrelevant) content is cleared.
    """
    template_tr = table.rows[row_index]._tr
    for_tr = copy.deepcopy(template_tr)
    endfor_tr = copy.deepcopy(template_tr)
    for tr_elem, tag in ((for_tr, for_tag), (endfor_tr, endfor_tag)):
        row = _Row(tr_elem, table)
        for i, cell in enumerate(row.cells):
            _set_cell_text(cell, tag if i == 0 else "")
    template_tr.addprevious(for_tr)
    template_tr.addnext(endfor_tr)


def _wrap_paragraph_as_loop(paragraph: Paragraph, for_tag: str, endfor_tag: str) -> None:
    """Same idea as `_wrap_row_as_loop` but for a `{%p %}` paragraph loop."""
    p_elem = paragraph._p
    for_p = copy.deepcopy(p_elem)
    endfor_p = copy.deepcopy(p_elem)
    _set_paragraph_text(Paragraph(for_p, paragraph._parent), for_tag)
    _set_paragraph_text(Paragraph(endfor_p, paragraph._parent), endfor_tag)
    p_elem.addprevious(for_p)
    p_elem.addnext(endfor_p)


def _find_certificate_paragraph(doc: Document) -> Paragraph:
    """The certificate line is the one body paragraph anchoring a 6799580x238125-EMU image."""
    for paragraph in doc.paragraphs:
        if 'cx="6799580" cy="238125"' in paragraph._p.xml:
            return paragraph
    raise DocxTokenizeError(
        "Could not find the Certificate Summary image paragraph — has the template changed?"
    )


def _replace_certificate_image_with_text(doc: Document) -> None:
    paragraph = _find_certificate_paragraph(doc)
    _set_paragraph_text(paragraph, CERTIFIED_TEXT)


def _fix_footer_classification_label(doc: Document) -> None:
    footer = doc.sections[0].footer
    found = False
    for t in footer._element.iter(qn("w:t")):
        if t.text and t.text.strip().lower() == "apublic":
            t.text = "{{ classification_label }}"
            found = True
    if not found:
        raise DocxTokenizeError(
            "Could not find the footer classification label text — has the template changed?"
        )


def _tokenize_project_info_table(table: Table) -> None:
    rows = table.rows
    _set_cell_text(rows[0].cells[1], "{{ product_name }}")

    pr_links_p = _clear_cell_to_single_paragraph(rows[1].cells[1])
    _set_paragraph_text(pr_links_p, "{{ l }}")
    _wrap_paragraph_as_loop(pr_links_p, "{%p for l in pr_links %}", "{%p endfor %}")

    version_p = _clear_cell_to_single_paragraph(rows[2].cells[1])
    _set_paragraph_text(version_p, "{{ v }}")
    _wrap_paragraph_as_loop(version_p, "{%p for v in version_numbers %}", "{%p endfor %}")

    _set_cell_text(rows[3].cells[1], "{{ test_url }}")
    _set_cell_text(rows[4].cells[1], "{{ workitem_url }}")
    _set_cell_text(rows[5].cells[1], "{{ jira_link }}")
    _set_cell_text(rows[6].cells[1], "{{ general_description }}")


def _tokenize_feature_table(table: Table) -> None:
    if len(table.rows) < 2:
        raise DocxTokenizeError("Feature status table has fewer than 2 rows — template changed?")
    row = table.rows[0]
    _set_cell_text(row.cells[0], "{{ loop.index }}.")
    _set_cell_text(row.cells[1], "{{ f.name }}")
    _set_cell_text(row.cells[2], "{{ f.description }}")
    _set_cell_text(row.cells[3], "{{ f.impl_yes }} Yes {{ f.impl_no }} No")
    _set_cell_text(row.cells[4], "{{ f.func_yes }} Yes {{ f.func_no }} No")
    for i in range(len(table.rows) - 1, 0, -1):
        _delete_row(table, i)
    _wrap_row_as_loop(table, 0, "{%tr for f in features %}", "{%tr endfor %}")


def _tokenize_exit_criteria_table(table: Table) -> None:
    row = table.rows[1]
    _set_cell_text(row.cells[0], "{{ loop.index }}.")
    _set_cell_text(row.cells[1], "{{ c }}")
    for i in range(len(table.rows) - 1, 1, -1):
        _delete_row(table, i)
    _wrap_row_as_loop(table, 1, "{%tr for c in exit_criteria %}", "{%tr endfor %}")


def _tokenize_result_status_table(table: Table) -> None:
    rows = table.rows
    _set_cell_text(rows[1].cells[1], "{{ ra.test_cycles }}")
    _set_cell_text(rows[2].cells[1], "{{ ra.total }}")
    _set_cell_text(rows[3].cells[1], "{{ ra.passed }}")
    _set_cell_text(rows[4].cells[1], "{{ ra.failed }}")
    _set_cell_text(rows[5].cells[1], "{{ ra.unexecuted }}")
    _set_cell_text(rows[6].cells[1], "{{ ra.suspended }}")
    _set_cell_text(rows[7].cells[1], "{{ ra.modification }}")


def _tokenize_ratio_and_bugs_table(table: Table) -> None:
    rows = table.rows
    _set_cell_text(rows[0].cells[1], "{{ automation_ratio }}")
    _set_cell_text(rows[2].cells[1], "{{ bugs.raised }}")
    _set_cell_text(rows[3].cells[1], "{{ bugs.fixed_retested }}")
    _set_cell_text(rows[4].cells[1], "{{ bugs.open }}")


def _tokenize_exceptions_table(table: Table) -> None:
    row = table.rows[1]
    _set_cell_text(row.cells[0], "{{ e.id }}")
    _set_cell_text(row.cells[1], "{{ e.status_type }}")
    _set_cell_text(row.cells[2], "{{ e.description }}")
    _set_cell_text(row.cells[3], "{{ e.severity }}")
    _set_cell_text(row.cells[4], "{{ e.risk }}")
    _wrap_row_as_loop(table, 1, "{%tr for e in exceptions %}", "{%tr endfor %}")


def _tokenize_approvals_table(table: Table) -> None:
    row = table.rows[1]
    _set_cell_text(row.cells[0], "{{ a.action }}")
    _set_cell_text(row.cells[1], "{{ a.name }}")
    _set_cell_text(row.cells[2], "{{ a.staff_id }}")
    _set_cell_text(row.cells[3], "{{ a.signature }}")
    _set_cell_text(row.cells[4], "{{ a.date }}")
    for i in range(len(table.rows) - 1, 1, -1):
        _delete_row(table, i)
    _wrap_row_as_loop(table, 1, "{%tr for a in approvals %}", "{%tr endfor %}")


def _tokenize_comments(doc: Document) -> None:
    for paragraph in doc.paragraphs:
        if paragraph.text.strip() == "Comments/Observation":
            next_p = paragraph._p.getnext()
            if next_p is not None and next_p.tag == qn("w:p"):
                target = Paragraph(next_p, paragraph._parent)
                _set_paragraph_text(target, "{{ p }}")
                _wrap_paragraph_as_loop(target, "{%p for p in comments %}", "{%p endfor %}")
                return
    raise DocxTokenizeError("Could not find the Comments/Observation section — template changed?")


def tokenize_report_template(source_path: Path, output_path: Path) -> None:
    doc = docx.Document(str(source_path))

    tables = doc.tables
    if len(tables) != 8:
        raise DocxTokenizeError(f"Expected 8 tables in the template, found {len(tables)}")

    _tokenize_project_info_table(tables[0])
    _replace_certificate_image_with_text(doc)
    _tokenize_feature_table(tables[2])
    _tokenize_exit_criteria_table(tables[3])
    _tokenize_result_status_table(tables[4])
    _tokenize_ratio_and_bugs_table(tables[5])
    _tokenize_exceptions_table(tables[6])
    _tokenize_approvals_table(tables[7])
    _tokenize_comments(doc)
    _fix_footer_classification_label(doc)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    doc.save(str(output_path))
