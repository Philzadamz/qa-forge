import json

from app.services.ai.client import FakeLLMClient
from app.services.ai.orchestrator import GenerationConfig, run_generation
from app.services.ai.schemas import AcceptanceCriterion, Limit, StoryAnalysis

ANALYSIS = StoryAnalysis(
    features=["Login", "Petty Cash"],
    actors=["Cash Centre initiator", "SSA", "FINOPS Officer"],
    acceptance_criteria=[
        AcceptanceCriterion(id="AC-1", text="Login works", feature="Login"),
        AcceptanceCriterion(id="AC-2", text="Amount is capped", feature="Petty Cash"),
    ],
    business_rules=[],
    limits=[
        Limit(subject="Cash Centre amount", value=50000, unit="NGN", comparator="<=", applies_to=[])
    ],
    states=["Pending", "Approved"],
    approval_chains=[["SSA", "FINOPS Officer"]],
    validations=[],
    integrations=[],
    out_of_scope=[],
    questions=[],
)


def _cases_json(cases: list[dict[str, object]]) -> str:
    return json.dumps({"cases": cases})


def test_every_case_has_required_fields_nonempty() -> None:
    # USR-GEN-4
    login_cases = _cases_json(
        [
            {
                "feature": "Login",
                "scenario": "Check that valid credentials grant access",
                "steps": ["Open the app.", "Log in."],
                "expected_result": "User is logged in",
                "traces_to": ["AC-1"],
            }
        ]
    )
    petty_cash_cases = _cases_json(
        [
            {
                "feature": "Petty Cash",
                "scenario": "Check that exactly 50000 is accepted",
                "steps": ["Enter 50,000."],
                "expected_result": "Request is accepted",
                "traces_to": ["AC-2"],
                "test_data": {"amount": "50,000"},
            },
            {
                "feature": "Petty Cash",
                "scenario": "Check that 50001 is rejected",
                "steps": ["Enter 50,001."],
                "expected_result": "Request is rejected",
                "traces_to": ["AC-2"],
                "test_data": {"amount": "50,001"},
            },
            {
                "feature": "Petty Cash",
                "scenario": "Check that SSA approves and FINOPS Officer gives final approval",
                "steps": ["As SSA, approve.", "As FINOPS Officer, approve."],
                "expected_result": "Request is fully approved",
                "traces_to": ["AC-2"],
            },
            {
                "feature": "Petty Cash",
                "scenario": "Check that FINOPS Officer cannot skip the SSA approval step",
                "steps": ["As FINOPS Officer, attempt to approve before SSA has approved."],
                "expected_result": "System rejects the out of order approval attempt",
                "traces_to": ["AC-2"],
            },
        ]
    )
    client = FakeLLMClient(responses=[login_cases, petty_cash_cases])
    config = GenerationConfig(model_generation="fake-model", allow_gap_fill=True)

    outcome = run_generation(
        client, analysis=ANALYSIS, config=config, default_scenario_summaries=[]
    )

    assert len(outcome.cases) == 5
    for case in outcome.cases:
        assert case.feature
        assert case.scenario
        assert case.steps
        assert case.expected_result
    # No gaps — BVA and routing are both fully covered, no gap-fill call should have fired.
    assert len(client.calls) == 2


def test_gap_fill_call_fires_when_coverage_is_incomplete() -> None:
    login_cases = _cases_json(
        [
            {
                "feature": "Login",
                "scenario": "Check that valid credentials grant access",
                "steps": ["Log in."],
                "expected_result": "User is logged in",
                "traces_to": ["AC-1"],
            }
        ]
    )
    # Petty Cash cases say nothing about the limit or the approval chain — gaps expected.
    petty_cash_cases = _cases_json(
        [
            {
                "feature": "Petty Cash",
                "scenario": "Check that a request can be created",
                "steps": ["Create a request."],
                "expected_result": "Request is created",
                "traces_to": ["AC-2"],
            }
        ]
    )
    gap_fill_cases = _cases_json(
        [
            {
                "feature": "Petty Cash",
                "scenario": "Check that exactly 50000 is accepted",
                "steps": ["Enter 50,000."],
                "expected_result": "Accepted",
                "traces_to": ["AC-2"],
                "test_data": {"amount": "50,000"},
            },
            {
                "feature": "Petty Cash",
                "scenario": "Check that 50001 is rejected",
                "steps": ["Enter 50,001."],
                "expected_result": "Rejected",
                "traces_to": ["AC-2"],
                "test_data": {"amount": "50,001"},
            },
        ]
    )
    client = FakeLLMClient(responses=[login_cases, petty_cash_cases, gap_fill_cases])
    config = GenerationConfig(model_generation="fake-model", allow_gap_fill=True)

    outcome = run_generation(
        client, analysis=ANALYSIS, config=config, default_scenario_summaries=[]
    )

    assert len(client.calls) == 3  # 2 feature calls + 1 gap-fill
    assert len(outcome.cases) == 4  # 1 login + 1 petty cash + 2 gap-fill
    # Routing gap for the approval chain remains (gap-fill didn't address it) — still reported.
    assert any(g.kind == "missing_routing_hop" for g in outcome.gaps)


def test_gap_fill_disabled_skips_the_extra_call() -> None:
    login_cases = _cases_json(
        [
            {
                "feature": "Login",
                "scenario": "Check login",
                "steps": ["Log in."],
                "expected_result": "Logged in",
                "traces_to": ["AC-1"],
            }
        ]
    )
    petty_cash_cases = _cases_json(
        [
            {
                "feature": "Petty Cash",
                "scenario": "Check that a request can be created",
                "steps": ["Create a request."],
                "expected_result": "Created",
                "traces_to": ["AC-2"],
            }
        ]
    )
    client = FakeLLMClient(responses=[login_cases, petty_cash_cases])
    config = GenerationConfig(model_generation="fake-model", allow_gap_fill=False)

    outcome = run_generation(
        client, analysis=ANALYSIS, config=config, default_scenario_summaries=[]
    )

    assert len(client.calls) == 2
    assert len(outcome.gaps) > 0


def test_duplicate_default_scenario_is_flagged() -> None:
    login_cases = _cases_json(
        [
            {
                "feature": "Login",
                "scenario": "Check that a valid login succeeds",
                "steps": ["Log in."],
                "expected_result": "Logged in",
                "traces_to": ["AC-1"],
            }
        ]
    )
    petty_cash_cases = _cases_json(
        [
            {
                "feature": "Petty Cash",
                "scenario": "Check that exactly 50000 is accepted",
                "steps": ["Enter 50,000."],
                "expected_result": "Accepted",
                "traces_to": ["AC-2"],
                "test_data": {"amount": "50,000"},
            },
            {
                "feature": "Petty Cash",
                "scenario": "Check that 50001 is rejected",
                "steps": ["Enter 50,001."],
                "expected_result": "Rejected",
                "traces_to": ["AC-2"],
                "test_data": {"amount": "50,001"},
            },
            {
                "feature": "Petty Cash",
                "scenario": "Check that SSA approves and FINOPS Officer gives final approval",
                "steps": ["As SSA, approve.", "As FINOPS Officer, approve."],
                "expected_result": "Fully approved",
                "traces_to": ["AC-2"],
            },
        ]
    )
    client = FakeLLMClient(responses=[login_cases, petty_cash_cases])
    config = GenerationConfig(model_generation="fake-model", allow_gap_fill=False)

    outcome = run_generation(
        client,
        analysis=ANALYSIS,
        config=config,
        default_scenario_summaries=["Check that a valid login succeeds."],
    )

    assert outcome.duplicate_indexes == [0]
