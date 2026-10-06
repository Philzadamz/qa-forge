"""Feature flags: read by every signed-in user (so the UI can hide off features), changed by
admins only, under /admin/features."""

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.core.audit import record as audit_record
from app.core.features import FEATURE_BY_KEY, FEATURES, feature_states
from app.core.rbac import require_admin, require_user
from app.db.session import get_db
from app.models.feature_flag import FeatureFlag
from app.models.user import User
from app.schemas.features import FeatureOut, FeaturePatch

public_router = APIRouter(tags=["features"])
admin_router = APIRouter(prefix="/features", tags=["admin:features"])


def _listing(db: Session) -> list[FeatureOut]:
    states = feature_states(db)
    return [
        FeatureOut(key=f.key, label=f.label, description=f.description, enabled=states[f.key])
        for f in FEATURES
    ]


@public_router.get("/features", response_model=list[FeatureOut])
def list_features(
    db: Session = Depends(get_db), _: User = Depends(require_user)
) -> list[FeatureOut]:
    return _listing(db)


@admin_router.get("", response_model=list[FeatureOut])
def admin_list_features(
    db: Session = Depends(get_db), _: User = Depends(require_admin)
) -> list[FeatureOut]:
    return _listing(db)


@admin_router.put("/{key}", response_model=list[FeatureOut])
def set_feature(
    key: str,
    payload: FeaturePatch,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_admin),
) -> list[FeatureOut]:
    if key not in FEATURE_BY_KEY:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Unknown feature")
    before = feature_states(db)[key]
    row = db.get(FeatureFlag, key)
    if row is None:
        row = FeatureFlag(key=key)
        db.add(row)
    row.enabled = payload.enabled
    row.updated_by = user.id
    audit_record(
        db,
        actor_id=user.id,
        action="update",
        entity="feature_flag",
        entity_id=key,
        diff={"enabled": {"from": before, "to": payload.enabled}},
        request=request,
    )
    db.commit()
    return _listing(db)
