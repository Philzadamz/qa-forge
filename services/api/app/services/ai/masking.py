"""PII/secret masking, run on every piece of text before it reaches an LLM (PRD §8.1, CLAUDE.md).

Masking is stateless and one-way for v1: callers don't need to unmask AI output (generated
test cases describe scenarios generically — "a Cash Centre initiator", not a real account
number), so there's no reversal map to manage or leak. Each masked run is logged with a
count per category for the audit trail, never the original values.
"""

import re
from collections.abc import Callable
from dataclasses import dataclass, field

_NUBAN_RE = re.compile(r"(?<!\d)\d{10}(?!\d)")
_BVN_NIN_RE = re.compile(r"(?<!\d)\d{11}(?!\d)")
_CARD_RE = re.compile(r"(?<!\d)(?:\d[ -]?){13,19}(?!\d)")
_EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")
_PHONE_RE = re.compile(r"(?<!\d)(?:\+?234|0)[789]\d{9}(?!\d)")


def _luhn_valid(digits: str) -> bool:
    cleaned = re.sub(r"[ -]", "", digits)
    if not cleaned.isdigit():
        return False
    total = 0
    for i, ch in enumerate(reversed(cleaned)):
        d = int(ch)
        if i % 2 == 1:
            d *= 2
            if d > 9:
                d -= 9
        total += d
    return total % 10 == 0


@dataclass
class MaskResult:
    text: str
    counts: dict[str, int] = field(default_factory=dict)

    @property
    def total_masked(self) -> int:
        return sum(self.counts.values())


def mask_text(text: str, *, mask_email: bool = True, mask_phone: bool = True) -> MaskResult:
    counts: dict[str, int] = {}

    def _replace(
        pattern: re.Pattern[str],
        label: str,
        text_in: str,
        validator: Callable[[str], bool] | None = None,
    ) -> str:
        n = 0

        def _sub(m: re.Match[str]) -> str:
            nonlocal n
            if validator and not validator(m.group(0)):
                return m.group(0)
            n += 1
            return f"[MASKED_{label}_{n}]"

        result = pattern.sub(_sub, text_in)
        if n:
            counts[label] = counts.get(label, 0) + n
        return result

    # Order matters: a Nigerian phone number and a BVN/NIN are both 11 digits, so the more
    # specific phone pattern (fixed prefix) must run before the generic 11-digit one claims it.
    masked = text
    masked = _replace(_CARD_RE, "CARD", masked, validator=_luhn_valid)
    if mask_phone:
        masked = _replace(_PHONE_RE, "PHONE", masked)
    masked = _replace(_BVN_NIN_RE, "BVN_NIN", masked)
    masked = _replace(_NUBAN_RE, "ACCOUNT", masked)
    if mask_email:
        masked = _replace(_EMAIL_RE, "EMAIL", masked)

    return MaskResult(text=masked, counts=counts)


def mask_secrets(text: str, secret_values: list[str]) -> MaskResult:
    """Mask any known secret value (from the `secrets` table) found verbatim in text."""
    masked = text
    n = 0
    for value in secret_values:
        if value and value in masked:
            n += 1
            masked = masked.replace(value, f"[MASKED_SECRET_{n}]")
    return MaskResult(text=masked, counts={"SECRET": n} if n else {})
