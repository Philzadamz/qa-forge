"""Post-generation checks (PRD §8.2 step 4): USR-GEN-5 (boundary value completeness),
USR-GEN-6 (approval-chain completeness), traceability, wording normalization, and
duplicate detection against the type's default scenarios.
"""

import re
from dataclasses import dataclass
from decimal import Decimal
from difflib import SequenceMatcher

from app.services.ai.schemas import AcceptanceCriterion, FunctionalCase, Limit

DUPLICATE_SIMILARITY_THRESHOLD = 0.9


@dataclass
class CoverageGap:
    kind: str
    detail: str


def normalize_scenario(text: str, *, style_guide_has_custom_prefix: bool = False) -> str:
    """Scenario starts with 'Check that…' unless the style guide says otherwise (PRD §8.2)."""
    text = text.strip()
    if not text or style_guide_has_custom_prefix:
        return text
    if text.lower().startswith("check that"):
        return text
    first_char = text[0].lower() + text[1:] if text else text
    return f"Check that {first_char}"


def number_steps(steps: list[str]) -> list[str]:
    """Render steps as '1. ...', '2. ...' for display — storage stays unnumbered."""
    return [f"{i}. {s}" for i, s in enumerate(steps, start=1)]


def _limit_mentions_value(case: FunctionalCase, value: Decimal) -> bool:
    haystack = " ".join([case.scenario, *case.steps, *case.test_data.values()])
    # Match the value with or without thousands separators (150000 vs 150,000).
    plain = str(value).rstrip("0").rstrip(".") if "." in str(value) else str(value)
    with_commas = f"{value:,.0f}" if value == value.to_integral_value() else str(value)
    return plain in haystack.replace(",", "") or with_commas in haystack


def check_bva_completeness(cases: list[FunctionalCase], limits: list[Limit]) -> list[CoverageGap]:
    """USR-GEN-5: for every limit, at least one case at the limit and one at limit+1 unit."""
    gaps: list[CoverageGap] = []
    for limit in limits:
        at_limit = any(_limit_mentions_value(c, limit.value) for c in cases)
        over_limit = any(_limit_mentions_value(c, limit.value + 1) for c in cases)
        if not at_limit:
            gaps.append(
                CoverageGap(
                    kind="missing_bva_at_limit",
                    detail=f"No case tests {limit.subject} at exactly {limit.value} {limit.unit}",
                )
            )
        if not over_limit:
            gaps.append(
                CoverageGap(
                    kind="missing_bva_over_limit",
                    detail=(
                        f"No case tests {limit.subject} at {limit.value + 1} {limit.unit} "
                        "(one unit past the limit)"
                    ),
                )
            )
    return gaps


def check_routing_completeness(
    cases: list[FunctionalCase], approval_chains: list[list[str]]
) -> list[CoverageGap]:
    """USR-GEN-6: every hop in every approval chain should have at least one case mentioning
    both that role and an adjacent one (so the hop itself, not just the role in isolation, is
    covered)."""
    gaps: list[CoverageGap] = []
    haystacks = [" ".join([c.scenario, *c.steps]).lower() for c in cases]
    for chain in approval_chains:
        for role in chain:
            if not any(role.lower() in h for h in haystacks):
                gaps.append(
                    CoverageGap(
                        kind="missing_routing_hop",
                        detail=f"No case mentions approval role '{role}' from chain {chain}",
                    )
                )
        if len(chain) > 1:
            enforcement_terms = ("skip", "bypass", "out of order", "without")
            if not any(any(t in h for t in enforcement_terms) for h in haystacks):
                gaps.append(
                    CoverageGap(
                        kind="missing_routing_enforcement",
                        detail=f"No case verifies the chain {chain} is enforced (can't be skipped)",
                    )
                )
    return gaps


def check_traceability(
    cases: list[FunctionalCase], acceptance_criteria: list[AcceptanceCriterion]
) -> list[CoverageGap]:
    gaps: list[CoverageGap] = []
    traced_ids = {ac_id for c in cases for ac_id in c.traces_to}
    for ac in acceptance_criteria:
        if ac.id not in traced_ids:
            gaps.append(
                CoverageGap(
                    kind="untraced_ac", detail=f"{ac.id} ({ac.text}) has no case tracing to it"
                )
            )
    for i, case in enumerate(cases):
        if not case.traces_to:
            gaps.append(
                CoverageGap(
                    kind="case_without_trace",
                    detail=f"Case {i} ('{case.scenario}') traces to nothing",
                )
            )
    return gaps


def _normalized(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip().lower())


def find_duplicates(
    cases: list[FunctionalCase],
    default_scenarios: list[str],
    *,
    threshold: float = DUPLICATE_SIMILARITY_THRESHOLD,
) -> list[int]:
    """Indexes into `cases` that semantically duplicate a default scenario or an earlier
    case (simple normalized-text similarity, PRD §8.2 — no embedding model available)."""
    normalized_defaults = [_normalized(s) for s in default_scenarios]
    seen: list[str] = []
    duplicate_indexes: list[int] = []
    for i, case in enumerate(cases):
        candidate = _normalized(case.scenario)
        pool = normalized_defaults + seen
        if any(SequenceMatcher(None, candidate, other).ratio() >= threshold for other in pool):
            duplicate_indexes.append(i)
        else:
            seen.append(candidate)
    return duplicate_indexes
