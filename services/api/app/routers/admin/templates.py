"""Admin: template management (ADM-TM-1..4).

xlsx templates are used as-is (their structure already matches Appendix B). docx templates
are auto-tokenized on upload (ADM-TM-2's "automated tokeniser for the known template"). Both
kinds are validated immediately by actually rendering them with small fixture data — a
template can't be activated if that render fails, so a broken template is caught at upload
time rather than the first time someone tries to export a real suite or report.
"""

import tempfile
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.core.audit import record as audit_record
from app.core.config import get_settings
from app.core.enums import TemplateKind, TemplateStatus
from app.core.rbac import require_admin
from app.db.session import get_db
from app.models.template import Template
from app.models.user import User
from app.schemas.admin import TemplateOut
from app.services.docengine.docx_tokenizer import tokenize_report_template
from app.services.docengine.docx_writer import write_report_docx
from app.services.docengine.fixtures import sample_report_data, sample_suite_export_data
from app.services.docengine.xlsx_writer import write_test_cases_xlsx
from app.services.storage import build_storage

router = APIRouter(prefix="/templates", tags=["admin:templates"])

MAX_UPLOAD_BYTES = 20 * 1024 * 1024
_XLSX_CONTENT_TYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
_DOCX_CONTENT_TYPE = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
CONTENT_TYPES = {
    TemplateKind.XLSX_TEST_CASES: _XLSX_CONTENT_TYPE,
    TemplateKind.DOCX_REPORT: _DOCX_CONTENT_TYPE,
}


def _get_template_or_404(db: Session, template_id: uuid.UUID) -> Template:
    obj = db.get(Template, template_id)
    if obj is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Template not found")
    return obj


def _validate_and_store(
    template_id: uuid.UUID, kind: TemplateKind, raw: bytes
) -> tuple[str, str | None, str | None]:
    """Stores the raw upload, renders it against fixture data, and returns
    (source_key, rendered_key, validation_error). rendered_key is None for xlsx (the source
    is used as-is) or points at the freshly tokenized docx working copy, only stored once
    validation succeeds."""
    storage = build_storage(get_settings())
    extension = "xlsx" if kind == TemplateKind.XLSX_TEST_CASES else "docx"
    source_key = f"templates/{template_id}/source.{extension}"
    storage.put(source_key, raw)

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        source_path = tmp_path / f"source.{extension}"
        source_path.write_bytes(raw)

        if kind == TemplateKind.XLSX_TEST_CASES:
            try:
                write_test_cases_xlsx(
                    source_path, sample_suite_export_data(), tmp_path / "out.xlsx"
                )
            except Exception as exc:
                return source_key, None, str(exc)
            return source_key, None, None

        tokenized_path = tmp_path / "tokenized.docx"
        try:
            tokenize_report_template(source_path, tokenized_path)
            write_report_docx(tokenized_path, sample_report_data(), tmp_path / "out.docx")
        except Exception as exc:
            return source_key, None, str(exc)

        rendered_key = f"templates/{template_id}/tokenized.docx"
        storage.put(rendered_key, tokenized_path.read_bytes())
        return source_key, rendered_key, None


@router.get("", response_model=list[TemplateOut])
def list_templates(
    kind: TemplateKind | None = None,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> list[Template]:
    query = db.query(Template)
    if kind:
        query = query.filter(Template.kind == kind)
    return list(query.order_by(Template.kind, Template.name, Template.version.desc()).all())


@router.post("", response_model=TemplateOut, status_code=status.HTTP_201_CREATED)
async def upload_template(
    request: Request,
    file: UploadFile,
    kind: TemplateKind,
    name: str,
    type_id: uuid.UUID | None = None,
    notes: str | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(require_admin),
) -> Template:
    raw = await file.read()
    if len(raw) > MAX_UPLOAD_BYTES:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "File is too large (max 20 MB)")

    existing_versions = (
        db.query(Template).filter(Template.kind == kind, Template.name == name).count()
    )

    obj = Template(
        kind=kind,
        name=name,
        version=existing_versions + 1,
        file_key="",
        type_id=type_id,
        status=TemplateStatus.DRAFT,
        uploaded_by=user.id,
        notes=notes,
    )
    db.add(obj)
    db.flush()  # need obj.id for the storage key

    source_key, rendered_key, validation_error = _validate_and_store(obj.id, kind, raw)
    obj.file_key = source_key
    obj.rendered_key = rendered_key
    obj.validation_error = validation_error

    audit_record(
        db,
        actor_id=user.id,
        action="upload",
        entity="template",
        entity_id=str(obj.id),
        diff={"kind": kind.value, "valid": validation_error is None},
        request=request,
    )
    db.commit()
    db.refresh(obj)
    return obj


@router.post("/{template_id}/activate", response_model=TemplateOut)
def activate_template(
    template_id: uuid.UUID,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_admin),
) -> Template:
    obj = _get_template_or_404(db, template_id)
    if obj.validation_error:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"Cannot activate an invalid template: {obj.validation_error}",
        )

    db.query(Template).filter(
        Template.kind == obj.kind, Template.type_id == obj.type_id, Template.id != obj.id
    ).update({"is_default": False})
    obj.is_default = True
    obj.status = TemplateStatus.ACTIVE

    audit_record(
        db,
        actor_id=user.id,
        action="activate",
        entity="template",
        entity_id=str(obj.id),
        request=request,
    )
    db.commit()
    db.refresh(obj)
    return obj


@router.post("/{template_id}/archive", response_model=TemplateOut)
def archive_template(
    template_id: uuid.UUID,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_admin),
) -> Template:
    obj = _get_template_or_404(db, template_id)
    obj.status = TemplateStatus.ARCHIVED
    obj.is_default = False
    audit_record(
        db,
        actor_id=user.id,
        action="archive",
        entity="template",
        entity_id=str(obj.id),
        request=request,
    )
    db.commit()
    db.refresh(obj)
    return obj


@router.get("/{template_id}/preview")
def preview_template(
    template_id: uuid.UUID, db: Session = Depends(get_db), _: User = Depends(require_admin)
) -> StreamingResponse:
    """Renders the template against small fixture data so the admin can eyeball the result.

    A true PDF preview needs LibreOffice headless (PRD ADM-TM-3); without it installed, this
    returns the native xlsx/docx file instead — still openable, just not a universal preview.
    """
    obj = _get_template_or_404(db, template_id)
    if obj.validation_error:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, f"Template is invalid: {obj.validation_error}"
        )

    storage = build_storage(get_settings())
    key = obj.rendered_key or obj.file_key
    raw = storage.get(key)

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        if obj.kind == TemplateKind.XLSX_TEST_CASES:
            source_path = tmp_path / "source.xlsx"
            source_path.write_bytes(raw)
            out_path = tmp_path / "preview.xlsx"
            write_test_cases_xlsx(source_path, sample_suite_export_data(), out_path)
            filename = "preview.xlsx"
        else:
            source_path = tmp_path / "tokenized.docx"
            source_path.write_bytes(raw)
            out_path = tmp_path / "preview.docx"
            write_report_docx(source_path, sample_report_data(), out_path)
            filename = "preview.docx"
        rendered = out_path.read_bytes()

    return StreamingResponse(
        iter([rendered]),
        media_type=CONTENT_TYPES[obj.kind],
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.delete("/{template_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_template(
    template_id: uuid.UUID,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_admin),
) -> None:
    obj = _get_template_or_404(db, template_id)
    if obj.is_default:
        raise HTTPException(status.HTTP_409_CONFLICT, "Deactivate this template before deleting it")

    storage = build_storage(get_settings())
    storage.delete(obj.file_key)
    if obj.rendered_key:
        storage.delete(obj.rendered_key)

    audit_record(
        db,
        actor_id=user.id,
        action="delete",
        entity="template",
        entity_id=str(template_id),
        request=request,
    )
    db.delete(obj)
    db.commit()
