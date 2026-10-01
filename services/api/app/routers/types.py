"""Read-only test case types + resolved defaults for regular users (USR-GEN-1, ADM-DC-5)."""

import json
import re
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.rbac import require_user
from app.db.session import get_db
from app.models.test_case_type import DefaultTestCase, TestCaseType
from app.models.user import User
from app.schemas.admin import DefaultTestCaseOut, TestCaseTypeOut

router = APIRouter(tags=["types"])

_PLACEHOLDER_RE = re.compile(r"\{\{\s*(\w+)\s*\}\}")


def _resolve(text: str, values: dict[str, str]) -> str:
    def _sub(m: re.Match[str]) -> str:
        return values.get(m.group(1), m.group(0))

    return _PLACEHOLDER_RE.sub(_sub, text)


@router.get("/types", response_model=list[TestCaseTypeOut])
def list_active_types(
    db: Session = Depends(get_db), _: User = Depends(require_user)
) -> list[TestCaseType]:
    return list(
        db.query(TestCaseType)
        .filter(TestCaseType.is_active.is_(True))
        .order_by(TestCaseType.sort_order, TestCaseType.name)
        .all()
    )


@router.get("/types/{type_id}/defaults", response_model=list[DefaultTestCaseOut])
def list_resolved_defaults(
    type_id: uuid.UUID,
    placeholders: str | None = Query(
        default=None, description='JSON object of placeholder values, e.g. {"app_name":"Kusala"}'
    ),
    db: Session = Depends(get_db),
    _: User = Depends(require_user),
) -> list[DefaultTestCase] | list[DefaultTestCaseOut]:
    type_obj = db.get(TestCaseType, type_id)
    if type_obj is None or not type_obj.is_active:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Test case type not found")

    values: dict[str, str] = {}
    if placeholders:
        try:
            values = {str(k): str(v) for k, v in json.loads(placeholders).items()}
        except (json.JSONDecodeError, AttributeError) as exc:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST, "placeholders must be a JSON object"
            ) from exc

    defaults = (
        db.query(DefaultTestCase)
        .filter(DefaultTestCase.type_id == type_id, DefaultTestCase.is_active.is_(True))
        .order_by(DefaultTestCase.sort_order)
        .all()
    )
    if not values:
        return defaults

    # Build fresh output objects rather than mutating the ORM-tracked rows in place — those
    # are shared, session-cached instances, and this is a read endpoint, not an edit one.
    resolved = []
    for d in defaults:
        out = DefaultTestCaseOut.model_validate(d)
        out.feature = _resolve(out.feature, values)
        out.scenario = _resolve(out.scenario, values)
        out.steps = [_resolve(s, values) for s in out.steps]
        out.expected_result = _resolve(out.expected_result, values)
        resolved.append(out)
    return resolved
