from app.core.enums import DEFAULT_STATUS_PALETTE, UNEXECUTED_STATUSES
from app.core.enums import TestStatus as Status


def test_status_values_match_template_vocabulary() -> None:
    assert [s.value for s in Status] == [
        "Passed",
        "Failed",
        "Not Tested",
        "Suspended",
        "Modification",
        "Blocked",
    ]


def test_palette_covers_every_status() -> None:
    assert set(DEFAULT_STATUS_PALETTE) == set(Status)
    assert DEFAULT_STATUS_PALETTE[Status.PASSED]["fill"] == "00B050"


def test_unexecuted_mapping() -> None:
    assert {Status.NOT_TESTED, Status.BLOCKED} == UNEXECUTED_STATUSES
