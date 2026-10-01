"""Ties analyze → generate (per feature) → post-process into one pipeline (PRD §8.2).

Pure and DB-agnostic — the router layer persists results and streams progress over SSE;
this module just runs the pipeline and returns data. That split is what makes it testable
with FakeLLMClient and fixture data (PRD §13.3) without a database at all.
"""

from collections.abc import Callable
from dataclasses import dataclass, field

from app.services.ai.client import LLMClient
from app.services.ai.generate import generate_functional_cases
from app.services.ai.postprocess import (
    CoverageGap,
    check_bva_completeness,
    check_routing_completeness,
    check_traceability,
    find_duplicates,
    normalize_scenario,
)
from app.services.ai.prompts import load_prompt
from app.services.ai.schemas import FunctionalCase, FunctionalCaseList, StoryAnalysis
from app.services.ai.structured import call_structured

GAP_FILL_PROMPT_VERSION = "v1"


@dataclass
class GenerationConfig:
    model_generation: str
    coverage_depth: str = "Standard"
    focus_areas: list[str] = field(default_factory=list)
    style_guide: str = ""
    exemplars: list[dict[str, object]] = field(default_factory=list)
    temperature: float = 0.2
    allow_gap_fill: bool = True


@dataclass
class GenerationOutcome:
    analysis: StoryAnalysis
    cases: list[FunctionalCase]
    duplicate_indexes: list[int]
    gaps: list[CoverageGap]


def generate_cases_for_feature(
    client: LLMClient,
    *,
    feature: str,
    analysis: StoryAnalysis,
    config: GenerationConfig,
    default_scenario_summaries: list[str],
) -> list[FunctionalCase]:
    cases = generate_functional_cases(
        client,
        feature=feature,
        analysis=analysis,
        coverage_depth=config.coverage_depth,
        focus_areas=config.focus_areas,
        style_guide=config.style_guide,
        exemplars=config.exemplars,
        default_scenario_summaries=default_scenario_summaries,
        model=config.model_generation,
        temperature=config.temperature,
    )
    for case in cases:
        case.scenario = normalize_scenario(
            case.scenario, style_guide_has_custom_prefix=bool(config.style_guide.strip())
        )
    return cases


def _gap_fill(
    client: LLMClient, *, analysis: StoryAnalysis, gaps: list[CoverageGap], config: GenerationConfig
) -> list[FunctionalCase]:
    system = load_prompt("generate_functional_cases", GAP_FILL_PROMPT_VERSION)
    gap_lines = "\n".join(f"- ({g.kind}) {g.detail}" for g in gaps)
    user = (
        "The first generation pass left coverage gaps. Generate ADDITIONAL test cases that "
        f"close exactly these gaps — nothing else:\n\n{gap_lines}\n\n"
        f"Story features: {', '.join(analysis.features)}"
    )
    result = call_structured(
        client,
        system=system,
        user=user,
        schema=FunctionalCaseList,
        model=config.model_generation,
        temperature=config.temperature,
    )
    for case in result.cases:
        case.scenario = normalize_scenario(
            case.scenario, style_guide_has_custom_prefix=bool(config.style_guide.strip())
        )
    return result.cases


def run_generation(
    client: LLMClient,
    *,
    analysis: StoryAnalysis,
    config: GenerationConfig,
    default_scenario_summaries: list[str],
    on_feature_done: Callable[[str, list[FunctionalCase]], None] | None = None,
) -> GenerationOutcome:
    all_cases: list[FunctionalCase] = []
    for feature in analysis.features:
        cases = generate_cases_for_feature(
            client,
            feature=feature,
            analysis=analysis,
            config=config,
            default_scenario_summaries=default_scenario_summaries,
        )
        all_cases.extend(cases)
        if on_feature_done:
            on_feature_done(feature, cases)

    gaps = [
        *check_bva_completeness(all_cases, analysis.limits),
        *check_routing_completeness(all_cases, analysis.approval_chains),
    ]

    if gaps and config.allow_gap_fill:
        topup_cases = _gap_fill(client, analysis=analysis, gaps=gaps, config=config)
        all_cases.extend(topup_cases)
        if on_feature_done and topup_cases:
            on_feature_done("__gap_fill__", topup_cases)
        gaps = [
            *check_bva_completeness(all_cases, analysis.limits),
            *check_routing_completeness(all_cases, analysis.approval_chains),
        ]

    gaps.extend(check_traceability(all_cases, analysis.acceptance_criteria))
    duplicate_indexes = find_duplicates(all_cases, default_scenario_summaries)

    return GenerationOutcome(
        analysis=analysis, cases=all_cases, duplicate_indexes=duplicate_indexes, gaps=gaps
    )
