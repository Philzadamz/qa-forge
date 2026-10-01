"""Deterministic report numbers (PRD §3.2(d), USR-RP-3).

These are computed from exactly the same case set the xlsx export uses (included cases only,
PRD §3.1's "Result Analysis" semantics) — by construction, not by a separate reconciliation
step, the report's Result Analysis always equals the xlsx Result Analysis for the same suite
and cycle. Only the narrative (feature descriptions, exceptions' wording, comments) comes from
the AI; the numbers never do.
"""

from dataclasses import dataclass

from app.core.enums import BugStatus, CaseSection, ExecutionMode, TestStatus
from app.models.bug import Bug
from app.models.test_case import TestCase


@dataclass
class ResultCounts:
    test_cycles: int
    total: int
    passed: int
    failed: int
    unexecuted: int
    suspended: int
    modification: int


@dataclass
class BugCounts:
    raised: int
    fixed_retested: int
    open: int


def compute_result_counts(cases: list[TestCase], test_cycle: int) -> ResultCounts:
    included = [c for c in cases if c.included]
    return ResultCounts(
        test_cycles=test_cycle,
        total=len(included),
        passed=sum(1 for c in included if c.status == TestStatus.PASSED),
        failed=sum(1 for c in included if c.status == TestStatus.FAILED),
        unexecuted=sum(
            1 for c in included if c.status in (TestStatus.NOT_TESTED, TestStatus.BLOCKED)
        ),
        suspended=sum(1 for c in included if c.status == TestStatus.SUSPENDED),
        modification=sum(1 for c in included if c.status == TestStatus.MODIFICATION),
    )


def compute_automation_ratio(cases: list[TestCase]) -> str:
    included = [c for c in cases if c.included]
    executed = [c for c in included if c.status != TestStatus.NOT_TESTED]
    if not executed:
        return "0:100"
    automated = sum(1 for c in executed if c.execution_mode == ExecutionMode.AUTOMATED)
    automated_pct = round(automated / len(executed) * 100)
    return f"{automated_pct}:{100 - automated_pct}"


def compute_bug_counts(bugs: list[Bug]) -> BugCounts:
    return BugCounts(
        raised=len(bugs),
        fixed_retested=sum(
            1 for b in bugs if b.status in (BugStatus.FIXED, BugStatus.RETESTED, BugStatus.CLOSED)
        ),
        open=sum(1 for b in bugs if b.status == BugStatus.OPEN),
    )


def suggest_certified(result: ResultCounts, bug_counts: BugCounts) -> bool:
    """PRD §3.2(2): suggested, not final — the user must confirm. All executed cases passed
    (nothing failed/suspended/needs modification) and no bugs remain open."""
    return (
        result.failed == 0
        and result.suspended == 0
        and result.modification == 0
        and bug_counts.open == 0
    )


def functional_features(cases: list[TestCase]) -> list[str]:
    seen: list[str] = []
    for c in cases:
        if c.section == CaseSection.FUNCTIONAL and c.included and c.feature not in seen:
            seen.append(c.feature)
    return seen


def feature_is_functional(cases: list[TestCase], feature: str) -> bool:
    feature_cases = [c for c in cases if c.feature == feature and c.included]
    return bool(feature_cases) and all(c.status == TestStatus.PASSED for c in feature_cases)
