"""Retention and project-delete purge (PRD §12 Privacy: uploads & evidence default 180 days,
audit log default 2 years; "'delete project' purges storage objects").

Two separate operations:
- `purge_project_storage` runs once, synchronously, from the delete-project endpoint — the
  project row is already soft-deleted by the caller, so this is the one chance to reclaim the
  files it owned before they become unreachable.
- `sweep_retention` is time-based and runs however the operator schedules it
  (`python -m app.cli retention-sweep`) — no in-process scheduler in local mode
  (docs/decisions/001).

`Template` rows are deliberately out of scope for both: they're admin-managed, project-wide
report/case templates, not time-bound "uploads & evidence" artifacts.
"""

import contextlib
import uuid
from dataclasses import dataclass
from datetime import timedelta

from sqlalchemy.orm import Session

from app.db.base import utcnow
from app.models.apk import Apk
from app.models.audit_log import AuditLog
from app.models.evidence import Evidence
from app.models.report import Report
from app.models.test_case import TestCase
from app.models.test_run import RunStep
from app.models.test_suite import TestSuite
from app.models.user_story import UserStory
from app.services.storage import Storage, StorageError


def _safe_delete(storage: Storage, key: str | None) -> None:
    if not key:
        return
    with contextlib.suppress(StorageError):
        storage.delete(key)


@dataclass
class PurgeCounts:
    evidence: int = 0
    stories: int = 0
    reports: int = 0
    apks: int = 0


def purge_project_storage(session: Session, storage: Storage, project_id: uuid.UUID) -> PurgeCounts:
    counts = PurgeCounts()

    suite_ids = [
        row.id for row in session.query(TestSuite.id).filter(TestSuite.project_id == project_id)
    ]
    if suite_ids:
        case_ids = [
            row.id for row in session.query(TestCase.id).filter(TestCase.suite_id.in_(suite_ids))
        ]
        if case_ids:
            for (file_key,) in session.query(Evidence.file_key).filter(
                Evidence.test_case_id.in_(case_ids)
            ):
                _safe_delete(storage, file_key)
                counts.evidence += 1
        for (report_file_key,) in session.query(Report.file_key).filter(
            Report.suite_id.in_(suite_ids), Report.file_key.isnot(None)
        ):
            _safe_delete(storage, report_file_key)
            counts.reports += 1

    for (story_file_key,) in session.query(UserStory.file_key).filter(
        UserStory.project_id == project_id, UserStory.file_key.isnot(None)
    ):
        _safe_delete(storage, story_file_key)
        counts.stories += 1

    for (apk_file_key,) in session.query(Apk.file_key).filter(Apk.project_id == project_id):
        _safe_delete(storage, apk_file_key)
        counts.apks += 1

    return counts


@dataclass
class RetentionSweepResult:
    evidence_deleted: int = 0
    stories_purged: int = 0
    reports_purged: int = 0
    audit_log_deleted: int = 0


def sweep_retention(
    session: Session, storage: Storage, *, evidence_days: int, audit_log_days: int
) -> RetentionSweepResult:
    result = RetentionSweepResult()
    upload_cutoff = utcnow() - timedelta(days=evidence_days)
    audit_cutoff = utcnow() - timedelta(days=audit_log_days)

    old_evidence = session.query(Evidence).filter(Evidence.created_at < upload_cutoff).all()
    old_evidence_ids = [row.id for row in old_evidence]
    if old_evidence_ids:
        # RunStep.screenshot_evidence_id has no ON DELETE clause and the app runs with SQLite
        # foreign_keys=ON — deleting a referenced Evidence row would raise an IntegrityError.
        session.query(RunStep).filter(RunStep.screenshot_evidence_id.in_(old_evidence_ids)).update(
            {RunStep.screenshot_evidence_id: None}, synchronize_session="fetch"
        )
    for row in old_evidence:
        _safe_delete(storage, row.file_key)
        session.delete(row)
        result.evidence_deleted += 1

    # Stories and reports keep their row (the extracted text / rendered fields are still part
    # of suite history) — only the raw uploaded/rendered file is reclaimed.
    old_stories = (
        session.query(UserStory)
        .filter(UserStory.created_at < upload_cutoff, UserStory.file_key.isnot(None))
        .all()
    )
    for story in old_stories:
        _safe_delete(storage, story.file_key)
        story.file_key = None
        result.stories_purged += 1

    old_reports = (
        session.query(Report)
        .filter(Report.created_at < upload_cutoff, Report.file_key.isnot(None))
        .all()
    )
    for report in old_reports:
        _safe_delete(storage, report.file_key)
        report.file_key = None
        result.reports_purged += 1

    result.audit_log_deleted = (
        session.query(AuditLog).filter(AuditLog.at < audit_cutoff).delete(synchronize_session=False)
    )

    session.commit()
    return result
