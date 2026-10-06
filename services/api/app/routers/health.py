"""Liveness and readiness probes (PRD §12)."""

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse, Response
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.metrics import render as render_metrics
from app.db.session import get_db
from app.services.storage import build_storage

router = APIRouter(tags=["health"])


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/metrics", include_in_schema=False)
def metrics() -> Response:
    body, content_type = render_metrics()
    return Response(content=body, media_type=content_type)


@router.get("/ready")
def ready(db: Session = Depends(get_db)) -> JSONResponse:
    checks: dict[str, str] = {}
    try:
        db.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except SQLAlchemyError:
        checks["database"] = "error"
    checks["storage"] = "ok" if build_storage(get_settings()).healthy() else "error"
    ok = all(v == "ok" for v in checks.values())
    return JSONResponse(
        {"status": "ok" if ok else "degraded", "checks": checks},
        status_code=200 if ok else 503,
    )
