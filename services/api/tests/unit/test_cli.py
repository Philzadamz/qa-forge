from pathlib import Path

from app.cli import SEED_TYPE_NAME, seed_admin, seed_defaults
from app.db.session import get_sessionmaker
from app.models.test_case_type import DefaultTestCase
from app.models.test_case_type import TestCaseType as TestCaseTypeModel
from app.models.user import User

REAL_TEMPLATE = (
    Path(__file__).resolve().parents[4] / "templates" / "source" / "QA_Test_Cases_Template.xlsx"
)


def test_seed_admin_creates_admin_user() -> None:
    seed_admin("admin@example.com", "a-strong-password")

    session = get_sessionmaker()()
    try:
        user = session.query(User).filter(User.email == "admin@example.com").one()
        assert user.role == "admin"
    finally:
        session.close()


def test_seed_admin_is_idempotent() -> None:
    seed_admin("admin@example.com", "a-strong-password")
    seed_admin("admin@example.com", "a-different-password")

    session = get_sessionmaker()()
    try:
        count = session.query(User).filter(User.email == "admin@example.com").count()
        assert count == 1
    finally:
        session.close()


def test_seed_defaults_skips_gracefully_when_template_missing(tmp_path: Path) -> None:
    seed_defaults(template_path=tmp_path / "does-not-exist.xlsx")

    session = get_sessionmaker()()
    try:
        assert session.query(TestCaseTypeModel).count() == 0
    finally:
        session.close()


def test_seed_defaults_imports_from_real_template_when_present() -> None:
    if not REAL_TEMPLATE.exists():
        return  # covered by the skip test above; this machine just doesn't have it.

    seed_defaults(template_path=REAL_TEMPLATE)

    session = get_sessionmaker()()
    try:
        type_obj = (
            session.query(TestCaseTypeModel).filter(TestCaseTypeModel.name == SEED_TYPE_NAME).one()
        )
        count = (
            session.query(DefaultTestCase).filter(DefaultTestCase.type_id == type_obj.id).count()
        )
        assert count == 31
    finally:
        session.close()

    # Re-running must not duplicate the type.
    seed_defaults(template_path=REAL_TEMPLATE)
    session = get_sessionmaker()()
    try:
        assert (
            session.query(TestCaseTypeModel)
            .filter(TestCaseTypeModel.name == SEED_TYPE_NAME)
            .count()
            == 1
        )
    finally:
        session.close()
