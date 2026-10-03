from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth import require_owner
from app.db import get_db
from app.models import User, VehicleShare
from app.routers.vehicles import get_owned_vehicle
from app.schemas import ShareIn, ShareOut

router = APIRouter(prefix="/api/vehicles/{vehicle_id}/shares", tags=["shares"])


@router.post("", response_model=ShareOut, status_code=201)
def add_share(
    vehicle_id: int,
    data: ShareIn,
    owner: User = Depends(require_owner),
    db: Session = Depends(get_db),
):
    vehicle = get_owned_vehicle(db, owner, vehicle_id)
    workshop = db.scalar(select(User).where(User.email == data.email, User.role == "taller"))
    if workshop is None:
        raise HTTPException(status_code=404, detail="No hay un taller registrado con ese email")
    db.add(VehicleShare(vehicle_id=vehicle.id, workshop_user_id=workshop.id))
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Ese taller ya está autorizado") from None
    return ShareOut(user_id=workshop.id, email=workshop.email)


@router.delete("/{user_id}", status_code=204)
def remove_share(
    vehicle_id: int,
    user_id: int,
    owner: User = Depends(require_owner),
    db: Session = Depends(get_db),
):
    vehicle = get_owned_vehicle(db, owner, vehicle_id)
    share = db.scalar(
        select(VehicleShare).where(
            VehicleShare.vehicle_id == vehicle.id, VehicleShare.workshop_user_id == user_id
        )
    )
    if share is None:
        raise HTTPException(status_code=404, detail="Autorización no encontrada")
    db.delete(share)
    db.commit()
