"""Minimal sample data used to validate/preview an uploaded template (ADM-TM-3/4).

Not test fixtures in the pytest sense — this is production code the template-upload
endpoint runs to prove a newly uploaded template actually renders before it can be
activated, so a broken template fails loudly at upload time rather than at suite-export
time weeks later.
"""

from app.core.enums import TestStatus
from app.services.docengine.models import (
    ApprovalRow,
    BugsSummary,
    ExceptionRow,
    ExportCase,
    FeatureRow,
    ReportData,
    ResultAnalysis,
    SuiteExportData,
    SuiteHeader,
)


def sample_suite_export_data() -> SuiteExportData:
    header = SuiteHeader(
        project_name_line="SAMPLE: Template Preview",
        user_group_dept="Quality Assurance",
        solution_provider="QA Forge",
        developers="Sample Developer",
        test_done_by="Sample Tester",
        test_reviewed_by="Sample Reviewer",
        start_date="01/01/2026",
        end_date="02/01/2026",
        test_description="Sample suite used to validate a template.",
        endpoint_url="http://example.com",
    )
    default_cases = [
        ExportCase(
            case_no="Sample_001",
            feature="Login",
            scenario="Check that valid credentials grant access",
            steps=["Open the app.", "Log in with valid credentials."],
            expected_result="User is logged in",
            actual_result="As expected",
            status=TestStatus.PASSED,
        )
    ]
    functional_cases = [
        ExportCase(
            case_no="Sample_002",
            feature="Sample Feature",
            scenario="Check that the sample feature works",
            steps=["Do the thing."],
            expected_result="The thing happens",
            actual_result="",
            status=TestStatus.NOT_TESTED,
        )
    ]
    return SuiteExportData(
        header=header, default_cases=default_cases, functional_cases=functional_cases
    )


def sample_report_data() -> ReportData:
    return ReportData(
        product_name="Sample Product",
        pr_links=["https://example.com/pr/1"],
        version_numbers=["abc123"],
        test_url="http://example.com",
        workitem_url="https://example.com/workitem/1",
        jira_link="https://example.com/browse/ABC-1",
        general_description="Sample report used to validate a template.",
        certified=True,
        features=[FeatureRow(name="Sample Feature", description="Sample description")],
        exit_criteria=["All cases executed"],
        result_analysis=ResultAnalysis(
            test_cycles=1, total=1, passed=1, failed=0, unexecuted=0, suspended=0, modification=0
        ),
        automation_ratio="0:100",
        bugs=BugsSummary(),
        exceptions=[
            ExceptionRow(
                case_id="N/A", status_type="N/A", description="N/A", severity="N/A", risk="N/A"
            )
        ],
        comments=["Sample comment."],
        approvals=[ApprovalRow(action="Tested By", name="Sample Tester", staff_id="000")],
        classification_label="Public",
    )
