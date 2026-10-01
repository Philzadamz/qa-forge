"""Admin: default test cases per type (ADM-DC-1..6)."""

import csv
import io
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.core.audit import record as audit_record
from app.core.rbac import require_admin
from app.db.session import get_db
from app.models.test_case_type import DefaultTestCase, TestCaseType
from app.models.user import User
from app.schemas.admin import (
    DefaultTestCaseIn,
    DefaultTestCaseOut,
    DefaultTestCasePatch,
    ImportConfirmRequest,
    ImportPreviewResponse,
    ImportWarning,
    ReorderRequest,
)
from app.services.docengine.xlsx_importer import XlsxImportError, parse_default_scenarios

router = APIRouter(tags=["admin:defaults"])


def _get_type_or_404(db: Session, type_id: uuid.UUID) -> TestCaseType:
    obj = db.get(TestCaseType, type_id)
    if obj is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Test case type not found")
    return obj


def _get_default_or_404(db: Session, default_id: uuid.UUID) -> DefaultTestCase:
    obj = db.get(DefaultTestCase, default_id)
    if obj is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Default test case not found")
    return obj


@router.get("/types/{type_id}/defaults", response_model=list[DefaultTestCaseOut])
def list_defaults(
    type_id: uuid.UUID, db: Session = Depends(get_db), _: User = Depends(require_admin)
) -> list[DefaultTestCase]:
    _get_type_or_404(db, type_id)
    return list(
        db.query(DefaultTestCase)
        .filter(DefaultTestCase.type_id == type_id)
        .order_by(DefaultTestCase.sort_order)
        .all()
    )


@router.post(
    "/types/{type_id}/defaults",
    response_model=DefaultTestCaseOut,
    status_code=status.HTTP_201_CREATED,
)
def create_default(
    type_id: uuid.UUID,
    payload: DefaultTestCaseIn,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_admin),
) -> DefaultTestCase:
    _get_type_or_404(db, type_id)
    obj = DefaultTestCase(type_id=type_id, **payload.model_dump())
    db.add(obj)
    db.flush()
    audit_record(
        db,
        actor_id=user.id,
        action="create",
        entity="default_test_case",
        entity_id=str(obj.id),
        request=request,
    )
    db.commit()
    db.refresh(obj)
    return obj


@router.patch("/defaults/{default_id}", response_model=DefaultTestCaseOut)
def update_default(
    default_id: uuid.UUID,
    payload: DefaultTestCasePatch,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_admin),
) -> DefaultTestCase:
    obj = _get_default_or_404(db, default_id)
    changes = payload.model_dump(exclude_unset=True)
    for key, value in changes.items():
        setattr(obj, key, value)
    if changes:
        # ADM-DC-6: bump version on every save; suites snapshot the version they used.
        obj.version += 1
    audit_record(
        db,
        actor_id=user.id,
        action="update",
        entity="default_test_case",
        entity_id=str(obj.id),
        diff=changes,
        request=request,
    )
    db.commit()
    db.refresh(obj)
    return obj


@router.delete("/defaults/{default_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_default(
    default_id: uuid.UUID,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_admin),
) -> None:
    obj = _get_default_or_404(db, default_id)
    audit_record(
        db,
        actor_id=user.id,
        action="delete",
        entity="default_test_case",
        entity_id=str(default_id),
        request=request,
    )
    db.delete(obj)
    db.commit()


@router.post("/types/{type_id}/defaults/reorder", response_model=list[DefaultTestCaseOut])
def reorder_defaults(
    type_id: uuid.UUID,
    payload: ReorderRequest,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_admin),
) -> list[DefaultTestCase]:
    _get_type_or_404(db, type_id)
    existing = {
        d.id: d for d in db.query(DefaultTestCase).filter(DefaultTestCase.type_id == type_id).all()
    }
    if set(payload.ordered_ids) != set(existing.keys()):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "ordered_ids must contain exactly this type's default cases",
        )
    for index, default_id in enumerate(payload.ordered_ids):
        existing[default_id].sort_order = index
    audit_record(
        db,
        actor_id=user.id,
        action="reorder",
        entity="default_test_case",
        entity_id=str(type_id),
        request=request,
    )
    db.commit()
    return list(
        db.query(DefaultTestCase)
        .filter(DefaultTestCase.type_id == type_id)
        .order_by(DefaultTestCase.sort_order)
        .all()
    )


@router.post("/types/{type_id}/defaults/import", response_model=ImportPreviewResponse)
async def import_defaults_preview(
    type_id: uuid.UUID,
    file: UploadFile,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> ImportPreviewResponse:
    """Parse an uploaded template-format workbook without saving anything (ADM-DC-3)."""
    _get_type_or_404(db, type_id)
    content = await file.read()
    try:
        result = parse_default_scenarios(content)
    except XlsxImportError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
    return ImportPreviewResponse(
        cases=[
            DefaultTestCaseIn(
                feature=c.feature,
                scenario=c.scenario,
                steps=c.steps,
                expected_result=c.expected_result,
                default_actual_result=c.default_actual_result,
                evidence_group=c.evidence_group,
                sort_order=c.sort_order,
            )
            for c in result.cases
        ],
        warnings=[ImportWarning(row=w.row, message=w.message) for w in result.warnings],
    )


@router.post(
    "/types/{type_id}/defaults/import/confirm",
    response_model=list[DefaultTestCaseOut],
    status_code=status.HTTP_201_CREATED,
)
def import_defaults_confirm(
    type_id: uuid.UUID,
    payload: ImportConfirmRequest,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_admin),
) -> list[DefaultTestCase]:
    _get_type_or_404(db, type_id)
    if payload.replace_existing:
        db.query(DefaultTestCase).filter(DefaultTestCase.type_id == type_id).delete()

    created: list[DefaultTestCase] = []
    for case in payload.cases:
        obj = DefaultTestCase(type_id=type_id, **case.model_dump())
        db.add(obj)
        created.append(obj)
    db.flush()
    audit_record(
        db,
        actor_id=user.id,
        action="import",
        entity="default_test_case",
        entity_id=str(type_id),
        diff={"count": len(created), "replace_existing": payload.replace_existing},
        request=request,
    )
    db.commit()
    for obj in created:
        db.refresh(obj)
    return created


@router.get("/types/{type_id}/defaults/export")
def export_defaults(
    type_id: uuid.UUID, db: Session = Depends(get_db), _: User = Depends(require_admin)
) -> StreamingResponse:
    """ADM-DC-4: CSV export. The template-styled xlsx export reuses the Phase 2 doc engine."""
    type_obj = _get_type_or_404(db, type_id)
    defaults = (
        db.query(DefaultTestCase)
        .filter(DefaultTestCase.type_id == type_id)
        .order_by(DefaultTestCase.sort_order)
        .all()
    )
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(
        [
            "Feature",
            "Scenario",
            "Steps",
            "Expected Result",
            "Default Actual Result",
            "Evidence Group",
            "Tags",
            "Active",
        ]
    )
    for d in defaults:
        writer.writerow(
            [
                d.feature,
                d.scenario,
                "\n".join(f"{i}. {s}" for i, s in enumerate(d.steps, start=1)),
                d.expected_result,
                d.default_actual_result,
                d.evidence_group,
                ", ".join(d.tags),
                "Yes" if d.is_active else "No",
            ]
        )
    buffer.seek(0)
    filename = f"{type_obj.name.replace(' ', '_')}_defaults.csv"
    return StreamingResponse(
        iter([buffer.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
