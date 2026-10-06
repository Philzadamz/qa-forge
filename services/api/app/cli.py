"""Operator CLI: `uv run python -m app.cli <command>` (wired through the Makefile)."""

import argparse
import sys
from pathlib import Path

from app.core.config import REPO_ROOT, get_settings
from app.core.report_defaults import DEFAULT_APPROVAL_ROLES, DEFAULT_EXIT_CRITERIA
from app.core.security import hash_password
from app.db.session import get_sessionmaker
from app.models.report_defaults import ReportDefaults
from app.models.test_case_type import DefaultTestCase, TestCaseType
from app.models.user import User
from app.services.docengine.docx_tokenizer import DocxTokenizeError, tokenize_report_template
from app.services.docengine.xlsx_importer import XlsxImportError, parse_default_scenarios
from app.services.retention import sweep_retention
from app.services.storage import build_storage

DEFAULT_TEMPLATE_PATH = REPO_ROOT / "templates" / "source" / "QA_Test_Cases_Template.xlsx"
REPORT_SOURCE_TEMPLATE_PATH = REPO_ROOT / "templates" / "source" / "QA_Test_Report_Template.docx"
REPORT_TOKENIZED_PATH = REPO_ROOT / "templates" / "tokenized" / "QA_Test_Report_Template.docx"
SEED_TYPE_NAME = "Web Application"


def seed_admin(email: str, password: str, full_name: str = "Admin") -> None:
    session = get_sessionmaker()()
    try:
        existing = session.query(User).filter(User.email == email.lower()).one_or_none()
        if existing is not None:
            print(f"User {email} already exists (role={existing.role}); not modifying it.")
            return
        user = User(
            email=email.lower(),
            full_name=full_name,
            role="admin",
            password_hash=hash_password(password),
        )
        session.add(user)
        session.commit()
        print(f"Created admin user {email}.")
    finally:
        session.close()


def seed_defaults(template_path: Path = DEFAULT_TEMPLATE_PATH) -> None:
    """ADM-DC-3 seed data: import the 31 default scenarios into the 'Web Application' type."""
    if not template_path.exists():
        print(
            f"No template at {template_path} — copy the team's QA_Test_Cases_Template.xlsx "
            "there first (see templates/source/README.md). Skipping."
        )
        return

    session = get_sessionmaker()()
    try:
        existing_type = (
            session.query(TestCaseType).filter(TestCaseType.name == SEED_TYPE_NAME).one_or_none()
        )
        if existing_type is not None:
            print(f"Type '{SEED_TYPE_NAME}' already exists; not re-seeding.")
            return

        try:
            result = parse_default_scenarios(template_path.read_bytes())
        except XlsxImportError as exc:
            print(f"Failed to parse template: {exc}")
            sys.exit(1)

        if result.warnings:
            for warning in result.warnings:
                print(f"  warning (row {warning.row}): {warning.message}")

        type_obj = TestCaseType(
            name=SEED_TYPE_NAME, description="Seeded from the team template", sort_order=0
        )
        session.add(type_obj)
        session.flush()
        for case in result.cases:
            session.add(
                DefaultTestCase(
                    type_id=type_obj.id,
                    feature=case.feature,
                    scenario=case.scenario,
                    steps=case.steps,
                    expected_result=case.expected_result,
                    default_actual_result=case.default_actual_result,
                    evidence_group=case.evidence_group,
                    sort_order=case.sort_order,
                )
            )
        session.commit()
        print(f"Seeded {len(result.cases)} default scenarios into '{SEED_TYPE_NAME}'.")
    finally:
        session.close()


def tokenize_report(
    source_path: Path = REPORT_SOURCE_TEMPLATE_PATH, output_path: Path = REPORT_TOKENIZED_PATH
) -> None:
    """ADM-TM-2: rebuild the docxtpl-tagged working copy from the raw team template."""
    if not source_path.exists():
        print(
            f"No template at {source_path} — copy the team's QA_Test_Report_Template.docx "
            "there first (see templates/source/README.md). Skipping."
        )
        return
    try:
        tokenize_report_template(source_path, output_path)
    except DocxTokenizeError as exc:
        print(f"Failed to tokenize template: {exc}")
        sys.exit(1)
    print(f"Wrote tokenized template to {output_path}.")


def seed_report_defaults() -> None:
    """PRD §14 seed data: 3 exit criteria, 4 approval roles, classification label 'Public'."""
    session = get_sessionmaker()()
    try:
        if session.query(ReportDefaults).count() > 0:
            print("Report defaults already seeded; not modifying them.")
            return
        session.add(
            ReportDefaults(
                exit_criteria=DEFAULT_EXIT_CRITERIA,
                approval_roles=DEFAULT_APPROVAL_ROLES,
                classification_label="Public",
                organisation_name="",
            )
        )
        session.commit()
        print("Seeded report defaults (3 exit criteria, 4 approval roles, label 'Public').")
    finally:
        session.close()


def retention_sweep() -> None:
    """PRD §12 Privacy: purge evidence/upload files past retention and prune the audit log.
    Intended to be run on a schedule (e.g. a daily cron calling `make retention-sweep`) —
    there's no in-process scheduler in local mode (docs/decisions/001)."""
    settings = get_settings()
    storage = build_storage(settings)
    session = get_sessionmaker()()
    try:
        result = sweep_retention(
            session,
            storage,
            evidence_days=settings.retention_evidence_days,
            audit_log_days=settings.retention_audit_log_days,
        )
        print(
            f"Deleted {result.evidence_deleted} evidence file(s) older than "
            f"{settings.retention_evidence_days}d, purged {result.stories_purged} story "
            f"upload(s) and {result.reports_purged} report file(s), removed "
            f"{result.audit_log_deleted} audit log row(s) older than "
            f"{settings.retention_audit_log_days}d."
        )
    finally:
        session.close()


def main() -> None:
    parser = argparse.ArgumentParser(prog="app.cli")
    subparsers = parser.add_subparsers(dest="command", required=True)

    seed_admin_parser = subparsers.add_parser("seed-admin", help="Create the first admin user")
    seed_admin_parser.add_argument("--email", required=True)
    seed_admin_parser.add_argument("--password", required=True)
    seed_admin_parser.add_argument("--full-name", default="Admin")

    subparsers.add_parser(
        "seed-defaults", help="Import the 31 default scenarios from the team template"
    )
    subparsers.add_parser(
        "tokenize-report-template",
        help="Rebuild templates/tokenized/QA_Test_Report_Template.docx from the raw template",
    )
    subparsers.add_parser(
        "seed-report-defaults", help="Seed exit criteria, approval roles, and classification label"
    )
    subparsers.add_parser(
        "retention-sweep",
        help="Purge evidence/upload files past retention and prune the audit log",
    )

    args = parser.parse_args()
    if args.command == "seed-admin":
        seed_admin(args.email, args.password, args.full_name)
    elif args.command == "seed-defaults":
        seed_defaults()
    elif args.command == "tokenize-report-template":
        tokenize_report()
    elif args.command == "seed-report-defaults":
        seed_report_defaults()
    elif args.command == "retention-sweep":
        retention_sweep()


if __name__ == "__main__":
    main()
