"""Render the QA Test Completion Report from the tokenized template (PRD §9.2, Appendix C)."""

from pathlib import Path

from docxtpl import DocxTemplate

from app.services.docengine.models import ReportData

CHECKED = "☒"  # ☒
UNCHECKED = "☐"  # ☐


def _yes_no(flag: bool) -> tuple[str, str]:
    return (CHECKED, UNCHECKED) if flag else (UNCHECKED, CHECKED)


def _build_context(data: ReportData) -> dict[str, object]:
    cert_yes_box, cert_no_box = _yes_no(data.certified)

    features = []
    for f in data.features:
        impl_yes, impl_no = _yes_no(f.implemented)
        func_yes, func_no = _yes_no(f.functional)
        features.append(
            {
                "name": f.name,
                "description": f.description,
                "impl_yes": impl_yes,
                "impl_no": impl_no,
                "func_yes": func_yes,
                "func_no": func_no,
            }
        )

    if data.exceptions:
        exceptions = [
            {
                "id": e.case_id,
                "status_type": e.status_type,
                "description": e.description,
                "severity": e.severity,
                "risk": e.risk,
            }
            for e in data.exceptions
        ]
    else:
        exceptions = [
            {
                "id": "N/A",
                "status_type": "N/A",
                "description": "N/A",
                "severity": "N/A",
                "risk": "N/A",
            }
        ]

    ra = data.result_analysis
    return {
        "product_name": data.product_name,
        "pr_links": data.pr_links,
        "version_numbers": data.version_numbers,
        "test_url": data.test_url,
        "workitem_url": data.workitem_url,
        "jira_link": data.jira_link,
        "general_description": data.general_description,
        "cert_yes_box": cert_yes_box,
        "cert_no_box": cert_no_box,
        "features": features,
        "exit_criteria": data.exit_criteria,
        "ra": {
            "test_cycles": ra.test_cycles,
            "total": ra.total,
            "passed": ra.passed,
            "failed": ra.failed,
            "unexecuted": ra.unexecuted,
            "suspended": ra.suspended,
            "modification": ra.modification,
        },
        "automation_ratio": data.automation_ratio,
        "bugs": {
            "raised": data.bugs.raised,
            "fixed_retested": data.bugs.fixed_retested,
            "open": data.bugs.open,
        },
        "exceptions": exceptions,
        "comments": data.comments or [""],
        "approvals": [
            {
                "action": a.action,
                "name": a.name,
                "staff_id": a.staff_id,
                "signature": a.signature,
                "date": a.date,
            }
            for a in data.approvals
        ],
        "classification_label": data.classification_label,
    }


def write_report_docx(template_path: Path, data: ReportData, output_path: Path) -> None:
    tpl = DocxTemplate(str(template_path))
    tpl.render(_build_context(data))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    tpl.save(str(output_path))
