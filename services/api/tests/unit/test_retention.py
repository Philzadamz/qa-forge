"""Project-delete purge and time-based retention sweep (PRD §12 Privacy)."""

import uuid
from datetime import timedelta

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.enums import CaseSection, CaseSource, RunTarget, StorySource, TestStatus
from app.db.base import utcnow
from app.models.apk import Apk
from app.models.audit_log import AuditLog
from app.models.evidence import Evidence
from app.models.project import Project
from app.models.report import Report
from app.models.test_case import TestCase
from app.models.test_case_type import TestCaseType
from app.models.test_run import RunStep, TestRun
from app.models.test_suite import TestSuite
from app.models.user import User
from app.models.user_story import UserStory
from app.services.retention import purge_project_storage, sweep_retention
from app.services.storage import build_storage
from tests.conftest import make_user


def _build_suite_and_case(db_session: Session, project: Project) -> tuple[TestSuite, TestCase]:
    type_obj = TestCaseType(name=f"Type-{uuid.uuid4().hex[:8]}")
    db_session.add(type_obj)
    db_session.flush()
    suite = TestSuite(project_id=project.id, type_id=type_obj.id, name="Suite")
    db_session.add(suite)
    db_session.flush()
    case = TestCase(
        suite_id=suite.id,
        section=CaseSection.FUNCTIONAL,
        case_no=1,
        display_id="T_001",
        feature="f",
        scenario="s",
        expected_result="e",
        status=TestStatus.NOT_TESTED,
        source=CaseSource.MANUAL,
    )
    db_session.add(case)
    db_session.flush()
    return suite, case


def _owner(db_session: Session) -> User:
    return make_user(db_session, email=f"owner-{uuid.uuid4().hex[:8]}@example.com")


def test_purge_project_storage_deletes_every_owned_file(db_session: Session) -> None:
    owner = _owner(db_session)
    project = Project(name="P", app_code="P", id_prefix="P", owner_id=owner.id)
    db_session.add(project)
    db_session.flush()
    suite, case = _build_suite_and_case(db_session, project)

    storage = build_storage(get_settings())
    storage.put("evidence/e1.png", b"img")
    storage.put("reports/r1.docx", b"doc")
    storage.put("stories/s1.pdf", b"pdf")
    storage.put("apks/a1.apk", b"apk")

    db_session.add(Evidence(test_case_id=case.id, file_key="evidence/e1.png"))
    db_session.add(Report(suite_id=suite.id, file_key="reports/r1.docx"))
    db_session.add(
        UserStory(
            project_id=project.id,
            title="Story",
            source=StorySource.UPLOAD,
            file_key="stories/s1.pdf",
        )
    )
    db_session.add(
        Apk(
            project_id=project.id,
            uploaded_by=owner.id,
            file_key="apks/a1.apk",
            file_name="a1.apk",
            file_size=3,
            package_name="com.example",
            launch_activity=".Main",
        )
    )
    db_session.commit()

    counts = purge_project_storage(db_session, storage, project.id)

    assert (counts.evidence, counts.reports, counts.stories, counts.apks) == (1, 1, 1, 1)
    assert not storage.exists("evidence/e1.png")
    assert not storage.exists("reports/r1.docx")
    assert not storage.exists("stories/s1.pdf")
    assert not storage.exists("apks/a1.apk")


def test_purge_project_storage_ignores_other_projects(db_session: Session) -> None:
    owner = _owner(db_session)
    project_a = Project(name="A", app_code="A", id_prefix="A", owner_id=owner.id)
    project_b = Project(name="B", app_code="B", id_prefix="B", owner_id=owner.id)
    db_session.add_all([project_a, project_b])
    db_session.flush()

    storage = build_storage(get_settings())
    storage.put("apks/keep.apk", b"apk")
    db_session.add(
        Apk(
            project_id=project_b.id,
            uploaded_by=owner.id,
            file_key="apks/keep.apk",
            file_name="keep.apk",
            file_size=3,
            package_name="com.keep",
            launch_activity=".Main",
        )
    )
    db_session.commit()

    counts = purge_project_storage(db_session, storage, project_a.id)

    assert counts.apks == 0
    assert storage.exists("apks/keep.apk")


def test_sweep_retention_deletes_old_evidence_and_nulls_run_step_reference(
    db_session: Session,
) -> None:
    owner = _owner(db_session)
    project = Project(name="P", app_code="P", id_prefix="P", owner_id=owner.id)
    db_session.add(project)
    db_session.flush()
    suite, case = _build_suite_and_case(db_session, project)
    run = TestRun(
        project_id=project.id,
        suite_id=suite.id,
        target=RunTarget.WEB,
        selected_case_ids=[str(case.id)],
    )
    db_session.add(run)
    db_session.flush()

    storage = build_storage(get_settings())
    storage.put("evidence/old.png", b"old")
    storage.put("evidence/new.png", b"new")

    old_evidence = Evidence(test_case_id=case.id, run_id=run.id, file_key="evidence/old.png")
    new_evidence = Evidence(test_case_id=case.id, run_id=run.id, file_key="evidence/new.png")
    db_session.add_all([old_evidence, new_evidence])
    db_session.flush()
    old_evidence.created_at = utcnow() - timedelta(days=200)
    step = RunStep(
        run_id=run.id,
        test_case_id=case.id,
        seq=1,
        action="assert_visible",
        screenshot_evidence_id=old_evidence.id,
    )
    db_session.add(step)
    db_session.commit()
    step_id = step.id

    result = sweep_retention(db_session, storage, evidence_days=180, audit_log_days=730)

    assert result.evidence_deleted == 1
    assert not storage.exists("evidence/old.png")
    assert storage.exists("evidence/new.png")
    assert db_session.get(Evidence, old_evidence.id) is None
    refreshed_step = db_session.get(RunStep, step_id)
    assert refreshed_step is not None
    assert refreshed_step.screenshot_evidence_id is None


def test_sweep_retention_purges_old_story_and_report_files_but_keeps_rows(
    db_session: Session,
) -> None:
    owner = _owner(db_session)
    project = Project(name="P", app_code="P", id_prefix="P", owner_id=owner.id)
    db_session.add(project)
    db_session.flush()
    suite, _case = _build_suite_and_case(db_session, project)

    storage = build_storage(get_settings())
    storage.put("stories/old.pdf", b"old")
    storage.put("reports/old.docx", b"old")

    story = UserStory(
        project_id=project.id, title="S", source=StorySource.UPLOAD, file_key="stories/old.pdf"
    )
    report = Report(suite_id=suite.id, file_key="reports/old.docx")
    db_session.add_all([story, report])
    db_session.commit()
    story.created_at = utcnow() - timedelta(days=200)
    report.created_at = utcnow() - timedelta(days=200)
    db_session.commit()

    result = sweep_retention(db_session, storage, evidence_days=180, audit_log_days=730)

    assert result.stories_purged == 1
    assert result.reports_purged == 1
    assert not storage.exists("stories/old.pdf")
    assert not storage.exists("reports/old.docx")
    db_session.refresh(story)
    db_session.refresh(report)
    assert story.file_key is None
    assert report.file_key is None


def test_sweep_retention_deletes_old_audit_log_rows_only(db_session: Session) -> None:
    storage = build_storage(get_settings())
    old_row = AuditLog(action="login", entity="user", entity_id="x")
    recent_row = AuditLog(action="login", entity="user", entity_id="y")
    db_session.add_all([old_row, recent_row])
    db_session.commit()
    old_row.at = utcnow() - timedelta(days=800)
    db_session.commit()

    result = sweep_retention(db_session, storage, evidence_days=180, audit_log_days=730)

    assert result.audit_log_deleted == 1
    remaining = db_session.query(AuditLog).all()
    assert [r.id for r in remaining] == [recent_row.id]
