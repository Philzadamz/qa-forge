"""API spec parsing and AI-assisted API test-case generation (PRD §7.6.2, §10)."""

import uuid

import httpx
from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile, status
from fastapi.responses import PlainTextResponse, StreamingResponse
from sqlalchemy.orm import Session

from app.core.audit import record as audit_record
from app.core.config import get_settings
from app.core.enums import CaseSection, CaseSource, Priority, TestStatus
from app.core.rbac import require_project_access, require_user
from app.db.session import get_db
from app.models.project import Project
from app.models.test_case import TestCase
from app.models.test_suite import TestSuite
from app.models.user import User
from app.schemas.api_lab import EndpointCatalogue, GenerateApiCasesIn
from app.schemas.suites import CaseOut
from app.services.ai.client import build_llm_client
from app.services.ai.generate_api import generate_api_cases
from app.services.docengine.api_export import build_postman_collection, build_pytest_file
from app.services.execution.api_spec import SpecParseError, parse_curl, parse_openapi, parse_postman
from app.services.suites.numbering import renumber_suite_cases

router = APIRouter(tags=["api-lab"])


def _get_suite_or_404(db: Session, suite_id: uuid.UUID, user: User) -> tuple[TestSuite, Project]:
    suite = db.get(TestSuite, suite_id)
    if suite is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Suite not found")
    project = db.get(Project, suite.project_id)
    if project is None or project.deleted_at is not None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Project not found")
    require_project_access(project, user)
    return suite, project


@router.post("/api-specs/parse", response_model=EndpointCatalogue)
async def parse_api_spec(
    kind: str = Form(...),
    file: UploadFile | None = File(None),
    url: str | None = Form(None),
    curl_text: str | None = Form(None),
    user: User = Depends(require_user),
) -> EndpointCatalogue:
    try:
        if kind == "openapi":
            if url:
                if not url.startswith(("http://", "https://")):
                    raise HTTPException(status.HTTP_400_BAD_REQUEST, "url must be http(s)")
                resp = httpx.get(url, timeout=10.0, follow_redirects=True)
                resp.raise_for_status()
                content = resp.text
            elif file is not None:
                content = (await file.read()).decode("utf-8")
            else:
                raise HTTPException(status.HTTP_400_BAD_REQUEST, "Give either url or file")
            return parse_openapi(content)
        if kind == "postman":
            if file is None:
                raise HTTPException(status.HTTP_400_BAD_REQUEST, "file is required for postman")
            return parse_postman((await file.read()).decode("utf-8"))
        if kind == "curl":
            if not curl_text:
                raise HTTPException(status.HTTP_400_BAD_REQUEST, "curl_text is required for curl")
            return parse_curl(curl_text.splitlines())
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "kind must be openapi, postman, or curl")
    except SpecParseError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
    except httpx.HTTPError as exc:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, f"Could not fetch spec URL: {exc}"
        ) from exc


@router.post("/suites/{suite_id}/generate-api-cases", response_model=list[CaseOut])
def generate_api_cases_endpoint(
    suite_id: uuid.UUID,
    payload: GenerateApiCasesIn,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_user),
) -> list[TestCase]:
    suite, project = _get_suite_or_404(db, suite_id, user)
    if payload.suite_id != suite_id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "suite_id mismatch")

    settings = get_settings()
    client = build_llm_client(settings)
    sort_order = db.query(TestCase).filter(TestCase.suite_id == suite.id).count()

    created: list[TestCase] = []
    for endpoint in payload.endpoints:
        drafts = generate_api_cases(
            client,
            endpoint=endpoint,
            guidance=payload.guidance,
            auth_header_template=payload.auth_header_template,
            model=settings.ai_model_generation,
        )
        for draft in drafts:
            case = TestCase(
                suite_id=suite.id,
                section=CaseSection.FUNCTIONAL,
                case_no=0,
                display_id="",
                feature=draft.feature,
                scenario=draft.scenario,
                steps=draft.steps,
                expected_result=draft.expected_result,
                actual_result="",
                status=TestStatus.NOT_TESTED,
                evidence_group=draft.feature,
                priority=Priority(draft.priority),
                technique=[draft.category],
                source=CaseSource.AI,
                included=True,
                sort_order=sort_order,
                request_plan=draft.request_plan.model_dump(mode="json"),
            )
            db.add(case)
            created.append(case)
            sort_order += 1

    db.flush()
    renumber_suite_cases(db, suite.id, project.id_prefix)
    audit_record(
        db,
        actor_id=user.id,
        action="generate_api_cases",
        entity="test_suite",
        entity_id=str(suite.id),
        diff={"endpoint_count": len(payload.endpoints), "case_count": len(created)},
        request=request,
    )
    db.commit()
    for case in created:
        db.refresh(case)
    return created


def _api_cases_for_export(db: Session, suite_id: uuid.UUID) -> list[TestCase]:
    cases = (
        db.query(TestCase)
        .filter(TestCase.suite_id == suite_id, TestCase.request_plan.is_not(None))
        .order_by(TestCase.sort_order)
        .all()
    )
    if not cases:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "This suite has no API test cases")
    return cases


@router.get("/suites/{suite_id}/export/postman")
def export_postman(
    suite_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(require_user)
) -> StreamingResponse:
    suite, project = _get_suite_or_404(db, suite_id, user)
    cases = _api_cases_for_export(db, suite_id)
    collection = build_postman_collection(
        collection_name=suite.name,
        base_url=project.default_test_url or "",
        cases=[(c.scenario, c.request_plan) for c in cases if c.request_plan is not None],
    )
    import io
    import json

    buf = io.BytesIO(json.dumps(collection, indent=2).encode("utf-8"))
    return StreamingResponse(
        buf,
        media_type="application/json",
        headers={
            "Content-Disposition": f'attachment; filename="{suite.name}.postman_collection.json"'
        },
    )


@router.get("/suites/{suite_id}/export/pytest", response_class=PlainTextResponse)
def export_pytest(
    suite_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(require_user)
) -> str:
    _, project = _get_suite_or_404(db, suite_id, user)
    cases = _api_cases_for_export(db, suite_id)
    return build_pytest_file(
        base_url=project.default_test_url or "",
        cases=[
            (c.display_id, c.scenario, c.request_plan) for c in cases if c.request_plan is not None
        ],
    )
