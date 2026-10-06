"""Usage dashboard (PRD §12 Observability; Phase 8 DoD). Scoped to the projects the caller can
see — admins see everything, everyone else sees projects they own or are a member of, the same
rule as `GET /projects`."""

import datetime as dt
import uuid
from collections import defaultdict

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core import usage
from app.core.config import get_settings
from app.core.enums import RunStatus
from app.core.rbac import require_user
from app.db.base import utcnow
from app.db.session import get_db
from app.models.generation_job import GenerationJob
from app.models.project import Project
from app.models.test_run import TestRun
from app.models.test_suite import TestSuite
from app.models.usage_record import UsageRecord
from app.models.user import User
from app.schemas.dashboard import DashboardOut, FeatureUsageOut, RecentRunOut, UsageSummaryOut

router = APIRouter(prefix="/dashboard", tags=["dashboard"])

USAGE_WINDOW_DAYS = 30
RECENT_RUN_LIMIT = 10


def _visible_project_ids(db: Session, user: User) -> list[uuid.UUID]:
    query = db.query(Project).filter(Project.deleted_at.is_(None))
    if user.role == "admin":
        return [p.id for p in query.all()]
    owned = [p.id for p in query.filter(Project.owner_id == user.id).all()]
    member = [
        p.id for p in query.filter(Project.owner_id != user.id).all() if str(user.id) in p.members
    ]
    return owned + member


def _aware(value: dt.datetime) -> dt.datetime:
    # SQLite returns naive datetimes; comparing them with the aware window start raises.
    return value if value.tzinfo is not None else value.replace(tzinfo=dt.UTC)


def _count(value: object) -> int:
    return value if isinstance(value, int) else 0


def _project_for_usage(
    record: UsageRecord,
    *,
    run_project: dict[str, uuid.UUID],
    job_project: dict[str, uuid.UUID],
    suite_project: dict[str, uuid.UUID],
) -> uuid.UUID | None:
    if record.feature == "execution_run":
        return run_project.get(record.entity_id or "")
    if record.feature == "story_generation":
        return job_project.get(record.entity_id or "")
    return suite_project.get(record.entity_id or "")


@router.get("", response_model=DashboardOut)
def get_dashboard(
    db: Session = Depends(get_db), user: User = Depends(require_user)
) -> DashboardOut:
    project_ids = _visible_project_ids(db, user)
    if not project_ids:
        return DashboardOut(
            project_count=0,
            suite_count=0,
            run_count_30_days=0,
            pass_rate_30_days=None,
            recent_runs=[],
            usage=UsageSummaryOut(
                window_days=USAGE_WINDOW_DAYS,
                prompt_tokens=0,
                completion_tokens=0,
                cost_estimate=0.0,
                by_feature=[],
            ),
        )

    suites = db.query(TestSuite).filter(TestSuite.project_id.in_(project_ids)).all()
    suite_names = {s.id: s.name for s in suites}
    suite_project = {str(s.id): s.project_id for s in suites}

    window_start = utcnow() - dt.timedelta(days=USAGE_WINDOW_DAYS)
    runs = (
        db.query(TestRun)
        .filter(TestRun.project_id.in_(project_ids))
        .order_by(TestRun.created_at.desc())
        .all()
    )
    recent_window_runs = [r for r in runs if _aware(r.created_at) >= window_start]
    finished = [r for r in recent_window_runs if r.status in (RunStatus.PASSED, RunStatus.FAILED)]
    pass_rate = (
        sum(1 for r in finished if r.status == RunStatus.PASSED) / len(finished)
        if finished
        else None
    )

    recent_runs = [
        RecentRunOut(
            id=r.id,
            suite_id=r.suite_id,
            suite_name=suite_names.get(r.suite_id) if r.suite_id else None,
            target=r.target.value,
            status=r.status.value,
            total=_count(r.summary_json.get("total")),
            passed=_count(r.summary_json.get("passed")),
            failed=_count(r.summary_json.get("failed")),
            created_at=r.created_at,
        )
        for r in runs[:RECENT_RUN_LIMIT]
    ]

    run_project = {str(r.id): r.project_id for r in runs}
    job_project = {
        str(j.id): suite_project[str(j.suite_id)]
        for j in db.query(GenerationJob).filter(GenerationJob.suite_id.in_(list(suite_names)))
    }

    records = db.query(UsageRecord).filter(UsageRecord.at >= window_start).all()
    totals: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    prompt_total = 0
    completion_total = 0
    for record in records:
        if (
            _project_for_usage(
                record,
                run_project=run_project,
                job_project=job_project,
                suite_project=suite_project,
            )
            not in project_ids
        ):
            continue
        totals[record.feature][0] += record.prompt_tokens
        totals[record.feature][1] += record.completion_tokens
        prompt_total += record.prompt_tokens
        completion_total += record.completion_tokens

    settings = get_settings()
    cost = usage.estimate_cost(
        prompt_tokens=prompt_total,
        completion_tokens=completion_total,
        cost_per_million_input=settings.ai_cost_per_million_input_tokens,
        cost_per_million_output=settings.ai_cost_per_million_output_tokens,
    )

    return DashboardOut(
        project_count=len(project_ids),
        suite_count=len(suites),
        run_count_30_days=len(recent_window_runs),
        pass_rate_30_days=pass_rate,
        recent_runs=recent_runs,
        usage=UsageSummaryOut(
            window_days=USAGE_WINDOW_DAYS,
            prompt_tokens=prompt_total,
            completion_tokens=completion_total,
            cost_estimate=cost,
            by_feature=[
                FeatureUsageOut(feature=f, prompt_tokens=p, completion_tokens=c)
                for f, (p, c) in sorted(totals.items())
            ],
        ),
    )
