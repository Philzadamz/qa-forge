from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[4]
XLSX_TEMPLATE = REPO_ROOT / "templates" / "source" / "QA_Test_Cases_Template.xlsx"
DOCX_TEMPLATE = REPO_ROOT / "templates" / "source" / "QA_Test_Report_Template.docx"

needs_xlsx_template = pytest.mark.skipif(
    not XLSX_TEMPLATE.exists(), reason="real team xlsx template not present on this machine"
)
needs_docx_template = pytest.mark.skipif(
    not DOCX_TEMPLATE.exists(), reason="real team docx template not present on this machine"
)
