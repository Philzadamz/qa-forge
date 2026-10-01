"""Continuous test-case numbering across a suite (USR-GEN-2/3).

IDs are `<prefix>_<NNN>`, continuous across the default and functional sections, counting
only included cases. Excluded cases carry no display ID so renumbering (e.g. after toggling
Include on a default) is just "run this again", not manual bookkeeping.
"""

import uuid

from sqlalchemy.orm import Session

from app.core.enums import CaseSection
from app.models.test_case import TestCase


def renumber_suite_cases(db: Session, suite_id: uuid.UUID, id_prefix: str) -> None:
    cases = db.query(TestCase).filter(TestCase.suite_id == suite_id).all()
    cases.sort(key=lambda c: (0 if c.section == CaseSection.DEFAULT else 1, c.sort_order))

    n = 0
    for case in cases:
        if case.included:
            n += 1
            case.case_no = n
            case.display_id = f"{id_prefix}_{n:03d}"
        else:
            case.case_no = 0
            case.display_id = ""
