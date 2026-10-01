"""Admin: test case types (ADM-TT-1..3)."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.core.audit import record as audit_record
from app.core.rbac import require_admin
from app.db.session import get_db
from app.models.test_case_type import DefaultTestCase, TestCaseType
from app.models.user import User
from app.schemas.admin import TestCaseTypeIn, TestCaseTypeOut, TestCaseTypePatch

router = APIRouter(prefix="/types", tags=["admin:types"])


def _get_type_or_404(db: Session, type_id: uuid.UUID) -> TestCaseType:
    obj = db.get(TestCaseType, type_id)
    if obj is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Test case type not found")
    return obj


@router.get("", response_model=list[TestCaseTypeOut])
def list_types(
    db: Session = Depends(get_db), _: User = Depends(require_admin)
) -> list[TestCaseType]:
    return list(db.query(TestCaseType).order_by(TestCaseType.sort_order, TestCaseType.name).all())


@router.post("", response_model=TestCaseTypeOut, status_code=status.HTTP_201_CREATED)
def create_type(
    payload: TestCaseTypeIn,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_admin),
) -> TestCaseType:
    if db.query(TestCaseType).filter(TestCaseType.name == payload.name).one_or_none():
        raise HTTPException(status.HTTP_409_CONFLICT, "A type with this name already exists")
    obj = TestCaseType(**payload.model_dump())
    db.add(obj)
    db.flush()
    audit_record(
        db,
        actor_id=user.id,
        action="create",
        entity="test_case_type",
        entity_id=str(obj.id),
        request=request,
    )
    db.commit()
    db.refresh(obj)
    return obj


@router.get("/{type_id}", response_model=TestCaseTypeOut)
def get_type(
    type_id: uuid.UUID, db: Session = Depends(get_db), _: User = Depends(require_admin)
) -> TestCaseType:
    return _get_type_or_404(db, type_id)


@router.patch("/{type_id}", response_model=TestCaseTypeOut)
def update_type(
    type_id: uuid.UUID,
    payload: TestCaseTypePatch,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_admin),
) -> TestCaseType:
    obj = _get_type_or_404(db, type_id)
    changes = payload.model_dump(exclude_unset=True)
    for key, value in changes.items():
        setattr(obj, key, value)
    audit_record(
        db,
        actor_id=user.id,
        action="update",
        entity="test_case_type",
        entity_id=str(obj.id),
        diff=changes,
        request=request,
    )
    db.commit()
    db.refresh(obj)
    return obj


@router.delete("/{type_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_type(
    type_id: uuid.UUID,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_admin),
) -> None:
    obj = _get_type_or_404(db, type_id)
    has_defaults = (
        db.query(DefaultTestCase.id).filter(DefaultTestCase.type_id == type_id).limit(1).first()
    )
    if has_defaults:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "This type still has default test cases; deactivate it instead of deleting",
        )
    audit_record(
        db,
        actor_id=user.id,
        action="delete",
        entity="test_case_type",
        entity_id=str(type_id),
        request=request,
    )
    db.delete(obj)
    db.commit()


@router.post(
    "/{type_id}/duplicate", response_model=TestCaseTypeOut, status_code=status.HTTP_201_CREATED
)
def duplicate_type(
    type_id: uuid.UUID,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_admin),
) -> TestCaseType:
    """ADM-TT-3: copy a type and all its default cases."""
    source = _get_type_or_404(db, type_id)
    base_name = f"{source.name} (copy)"
    name = base_name
    suffix = 2
    while db.query(TestCaseType).filter(TestCaseType.name == name).one_or_none():
        name = f"{base_name} {suffix}"
        suffix += 1

    clone = TestCaseType(
        name=name,
        description=source.description,
        id_prefix_hint=source.id_prefix_hint,
        sort_order=source.sort_order,
        is_active=source.is_active,
    )
    db.add(clone)
    db.flush()

    for default in (
        db.query(DefaultTestCase)
        .filter(DefaultTestCase.type_id == type_id)
        .order_by(DefaultTestCase.sort_order)
    ):
        db.add(
            DefaultTestCase(
                type_id=clone.id,
                feature=default.feature,
                scenario=default.scenario,
                steps=list(default.steps),
                expected_result=default.expected_result,
                default_actual_result=default.default_actual_result,
                sort_order=default.sort_order,
                evidence_group=default.evidence_group,
                tags=list(default.tags),
                is_active=default.is_active,
            )
        )

    audit_record(
        db,
        actor_id=user.id,
        action="duplicate",
        entity="test_case_type",
        entity_id=str(clone.id),
        diff={"source_type_id": str(type_id)},
        request=request,
    )
    db.commit()
    db.refresh(clone)
    return clone
