"""ORM models. Import every model module here so Alembic autogenerate sees it."""

from app.db.base import Base
from app.models.apk import Apk
from app.models.audit_log import AuditLog
from app.models.bug import Bug
from app.models.evidence import Evidence
from app.models.generation_job import GenerationJob
from app.models.note_snippet import NoteSnippet
from app.models.password_reset_token import PasswordResetToken
from app.models.project import Project
from app.models.report import Report
from app.models.report_defaults import ReportDefaults
from app.models.secret import Secret
from app.models.template import Template
from app.models.test_case import TestCase
from app.models.test_case_type import DefaultTestCase, TestCaseType
from app.models.test_run import RunStep, TestRun
from app.models.test_suite import TestSuite
from app.models.usage_record import UsageRecord
from app.models.user import User
from app.models.user_story import UserStory

__all__ = [
    "Apk",
    "AuditLog",
    "Base",
    "Bug",
    "DefaultTestCase",
    "Evidence",
    "GenerationJob",
    "NoteSnippet",
    "PasswordResetToken",
    "Project",
    "Report",
    "ReportDefaults",
    "RunStep",
    "Secret",
    "Template",
    "TestCase",
    "TestCaseType",
    "TestRun",
    "TestSuite",
    "UsageRecord",
    "User",
    "UserStory",
]
