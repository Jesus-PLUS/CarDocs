from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.auth import get_current_user, require_owner
from app.db import get_db
from app.models import Document, User, Vehicle, VehicleShare
from app.schemas import DocumentOut, ShareOut, VehicleDetail, VehicleIn, VehicleOut, today_mx
from app.storage import get_storage

router = APIRouter(prefix="/api/vehicles", tags=["vehicles"])


def document_status(doc: Document) -> str:
    if doc.expires_on is None:
        return "sin_fecha"
    return "vencido" if doc.expires_on < today_mx() else "vigente"


def document_out(doc: Document) -> DocumentOut:
    return DocumentOut(
        id=doc.id,
        doc_type=doc.doc_type,
        issued_on=doc.issued_on,
        expires_on=doc.expires_on,
        original_name=doc.original_name,
        content_type=doc.content_type,
        size_bytes=doc.size_bytes,
        created_at=doc.created_at,
        status=document_status(doc),
    )


def vehicle_out(v: Vehicle) -> VehicleOut:
    return VehicleOut(
        id=v.id,
        plates=v.plates,
        brand=v.brand,
        model=v.model,
        year=v.year,
        document_count=len(v.documents),
        expired_count=sum(1 for d in v.documents if document_status(d) == "vencido"),
    )


def get_visible_vehicle(db: Session, user: User, vehicle_id: int) -> Vehicle:
    """Owner sees their own cars; a workshop sees only cars shared with it.

    Anything else is reported as 404 so a car's existence is not revealed.
    """
    vehicle = db.get(Vehicle, vehicle_id)
    if vehicle is not None:
        if user.role == "dueño" and vehicle.owner_id == user.id:
            return vehicle
        if user.role == "taller" and any(s.workshop_user_id == user.id for s in vehicle.shares):
            return vehicle
    raise HTTPException(status_code=404, detail="Vehículo no encontrado")


def get_owned_vehicle(db: Session, owner: User, vehicle_id: int) -> Vehicle:
    vehicle = db.get(Vehicle, vehicle_id)
    if vehicle is None or vehicle.owner_id != owner.id:
        raise HTTPException(status_code=404, detail="Vehículo no encontrado")
    return vehicle


def _commit_unique_plates(db: Session) -> None:
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Ya existe un vehículo con esas placas") from None


@router.get("", response_model=list[VehicleOut])
def list_vehicles(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    query = select(Vehicle).options(selectinload(Vehicle.documents)).order_by(Vehicle.id)
    if user.role == "dueño":
        query = query.where(Vehicle.owner_id == user.id)
    else:
        query = query.join(VehicleShare).where(VehicleShare.workshop_user_id == user.id)
    return [vehicle_out(v) for v in db.scalars(query)]


@router.post("", response_model=VehicleOut, status_code=201)
def create_vehicle(data: VehicleIn, owner: User = Depends(require_owner), db: Session = Depends(get_db)):
    vehicle = Vehicle(owner_id=owner.id, **data.model_dump())
    db.add(vehicle)
    _commit_unique_plates(db)
    return vehicle_out(vehicle)


@router.get("/{vehicle_id}", response_model=VehicleDetail)
def get_vehicle(
    vehicle_id: int,
    doc_type: str | None = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    vehicle = get_visible_vehicle(db, user, vehicle_id)
    docs = [d for d in vehicle.documents if doc_type is None or d.doc_type == doc_type]
    # Shares are the owner's business; a workshop does not see who else is authorized.
    shares = (
        [ShareOut(user_id=s.workshop_user_id, email=s.workshop.email) for s in vehicle.shares]
        if user.role == "dueño"
        else []
    )
    return VehicleDetail(
        **vehicle_out(vehicle).model_dump(),
        documents=[document_out(d) for d in docs],
        shares=shares,
    )


@router.put("/{vehicle_id}", response_model=VehicleOut)
def update_vehicle(
    vehicle_id: int,
    data: VehicleIn,
    owner: User = Depends(require_owner),
    db: Session = Depends(get_db),
):
    vehicle = get_owned_vehicle(db, owner, vehicle_id)
    for field, value in data.model_dump().items():
        setattr(vehicle, field, value)
    _commit_unique_plates(db)
    return vehicle_out(vehicle)


@router.delete("/{vehicle_id}", status_code=204)
def delete_vehicle(vehicle_id: int, owner: User = Depends(require_owner), db: Session = Depends(get_db)):
    vehicle = get_owned_vehicle(db, owner, vehicle_id)
    storage = get_storage()
    # Files first: if storage fails the rows stay and the delete can be retried.
    for doc in vehicle.documents:
        storage.delete(doc.storage_key)
    db.delete(vehicle)
    db.commit()
