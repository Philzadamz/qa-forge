from decimal import Decimal

from app.services.ai.postprocess import (
    check_bva_completeness,
    check_routing_completeness,
    check_traceability,
    find_duplicates,
    normalize_scenario,
    number_steps,
)
from app.services.ai.schemas import AcceptanceCriterion, FunctionalCase, Limit


def _case(
    scenario: str, steps: list[str] | None = None, traces_to: list[str] | None = None, **kw
) -> FunctionalCase:
    return FunctionalCase(
        feature="Petty Cash",
        scenario=scenario,
        steps=steps or ["Do a thing."],
        expected_result="Something happens",
        traces_to=traces_to or [],
        **kw,
    )


def test_normalize_scenario_adds_check_that_prefix() -> None:
    assert normalize_scenario("Users can log in with valid credentials") == (
        "Check that users can log in with valid credentials"
    )


def test_normalize_scenario_leaves_existing_prefix() -> None:
    assert normalize_scenario("Check that login works") == "Check that login works"


def test_normalize_scenario_respects_custom_style_guide() -> None:
    assert normalize_scenario("Verify login works", style_guide_has_custom_prefix=True) == (
        "Verify login works"
    )


def test_number_steps() -> None:
    assert number_steps(["Open the app.", "Log in."]) == ["1. Open the app.", "2. Log in."]


def test_bva_completeness_flags_missing_limit_case() -> None:
    limit = Limit(
        subject="Cash Centre amount",
        value=Decimal(50000),
        unit="NGN",
        comparator="<=",
        applies_to=[],
    )
    cases = [_case("Check that a valid amount is accepted")]
    gaps = check_bva_completeness(cases, [limit])
    assert len(gaps) == 2
    assert {g.kind for g in gaps} == {"missing_bva_at_limit", "missing_bva_over_limit"}


def test_bva_completeness_passes_when_both_present() -> None:
    limit = Limit(
        subject="Cash Centre amount",
        value=Decimal(50000),
        unit="NGN",
        comparator="<=",
        applies_to=[],
    )
    cases = [
        _case("Check that exactly 50000 is accepted", test_data={"amount": "50,000"}),
        _case("Check that 50001 is rejected", test_data={"amount": "50,001"}),
    ]
    gaps = check_bva_completeness(cases, [limit])
    assert gaps == []


def test_routing_completeness_flags_missing_hop() -> None:
    cases = [_case("Check that SSA can approve the request")]
    gaps = check_routing_completeness(cases, [["SSA", "FINOPS Officer", "FINOPS Verifier"]])
    kinds = {g.kind for g in gaps}
    assert "missing_routing_hop" in kinds
    assert "missing_routing_enforcement" in kinds


def test_routing_completeness_passes_when_all_hops_and_enforcement_present() -> None:
    cases = [
        _case("Check that SSA can approve the request"),
        _case("Check that FINOPS Officer can approve after SSA"),
        _case("Check that FINOPS Verifier gives final approval"),
        _case("Check that FINOPS Officer cannot skip the SSA approval step"),
    ]
    gaps = check_routing_completeness(cases, [["SSA", "FINOPS Officer", "FINOPS Verifier"]])
    assert gaps == []


def test_traceability_flags_untraced_ac_and_untraced_case() -> None:
    acs = [AcceptanceCriterion(id="AC-1", text="Login works", feature="Login")]
    cases = [_case("Check that something unrelated happens", traces_to=[])]
    gaps = check_traceability(cases, acs)
    kinds = {g.kind for g in gaps}
    assert "untraced_ac" in kinds
    assert "case_without_trace" in kinds


def test_traceability_passes_when_linked() -> None:
    acs = [AcceptanceCriterion(id="AC-1", text="Login works", feature="Login")]
    cases = [_case("Check that login works", traces_to=["AC-1"])]
    assert check_traceability(cases, acs) == []


def test_find_duplicates_against_default_scenarios() -> None:
    cases = [
        _case("Check that a valid login succeeds"),
        _case("Check that the petty cash request routes to SSA"),
    ]
    duplicates = find_duplicates(cases, default_scenarios=["Check that a valid login succeeds."])
    assert duplicates == [0]


def test_find_duplicates_within_generated_set() -> None:
    cases = [
        _case("Check that the request routes to SSA for approval"),
        _case("Check that the request routes to SSA for approval"),
    ]
    duplicates = find_duplicates(cases, default_scenarios=[])
    assert duplicates == [1]
