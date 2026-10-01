"""Bugs (PRD §7.6.4, §10 "CRUD /bugs"). Feeds the report's Bugs Summary (§3.2(d))."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.core.audit import record as audit_record
from app.core.rbac import require_project_access, require_user
from app.db.session import get_db
from app.models.bug import Bug
from app.models.project import Project
from app.models.test_case import TestCase
from app.models.test_suite import TestSuite
from app.models.user import User
from app.schemas.execution import BugIn, BugOut, BugPatch

router = APIRouter(tags=["bugs"])


def _get_project_or_404(db: Session, project_id: uuid.UUID, user: User) -> Project:
    obj = db.get(Project, project_id)
    if obj is None or obj.deleted_at is not None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Project not found")
    require_project_access(obj, user)
    return obj


def _get_suite_or_404(db: Session, suite_id: uuid.UUID, user: User) -> TestSuite:
    suite = db.get(TestSuite, suite_id)
    if suite is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Suite not found")
    _get_project_or_404(db, suite.project_id, user)
    return suite


def _get_bug_or_404(db: Session, bug_id: uuid.UUID, user: User) -> Bug:
    bug = db.get(Bug, bug_id)
    if bug is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Bug not found")
    _get_suite_or_404(db, bug.suite_id, user)
    return bug


@router.get("/suites/{suite_id}/bugs", response_model=list[BugOut])
def list_bugs(
    suite_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(require_user)
) -> list[Bug]:
    _get_suite_or_404(db, suite_id, user)
    return list(
        db.query(Bug).filter(Bug.suite_id == suite_id).order_by(Bug.created_at.desc()).all()
    )


@router.post("/suites/{suite_id}/bugs", response_model=BugOut, status_code=status.HTTP_201_CREATED)
def create_bug(
    suite_id: uuid.UUID,
    payload: BugIn,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_user),
) -> Bug:
    _get_suite_or_404(db, suite_id, user)
    if payload.test_case_id is not None:
        case = db.get(TestCase, payload.test_case_id)
        if case is None or case.suite_id != suite_id:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST, "test_case_id must belong to this suite"
            )
    obj = Bug(suite_id=suite_id, **payload.model_dump())
    db.add(obj)
    db.flush()
    audit_record(
        db, actor_id=user.id, action="create", entity="bug", entity_id=str(obj.id), request=request
    )
    db.commit()
    db.refresh(obj)
    return obj


@router.post(
    "/cases/{case_id}/bugs/draft", response_model=BugOut, status_code=status.HTTP_201_CREATED
)
def draft_bug_from_case(
    case_id: uuid.UUID,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_user),
) -> Bug:
    """PRD §7.6.4: a failed case can create a draft bug, pre-filled from its own fields
    (there's no run step log yet — that's Test Lab, Phase 5+ — so this drafts from the
    case's scenario/steps/expected/actual instead)."""
    case = db.get(TestCase, case_id)
    if case is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Test case not found")
    _get_suite_or_404(db, case.suite_id, user)

    steps_text = "\n".join(f"{i}. {s}" for i, s in enumerate(case.steps, start=1))
    description = (
        f"Steps to reproduce:\n{steps_text}\n\n"
        f"Expected: {case.expected_result}\n"
        f"Actual: {case.actual_result or '(not recorded)'}"
    )
    obj = Bug(
        suite_id=case.suite_id,
        test_case_id=case.id,
        title=f"{case.display_id or case.feature}: {case.scenario}",
        description=description,
    )
    db.add(obj)
    db.flush()
    audit_record(
        db, actor_id=user.id, action="draft", entity="bug", entity_id=str(obj.id), request=request
    )
    db.commit()
    db.refresh(obj)
    return obj


@router.patch("/bugs/{bug_id}", response_model=BugOut)
def update_bug(
    bug_id: uuid.UUID,
    payload: BugPatch,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_user),
) -> Bug:
    obj = _get_bug_or_404(db, bug_id, user)
    changes = payload.model_dump(exclude_unset=True)
    for key, value in changes.items():
        setattr(obj, key, value)
    audit_record(
        db,
        actor_id=user.id,
        action="update",
        entity="bug",
        entity_id=str(obj.id),
        diff=changes,
        request=request,
    )
    db.commit()
    db.refresh(obj)
    return obj


@router.delete("/bugs/{bug_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_bug(
    bug_id: uuid.UUID,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_user),
) -> None:
    obj = _get_bug_or_404(db, bug_id, user)
    audit_record(
        db, actor_id=user.id, action="delete", entity="bug", entity_id=str(bug_id), request=request
    )
    db.delete(obj)
    db.commit()
