import uuid

from app.core.enums import BugStatus, CaseSection, CaseSource, ExecutionMode, Severity, TestStatus
from app.models.bug import Bug
from app.models.test_case import TestCase
from app.services.reports.builder import (
    compute_automation_ratio,
    compute_bug_counts,
    compute_result_counts,
    feature_is_functional,
    functional_features,
    suggest_certified,
)


def _case(status: TestStatus, included: bool = True, feature: str = "Login", **kw) -> TestCase:
    return TestCase(
        suite_id=uuid.uuid4(),
        section=kw.pop("section", CaseSection.FUNCTIONAL),
        case_no=1,
        display_id="X_001",
        feature=feature,
        scenario="Check something",
        steps=["Step"],
        expected_result="Expected",
        actual_result="",
        status=status,
        source=CaseSource.MANUAL,
        included=included,
        **kw,
    )


def test_compute_result_counts_only_counts_included_cases() -> None:
    cases = [
        _case(TestStatus.PASSED),
        _case(TestStatus.FAILED),
        _case(TestStatus.PASSED, included=False),  # excluded — must not count
        _case(TestStatus.NOT_TESTED),
        _case(TestStatus.BLOCKED),
        _case(TestStatus.SUSPENDED),
        _case(TestStatus.MODIFICATION),
    ]
    result = compute_result_counts(cases, test_cycle=2)
    assert result.test_cycles == 2
    assert result.total == 6  # one excluded
    assert result.passed == 1
    assert result.failed == 1
    assert result.unexecuted == 2  # not tested + blocked
    assert result.suspended == 1
    assert result.modification == 1


def test_compute_automation_ratio_counts_only_executed_cases() -> None:
    cases = [
        _case(TestStatus.PASSED, execution_mode=ExecutionMode.AUTOMATED),
        _case(TestStatus.PASSED, execution_mode=ExecutionMode.MANUAL),
        _case(TestStatus.NOT_TESTED, execution_mode=None),  # not executed — excluded from ratio
    ]
    assert compute_automation_ratio(cases) == "50:50"


def test_compute_automation_ratio_defaults_to_0_100_when_nothing_executed() -> None:
    cases = [_case(TestStatus.NOT_TESTED)]
    assert compute_automation_ratio(cases) == "0:100"


def test_compute_bug_counts() -> None:
    bugs = [
        Bug(suite_id=uuid.uuid4(), title="A", status=BugStatus.OPEN, severity=Severity.HIGH),
        Bug(suite_id=uuid.uuid4(), title="B", status=BugStatus.FIXED, severity=Severity.LOW),
        Bug(suite_id=uuid.uuid4(), title="C", status=BugStatus.RETESTED, severity=Severity.LOW),
        Bug(suite_id=uuid.uuid4(), title="D", status=BugStatus.CLOSED, severity=Severity.LOW),
    ]
    counts = compute_bug_counts(bugs)
    assert counts.raised == 4
    assert counts.fixed_retested == 3
    assert counts.open == 1


def test_suggest_certified_true_when_clean() -> None:
    cases = [_case(TestStatus.PASSED), _case(TestStatus.PASSED)]
    result = compute_result_counts(cases, test_cycle=1)
    assert suggest_certified(result, compute_bug_counts([])) is True


def test_suggest_certified_false_with_open_bug_even_if_all_passed() -> None:
    cases = [_case(TestStatus.PASSED)]
    result = compute_result_counts(cases, test_cycle=1)
    bugs = [Bug(suite_id=uuid.uuid4(), title="A", status=BugStatus.OPEN, severity=Severity.LOW)]
    assert suggest_certified(result, compute_bug_counts(bugs)) is False


def test_suggest_certified_false_with_any_failure() -> None:
    cases = [_case(TestStatus.PASSED), _case(TestStatus.FAILED)]
    result = compute_result_counts(cases, test_cycle=1)
    assert suggest_certified(result, compute_bug_counts([])) is False


def test_functional_features_excludes_defaults_and_excluded_cases() -> None:
    cases = [
        _case(TestStatus.PASSED, feature="Login", section=CaseSection.DEFAULT),
        _case(TestStatus.PASSED, feature="Petty Cash", section=CaseSection.FUNCTIONAL),
        _case(
            TestStatus.PASSED, feature="Approvals", section=CaseSection.FUNCTIONAL, included=False
        ),
        _case(TestStatus.FAILED, feature="Petty Cash", section=CaseSection.FUNCTIONAL),
    ]
    assert functional_features(cases) == ["Petty Cash"]


def test_feature_is_functional_true_only_when_all_cases_passed() -> None:
    cases = [
        _case(TestStatus.PASSED, feature="Petty Cash"),
        _case(TestStatus.PASSED, feature="Petty Cash"),
    ]
    assert feature_is_functional(cases, "Petty Cash") is True

    cases_with_failure = [*cases, _case(TestStatus.FAILED, feature="Petty Cash")]
    assert feature_is_functional(cases_with_failure, "Petty Cash") is False
