"""Feature flags: which parts of QA Forge are switched on (admin-controlled, stored in the DB).

The registry below is the single list of switchable features and their defaults. A flag with no
database row takes its default, so a fresh install behaves as before until an admin changes it.
Enforcement lives on the server (router dependencies and `ensure_feature`), so a disabled
feature is refused even when called directly, not only hidden in the UI.
"""

from dataclasses import dataclass

from fastapi import Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.feature_flag import FeatureFlag


@dataclass(frozen=True)
class FeatureDef:
    key: str
    label: str
    description: str
    default: bool = True


FEATURES: tuple[FeatureDef, ...] = (
    FeatureDef(
        "test_lab_web", "Test Lab: Web runs", "AI agent drives a browser through test cases."
    ),
    FeatureDef("test_lab_api", "Test Lab: API runs", "Deterministic HTTP runs from request plans."),
    FeatureDef(
        "test_lab_android",
        "Test Lab: Android runs",
        "APK upload and emulator runs. Needs an Android emulator on the host.",
    ),
    FeatureDef(
        "api_spec_import",
        "API spec import",
        "Import OpenAPI, Postman, or curl definitions and generate API test cases.",
    ),
    FeatureDef(
        "ai_case_generation",
        "AI test case generation",
        "Generate functional test cases from user stories.",
    ),
    FeatureDef(
        "report_generation",
        "QA completion reports",
        "Draft, edit, and download the QA Test Completion Report.",
    ),
    FeatureDef("bug_tracking", "Bug tracking", "Raise and track defects from failing cases."),
)

FEATURE_BY_KEY: dict[str, FeatureDef] = {f.key: f for f in FEATURES}


def feature_states(db: Session) -> dict[str, bool]:
    states = {f.key: f.default for f in FEATURES}
    for row in db.query(FeatureFlag).all():
        if row.key in states:
            states[row.key] = row.enabled
    return states


def ensure_feature(db: Session, key: str) -> None:
    if not feature_states(db)[key]:
        label = FEATURE_BY_KEY[key].label
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, f"{label} is turned off. An admin can enable it in Settings."
        )


def require_feature(key: str):  # type: ignore[no-untyped-def]
    def _check(db: Session = Depends(get_db)) -> None:
        ensure_feature(db, key)

    return _check
