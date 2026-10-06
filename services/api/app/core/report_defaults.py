"""Default approval roles and exit criteria for the QA Test Completion Report (PRD §14)."""

DEFAULT_EXIT_CRITERIA: list[str] = [
    "All Test cases applicable were executed with screenshots attached",
    "All defects raised were resolved and confirmed as fixed",
    "Completion of User Acceptance Test with the Product owner and other Stakeholders",
]

DEFAULT_APPROVAL_ROLES: list[dict[str, str]] = [
    {"action": "Tested By", "default_name": "", "default_staff_id": ""},
    {"action": "Product Owner Concurrence", "default_name": "", "default_staff_id": ""},
    {"action": "FT Lead, Quality Assurance", "default_name": "", "default_staff_id": ""},
    {
        "action": "Head Quality Assurance (Sterling Bank)",
        "default_name": "",
        "default_staff_id": "",
    },
]
