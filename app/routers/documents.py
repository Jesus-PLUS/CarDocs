import io
import re
import uuid
from datetime import date
from pathlib import PurePath
from urllib.parse import quote

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.auth import get_current_user, require_owner
from app.config import ALLOWED_EXTENSIONS, DOC_TYPES, MAX_UPLOAD_BYTES
from app.db import get_db
from app.models import Document, User
from app.routers.vehicles import document_out, get_owned_vehicle, get_visible_vehicle
from app.schemas import DocumentOut
from app.storage import get_storage

router = APIRouter(prefix="/api", tags=["documents"])


def _parse_date(value: str, label: str) -> date | None:
    if not value.strip():
        return None
    try:
        return date.fromisoformat(value.strip())
    except ValueError:
        raise HTTPException(status_code=400, detail=f"{label}: fecha inválida (use AAAA-MM-DD)") from None


def _safe_filename(name: str) -> str:
    base = PurePath(name.replace("\\", "/")).name
    return re.sub(r"[^A-Za-z0-9._-]", "_", base)[:100] or "archivo"


@router.post("/vehicles/{vehicle_id}/documents", response_model=DocumentOut, status_code=201)
async def upload_document(
    vehicle_id: int,
    file: UploadFile = File(...),
    doc_type: str = Form(...),
    issued_on: str = Form(""),
    expires_on: str = Form(""),
    owner: User = Depends(require_owner),
    db: Session = Depends(get_db),
):
    vehicle = get_owned_vehicle(db, owner, vehicle_id)

    if doc_type not in DOC_TYPES:
        raise HTTPException(status_code=400, detail=f"Tipo de documento inválido: {', '.join(DOC_TYPES)}")
    issued = _parse_date(issued_on, "Fecha de emisión")
    expires = _parse_date(expires_on, "Fecha de vencimiento")

    original_name = _safe_filename(file.filename or "")
    ext = original_name.rsplit(".", 1)[-1].lower() if "." in original_name else ""
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail="Formato no permitido. Use pdf, jpg, jpeg o png")

    data = await file.read(MAX_UPLOAD_BYTES + 1)
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="El archivo excede el máximo de 10 MB")
    if not data:
        raise HTTPException(status_code=400, detail="El archivo está vacío")

    storage = get_storage()
    key = f"{vehicle.id}/{uuid.uuid4().hex}_{original_name}"
    try:
        storage.save(key, io.BytesIO(data))
    except Exception:
        # No row is inserted when the file could not be stored.
        raise HTTPException(status_code=500, detail="No se pudo guardar el archivo") from None

    doc = Document(
        vehicle_id=vehicle.id,
        doc_type=doc_type,
        issued_on=issued,
        expires_on=expires,
        original_name=original_name,
        content_type=ALLOWED_EXTENSIONS[ext],
        storage_key=key,
        size_bytes=len(data),
    )
    db.add(doc)
    try:
        db.commit()
    except Exception:
        db.rollback()
        storage.delete(key)
        raise
    return document_out(doc)


def _stream(fileobj):
    try:
        while chunk := fileobj.read(64 * 1024):
            yield chunk
    finally:
        fileobj.close()


@router.get("/documents/{document_id}/download")
def download_document(
    document_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    doc = db.get(Document, document_id)
    if doc is None:
        raise HTTPException(status_code=404, detail="Documento no encontrado")
    get_visible_vehicle(db, user, doc.vehicle_id)  # 404 if this user may not see the car
    try:
        fileobj = get_storage().open(doc.storage_key)
    except Exception:
        raise HTTPException(status_code=404, detail="El archivo no está disponible") from None
    headers = {"Content-Disposition": f"attachment; filename*=UTF-8''{quote(doc.original_name)}"}
    return StreamingResponse(_stream(fileobj), media_type=doc.content_type, headers=headers)


@router.delete("/documents/{document_id}", status_code=204)
def delete_document(
    document_id: int, owner: User = Depends(require_owner), db: Session = Depends(get_db)
):
    doc = db.get(Document, document_id)
    if doc is None:
        raise HTTPException(status_code=404, detail="Documento no encontrado")
    get_owned_vehicle(db, owner, doc.vehicle_id)
    get_storage().delete(doc.storage_key)
    db.delete(doc)
    db.commit()
