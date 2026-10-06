"""Report drafting and rendering (PRD §7.5, §8.3, §10)."""

import logging
import tempfile
import uuid
from pathlib import Path
from typing import Any, cast

from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, UploadFile, status
from fastapi.responses import Response, StreamingResponse
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.core import usage
from app.core.audit import record as audit_record
from app.core.config import get_settings
from app.core.enums import TemplateKind, TemplateStatus
from app.core.rbac import require_project_access, require_user
from app.core.report_defaults import DEFAULT_APPROVAL_ROLES, DEFAULT_EXIT_CRITERIA
from app.core.uploads import sniff_image
from app.db.session import get_db
from app.models.bug import Bug
from app.models.project import Project
from app.models.report import Report
from app.models.report_defaults import ReportDefaults
from app.models.template import Template
from app.models.test_case import TestCase
from app.models.test_suite import TestSuite
from app.models.usage_record import UsageRecord
from app.models.user import User
from app.schemas.reports import ReportOut, ReportRenderData, ReportUpdate
from app.services.ai.client import LLMError, build_llm_client
from app.services.ai.draft_report import PROMPT_VERSION as DRAFT_PROMPT_VERSION
from app.services.ai.draft_report import draft_feature_descriptions
from app.services.docengine.docx_writer import write_report_docx
from app.services.docengine.models import (
    ApprovalRow,
    BugsSummary,
    ExceptionRow,
    FeatureRow,
    ReportData,
    ResultAnalysis,
)
from app.services.reports.builder import (
    compute_automation_ratio,
    compute_bug_counts,
    compute_result_counts,
    feature_is_functional,
    functional_features,
    suggest_certified,
)
from app.services.storage import build_storage

router = APIRouter(tags=["reports"])
logger = logging.getLogger(__name__)


def _get_suite_or_404(db: Session, suite_id: uuid.UUID, user: User) -> tuple[TestSuite, Project]:
    suite = db.get(TestSuite, suite_id)
    if suite is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Suite not found")
    project = db.get(Project, suite.project_id)
    if project is None or project.deleted_at is not None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Project not found")
    require_project_access(project, user)
    return suite, project


def _get_report_or_404(
    db: Session, report_id: uuid.UUID, user: User
) -> tuple[Report, TestSuite, Project]:
    report = db.get(Report, report_id)
    if report is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Report not found")
    suite, project = _get_suite_or_404(db, report.suite_id, user)
    return report, suite, project


@router.get("/suites/{suite_id}/reports", response_model=list[ReportOut])
def list_reports(
    suite_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(require_user)
) -> list[Report]:
    _get_suite_or_404(db, suite_id, user)
    return list(
        db.query(Report).filter(Report.suite_id == suite_id).order_by(Report.version.desc()).all()
    )


@router.post(
    "/suites/{suite_id}/reports/draft",
    response_model=ReportOut,
    status_code=status.HTTP_201_CREATED,
)
def draft_suite_report(
    suite_id: uuid.UUID,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_user),
) -> Report:
    suite, project = _get_suite_or_404(db, suite_id, user)
    cases = db.query(TestCase).filter(TestCase.suite_id == suite.id).all()
    bugs = db.query(Bug).filter(Bug.suite_id == suite.id).all()

    result = compute_result_counts(cases, suite.test_cycle)
    bug_counts = compute_bug_counts(bugs)
    ratio = compute_automation_ratio(cases)
    certified = suggest_certified(result, bug_counts)
    features = functional_features(cases)

    defaults_row = db.query(ReportDefaults).order_by(ReportDefaults.created_at).first()
    exit_criteria = (
        defaults_row.exit_criteria
        if defaults_row and defaults_row.exit_criteria
        else DEFAULT_EXIT_CRITERIA
    )
    approval_roles = (
        defaults_row.approval_roles
        if defaults_row and defaults_row.approval_roles
        else DEFAULT_APPROVAL_ROLES
    )
    classification_label = defaults_row.classification_label if defaults_row else "Public"

    feature_descriptions: dict[str, str] = {}
    try:
        settings = get_settings()
        client = build_llm_client(settings)
        with usage.track() as sink:
            draft = draft_feature_descriptions(
                client,
                product_name=project.name,
                features=features,
                model=settings.ai_model_drafting,
            )
        if sink.events:
            db.add(
                UsageRecord(
                    actor_id=user.id,
                    feature="report_draft",
                    entity_id=str(suite_id),
                    model=settings.ai_model_drafting,
                    prompt_tokens=sink.prompt_tokens,
                    completion_tokens=sink.completion_tokens,
                )
            )
        feature_descriptions = {f.name: f.description for f in draft.feature_descriptions}
    except (LLMError, ValidationError) as exc:
        logger.warning("Report draft AI call failed for suite %s: %s", suite_id, exc)

    feature_rows = [
        {
            "name": name,
            "description": feature_descriptions.get(
                name, f"To confirm that {name} works as expected."
            ),
            "implemented": True,
            "functional": feature_is_functional(cases, name),
        }
        for name in features
    ]

    exception_rows = [
        {
            "case_id": "N/A",
            "status_type": "N/A",
            "description": "N/A",
            "severity": "N/A",
            "risk": "N/A",
        }
    ]

    approvals = [
        {
            "action": r.get("action", ""),
            "name": "",
            "staff_id": "",
            "signature_key": None,
            "date": "",
        }
        for r in approval_roles
    ]

    fields_json: dict[str, object] = {
        "product_name": project.name,
        "pr_links": [],
        "version_numbers": [],
        "test_url": str(suite.header_json.get("endpoint_url") or ""),
        "workitem_url": "",
        "jira_link": "",
        "general_description": (
            f"Outlines the features of testing {project.name} sent to the Quality Assurance "
            "team for testing."
        ),
        "certified": certified,
        "features": feature_rows,
        "exit_criteria": exit_criteria,
        "result_analysis": {
            "test_cycles": result.test_cycles,
            "total": result.total,
            "passed": result.passed,
            "failed": result.failed,
            "unexecuted": result.unexecuted,
            "suspended": result.suspended,
            "modification": result.modification,
        },
        "automation_ratio": ratio,
        "bugs": {
            "raised": bug_counts.raised,
            "fixed_retested": bug_counts.fixed_retested,
            "open": bug_counts.open,
        },
        "exceptions": exception_rows,
        "comments": [],
        "approvals": approvals,
        "classification_label": classification_label,
        "ra_overridden": False,
        "ra_override_reason": None,
    }

    last_version = (
        db.query(Report.version)
        .filter(Report.suite_id == suite.id)
        .order_by(Report.version.desc())
        .first()
    )
    report = Report(
        suite_id=suite.id,
        fields_json=fields_json,
        version=(last_version[0] + 1) if last_version else 1,
        generated_by=user.id,
    )
    db.add(report)
    db.flush()
    audit_record(
        db,
        actor_id=user.id,
        action="draft",
        entity="report",
        entity_id=str(report.id),
        diff={"prompt_version": DRAFT_PROMPT_VERSION},
        request=request,
    )
    db.commit()
    db.refresh(report)
    return report


@router.get("/reports/{report_id}", response_model=ReportOut)
def get_report(
    report_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(require_user)
) -> Report:
    report, _, _ = _get_report_or_404(db, report_id, user)
    return report


@router.put("/reports/{report_id}", response_model=ReportOut)
def update_report(
    report_id: uuid.UUID,
    payload: ReportUpdate,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_user),
) -> Report:
    report, _, _ = _get_report_or_404(db, report_id, user)
    was_overridden = bool(report.fields_json.get("ra_overridden"))
    now_overridden = bool(payload.fields_json.get("ra_overridden"))
    if now_overridden and not was_overridden and not payload.fields_json.get("ra_override_reason"):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "ra_override_reason is required to override Result Analysis",
        )

    report.fields_json = payload.fields_json
    audit_record(
        db,
        actor_id=user.id,
        action="update",
        entity="report",
        entity_id=str(report.id),
        diff={
            "ra_overridden": now_overridden,
            "ra_override_reason": payload.fields_json.get("ra_override_reason"),
        }
        if now_overridden
        else {},
        request=request,
    )
    db.commit()
    db.refresh(report)
    return report


SIGNATURE_MAX_BYTES = 2 * 1024 * 1024


def _approval_or_404(report: Report, index: int) -> dict[str, Any]:
    approvals = report.fields_json.get("approvals")
    if not isinstance(approvals, list) or not 0 <= index < len(approvals):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Approval row not found")
    row = approvals[index]
    if not isinstance(row, dict):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Approval row not found")
    return cast(dict[str, Any], row)


def _set_signature_key(report: Report, index: int, key: str | None) -> None:
    approvals = [dict(row) for row in cast(list[dict[str, Any]], report.fields_json["approvals"])]
    approvals[index]["signature_key"] = key
    report.fields_json = {**report.fields_json, "approvals": approvals}


@router.post("/reports/{report_id}/approvals/{index}/signature", response_model=ReportOut)
async def upload_signature(
    report_id: uuid.UUID,
    index: int,
    request: Request,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(require_user),
) -> Report:
    report, _, _ = _get_report_or_404(db, report_id, user)
    row = _approval_or_404(report, index)
    raw = await file.read()
    if len(raw) > SIGNATURE_MAX_BYTES:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Signature image is too large (max 2 MB)")
    sniffed = sniff_image(raw)
    if sniffed is None:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "Unsupported signature file. Upload a PNG, JPEG, GIF, or WebP image.",
        )
    _, extension = sniffed

    storage = build_storage(get_settings())
    previous = row.get("signature_key")
    key = f"signatures/{report.id}/{index}-{uuid.uuid4().hex}.{extension}"
    storage.put(key, raw)
    _set_signature_key(report, index, key)
    if isinstance(previous, str):
        storage.delete(previous)
    audit_record(
        db,
        actor_id=user.id,
        action="upload_signature",
        entity="report",
        entity_id=str(report.id),
        diff={"approval_index": index},
        request=request,
    )
    db.commit()
    db.refresh(report)
    return report


@router.get("/reports/{report_id}/approvals/{index}/signature")
def get_signature(
    report_id: uuid.UUID,
    index: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_user),
) -> Response:
    report, _, _ = _get_report_or_404(db, report_id, user)
    row = _approval_or_404(report, index)
    key = row.get("signature_key")
    if not isinstance(key, str):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No signature for this row")
    raw = build_storage(get_settings()).get(key)
    sniffed = sniff_image(raw)
    content_type = sniffed[0] if sniffed else "application/octet-stream"
    return Response(content=raw, media_type=content_type)


@router.delete("/reports/{report_id}/approvals/{index}/signature", response_model=ReportOut)
def remove_signature(
    report_id: uuid.UUID,
    index: int,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_user),
) -> Report:
    report, _, _ = _get_report_or_404(db, report_id, user)
    row = _approval_or_404(report, index)
    previous = row.get("signature_key")
    _set_signature_key(report, index, None)
    if isinstance(previous, str):
        build_storage(get_settings()).delete(previous)
    audit_record(
        db,
        actor_id=user.id,
        action="remove_signature",
        entity="report",
        entity_id=str(report.id),
        diff={"approval_index": index},
        request=request,
    )
    db.commit()
    db.refresh(report)
    return report


@router.post("/reports/{report_id}/render")
def render_report(
    report_id: uuid.UUID,
    format: str = Query(default="docx", pattern="^docx$"),
    db: Session = Depends(get_db),
    user: User = Depends(require_user),
) -> StreamingResponse:
    report, suite, project = _get_report_or_404(db, report_id, user)

    try:
        data = ReportRenderData.model_validate(report.fields_json)
    except ValidationError as exc:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY, f"Report is incomplete: {exc}"
        ) from exc

    if not data.ra_overridden:
        cases = db.query(TestCase).filter(TestCase.suite_id == suite.id).all()
        fresh = compute_result_counts(cases, suite.test_cycle)
        stored = data.result_analysis
        if (
            fresh.total != stored.total
            or fresh.passed != stored.passed
            or fresh.failed != stored.failed
            or fresh.unexecuted != stored.unexecuted
            or fresh.suspended != stored.suspended
            or fresh.modification != stored.modification
        ):
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                "The suite's results have changed since this report was drafted "
                f"(fresh: total={fresh.total} passed={fresh.passed} failed={fresh.failed} "
                f"unexecuted={fresh.unexecuted} suspended={fresh.suspended} "
                f"modification={fresh.modification}). Re-draft the report, or set "
                "ra_overridden with a reason to use the numbers as saved.",
            )

    storage = build_storage(get_settings())
    report_data = ReportData(
        product_name=data.product_name,
        pr_links=data.pr_links,
        version_numbers=data.version_numbers,
        test_url=data.test_url,
        workitem_url=data.workitem_url,
        jira_link=data.jira_link,
        general_description=data.general_description,
        certified=data.certified,
        features=[FeatureRow(**f.model_dump()) for f in data.features],
        exit_criteria=data.exit_criteria,
        result_analysis=ResultAnalysis(**data.result_analysis.model_dump()),
        automation_ratio=data.automation_ratio,
        bugs=BugsSummary(**data.bugs.model_dump()),
        exceptions=[ExceptionRow(**e.model_dump()) for e in data.exceptions],
        comments=data.comments,
        approvals=[
            ApprovalRow(
                action=a.action,
                name=a.name,
                staff_id=a.staff_id,
                date=a.date,
                signature_image=storage.get(a.signature_key) if a.signature_key else None,
            )
            for a in data.approvals
        ],
        classification_label=data.classification_label,
    )

    settings = get_settings()
    active_template = (
        db.query(Template)
        .filter(
            Template.kind == TemplateKind.DOCX_REPORT,
            Template.is_default.is_(True),
            Template.status == TemplateStatus.ACTIVE,
        )
        .first()
    )

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        template_path = tmp_path / "template.docx"
        if active_template and active_template.rendered_key:
            template_path.write_bytes(storage.get(active_template.rendered_key))
        else:
            tokenized_path = settings.templates_dir / "tokenized" / "QA_Test_Report_Template.docx"
            if not tokenized_path.exists():
                raise HTTPException(
                    status.HTTP_503_SERVICE_UNAVAILABLE,
                    "No docx report template is available yet — an admin needs to activate one "
                    "(Admin → Templates) or run `make -C services/api` tokenize-report-template.",
                )
            template_path.write_bytes(tokenized_path.read_bytes())

        out_path = tmp_path / "out.docx"
        write_report_docx(template_path, report_data, out_path)
        rendered = out_path.read_bytes()
        file_key = f"reports/{report.id}/v{report.version}.docx"
        storage.put(file_key, rendered)

    report.file_key = file_key
    db.commit()

    filename = f"{project.name}_QA_Test_Report.docx".replace(" ", "_")
    return StreamingResponse(
        iter([rendered]),
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
