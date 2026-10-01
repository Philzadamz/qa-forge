"""Manual case edits, evidence upload, and the suite's xlsx export (reuses the Phase 2
document engine)."""

import tempfile
import uuid
from collections import defaultdict
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.core.audit import record as audit_record
from app.core.config import get_settings
from app.core.enums import CaseSection, CaseSource, EvidenceKind, TemplateKind, TemplateStatus
from app.core.rbac import require_project_access, require_user
from app.db.session import get_db
from app.models.evidence import Evidence
from app.models.project import Project
from app.models.template import Template
from app.models.test_case import TestCase
from app.models.test_suite import TestSuite
from app.models.user import User
from app.schemas.execution import EvidenceOut
from app.schemas.suites import CaseBulkPatch, CaseCreate, CaseOut, CasePatch
from app.services.docengine.models import EvidenceImage, ExportCase, SuiteExportData, SuiteHeader
from app.services.docengine.xlsx_writer import write_test_cases_xlsx
from app.services.storage import build_storage
from app.services.suites.numbering import renumber_suite_cases

router = APIRouter(tags=["cases"])

MAX_EVIDENCE_BYTES = 10 * 1024 * 1024
ALLOWED_EVIDENCE_CONTENT_TYPES = {"image/png", "image/jpeg", "image/gif", "image/webp"}


def _get_project_or_404(db: Session, project_id: uuid.UUID, user: User) -> Project:
    obj = db.get(Project, project_id)
    if obj is None or obj.deleted_at is not None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Project not found")
    require_project_access(obj, user)
    return obj


def _get_suite_or_404(db: Session, suite_id: uuid.UUID, user: User) -> tuple[TestSuite, Project]:
    suite = db.get(TestSuite, suite_id)
    if suite is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Suite not found")
    project = _get_project_or_404(db, suite.project_id, user)
    return suite, project


def _get_case_or_404(
    db: Session, case_id: uuid.UUID, user: User
) -> tuple[TestCase, TestSuite, Project]:
    case = db.get(TestCase, case_id)
    if case is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Test case not found")
    suite, project = _get_suite_or_404(db, case.suite_id, user)
    return case, suite, project


@router.get("/suites/{suite_id}/cases", response_model=list[CaseOut])
def list_cases(
    suite_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(require_user)
) -> list[TestCase]:
    suite, _ = _get_suite_or_404(db, suite_id, user)
    cases = db.query(TestCase).filter(TestCase.suite_id == suite.id).all()
    cases.sort(key=lambda c: (0 if c.section == CaseSection.DEFAULT else 1, c.sort_order))
    return cases


@router.post(
    "/suites/{suite_id}/cases", response_model=CaseOut, status_code=status.HTTP_201_CREATED
)
def create_case(
    suite_id: uuid.UUID,
    payload: CaseCreate,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_user),
) -> TestCase:
    suite, project = _get_suite_or_404(db, suite_id, user)
    max_sort = db.query(TestCase).filter(TestCase.suite_id == suite.id).count()
    case = TestCase(
        suite_id=suite.id,
        source=CaseSource.MANUAL,
        sort_order=max_sort,
        case_no=0,
        display_id="",
        actual_result="",
        **payload.model_dump(),
    )
    db.add(case)
    db.flush()
    renumber_suite_cases(db, suite.id, project.id_prefix)
    audit_record(
        db,
        actor_id=user.id,
        action="create",
        entity="test_case",
        entity_id=str(case.id),
        request=request,
    )
    db.commit()
    db.refresh(case)
    return case


@router.post("/suites/{suite_id}/cases/bulk", response_model=list[CaseOut])
def bulk_update_cases(
    suite_id: uuid.UUID,
    payload: CaseBulkPatch,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_user),
) -> list[TestCase]:
    suite, project = _get_suite_or_404(db, suite_id, user)
    cases = (
        db.query(TestCase)
        .filter(TestCase.suite_id == suite.id, TestCase.id.in_(payload.case_ids))
        .all()
    )
    found_ids = {c.id for c in cases}
    missing = set(payload.case_ids) - found_ids
    if missing:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"Case(s) not found in this suite: {sorted(str(m) for m in missing)}",
        )

    changes = payload.model_dump(exclude_unset=True, exclude={"case_ids"})
    for case in cases:
        for key, value in changes.items():
            setattr(case, key, value)
    if "included" in changes:
        renumber_suite_cases(db, suite.id, project.id_prefix)

    audit_record(
        db,
        actor_id=user.id,
        action="bulk_update",
        entity="test_case",
        entity_id=str(suite.id),
        diff={"case_count": len(cases), **changes},
        request=request,
    )
    db.commit()
    for case in cases:
        db.refresh(case)
    return cases


@router.patch("/cases/{case_id}", response_model=CaseOut)
def update_case(
    case_id: uuid.UUID,
    payload: CasePatch,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_user),
) -> TestCase:
    case, suite, project = _get_case_or_404(db, case_id, user)
    changes = payload.model_dump(exclude_unset=True)
    renumber_needed = "included" in changes or "sort_order" in changes
    for key, value in changes.items():
        setattr(case, key, value)
    if renumber_needed:
        renumber_suite_cases(db, suite.id, project.id_prefix)
    audit_record(
        db,
        actor_id=user.id,
        action="update",
        entity="test_case",
        entity_id=str(case.id),
        diff=changes,
        request=request,
    )
    db.commit()
    db.refresh(case)
    return case


@router.delete("/cases/{case_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_case(
    case_id: uuid.UUID,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_user),
) -> None:
    case, suite, project = _get_case_or_404(db, case_id, user)
    db.delete(case)
    db.flush()
    renumber_suite_cases(db, suite.id, project.id_prefix)
    audit_record(
        db,
        actor_id=user.id,
        action="delete",
        entity="test_case",
        entity_id=str(case_id),
        request=request,
    )
    db.commit()


@router.get("/cases/{case_id}/evidence", response_model=list[EvidenceOut])
def list_evidence(
    case_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(require_user)
) -> list[Evidence]:
    _get_case_or_404(db, case_id, user)
    return list(
        db.query(Evidence)
        .filter(Evidence.test_case_id == case_id)
        .order_by(Evidence.sort_order)
        .all()
    )


@router.post(
    "/cases/{case_id}/evidence", response_model=EvidenceOut, status_code=status.HTTP_201_CREATED
)
async def upload_evidence(
    case_id: uuid.UUID,
    request: Request,
    file: UploadFile,
    db: Session = Depends(get_db),
    user: User = Depends(require_user),
) -> Evidence:
    case, _, _ = _get_case_or_404(db, case_id, user)
    if file.content_type not in ALLOWED_EVIDENCE_CONTENT_TYPES:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"Unsupported evidence type '{file.content_type}'. Use PNG, JPEG, GIF, or WebP.",
        )
    raw = await file.read()
    if len(raw) > MAX_EVIDENCE_BYTES:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Evidence file is too large (max 10 MB)")

    max_sort = db.query(Evidence).filter(Evidence.test_case_id == case_id).count()
    evidence_id = uuid.uuid4()
    extension = (
        (file.filename or "png").rsplit(".", 1)[-1].lower()
        if "." in (file.filename or "")
        else "png"
    )
    key = f"evidence/{case.suite_id}/{case_id}/{evidence_id}.{extension}"
    build_storage(get_settings()).put(key, raw)

    obj = Evidence(
        id=evidence_id,
        test_case_id=case_id,
        kind=EvidenceKind.SCREENSHOT,
        file_key=key,
        caption=file.filename,
        sort_order=max_sort,
    )
    db.add(obj)
    db.flush()
    audit_record(
        db,
        actor_id=user.id,
        action="upload",
        entity="evidence",
        entity_id=str(obj.id),
        request=request,
    )
    db.commit()
    db.refresh(obj)
    return obj


_EXTENSION_CONTENT_TYPES = {
    "png": "image/png",
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
    "gif": "image/gif",
    "webp": "image/webp",
}


@router.get("/evidence/{evidence_id}/file")
def get_evidence_file(
    evidence_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(require_user)
) -> StreamingResponse:
    obj = db.get(Evidence, evidence_id)
    if obj is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Evidence not found")
    _get_case_or_404(db, obj.test_case_id, user)
    raw = build_storage(get_settings()).get(obj.file_key)
    extension = obj.file_key.rsplit(".", 1)[-1].lower()
    content_type = _EXTENSION_CONTENT_TYPES.get(extension, "application/octet-stream")
    return StreamingResponse(iter([raw]), media_type=content_type)


@router.delete("/evidence/{evidence_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_evidence(
    evidence_id: uuid.UUID,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_user),
) -> None:
    obj = db.get(Evidence, evidence_id)
    if obj is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Evidence not found")
    _get_case_or_404(db, obj.test_case_id, user)
    build_storage(get_settings()).delete(obj.file_key)
    audit_record(
        db,
        actor_id=user.id,
        action="delete",
        entity="evidence",
        entity_id=str(evidence_id),
        request=request,
    )
    db.delete(obj)
    db.commit()


@router.post("/suites/{suite_id}/export/xlsx")
def export_xlsx(
    suite_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(require_user)
) -> StreamingResponse:
    suite, project = _get_suite_or_404(db, suite_id, user)
    cases = (
        db.query(TestCase).filter(TestCase.suite_id == suite.id, TestCase.included.is_(True)).all()
    )
    cases.sort(key=lambda c: (0 if c.section == CaseSection.DEFAULT else 1, c.sort_order))

    settings = get_settings()
    storage = build_storage(settings)

    evidence_by_case: dict[uuid.UUID, list[Evidence]] = defaultdict(list)
    if cases:
        for e in (
            db.query(Evidence)
            .filter(Evidence.test_case_id.in_([c.id for c in cases]))
            .order_by(Evidence.sort_order)
            .all()
        ):
            evidence_by_case[e.test_case_id].append(e)

    def h(key: str) -> str:
        value = suite.header_json.get(key)
        return str(value) if value is not None else ""

    active_template = (
        db.query(Template)
        .filter(
            Template.kind == TemplateKind.XLSX_TEST_CASES,
            Template.is_default.is_(True),
            Template.status == TemplateStatus.ACTIVE,
        )
        .filter((Template.type_id == suite.type_id) | (Template.type_id.is_(None)))
        .order_by(Template.type_id.isnot(None).desc())  # prefer a type-specific template
        .first()
    )

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)

        def to_export_case(c: TestCase) -> ExportCase:
            images = []
            for e in evidence_by_case.get(c.id, []):
                ext = e.file_key.rsplit(".", 1)[-1]
                local_path = tmp_path / f"evidence-{e.id}.{ext}"
                local_path.write_bytes(storage.get(e.file_key))
                images.append(EvidenceImage(file_path=local_path, caption=e.caption))
            return ExportCase(
                case_no=c.display_id,
                feature=c.feature,
                scenario=c.scenario,
                steps=c.steps,
                expected_result=c.expected_result,
                actual_result=c.actual_result,
                status=c.status,
                evidence_group=c.evidence_group,
                is_regression=c.is_regression,
                evidence=images,
            )

        data = SuiteExportData(
            header=SuiteHeader(
                project_name_line=h("project_name_line"),
                user_group_dept=h("user_group_dept"),
                solution_provider=h("solution_provider"),
                developers=h("developers"),
                test_done_by=h("test_done_by"),
                test_reviewed_by=h("test_reviewed_by"),
                start_date=h("start_date"),
                end_date=h("end_date"),
                test_description=h("test_description"),
                endpoint_url=h("endpoint_url"),
            ),
            default_cases=[to_export_case(c) for c in cases if c.section == CaseSection.DEFAULT],
            functional_cases=[
                to_export_case(c) for c in cases if c.section == CaseSection.FUNCTIONAL
            ],
        )

        template_path = tmp_path / "template.xlsx"
        if active_template:
            template_path.write_bytes(storage.get(active_template.file_key))
        else:
            source_path = settings.templates_dir / "source" / "QA_Test_Cases_Template.xlsx"
            if not source_path.exists():
                raise HTTPException(
                    status.HTTP_503_SERVICE_UNAVAILABLE,
                    "No xlsx template is available yet — an admin needs to activate one "
                    "(Admin → Templates) or place the team template at templates/source/.",
                )
            template_path.write_bytes(source_path.read_bytes())

        out_path = tmp_path / "out.xlsx"
        write_test_cases_xlsx(template_path, data, out_path)
        rendered = out_path.read_bytes()

    filename = f"{project.app_code}_{suite.name}_QA_Test_Cases.xlsx".replace(" ", "_")
    return StreamingResponse(
        iter([rendered]),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
