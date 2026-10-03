import re
from datetime import date, datetime
from typing import Literal
from zoneinfo import ZoneInfo

from pydantic import BaseModel, ConfigDict, field_validator

from app.config import TIMEZONE

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
PLATES_RE = re.compile(r"^[A-Z0-9-]{3,15}$")


def today_mx() -> date:
    return datetime.now(ZoneInfo(TIMEZONE)).date()


def normalize_email(value: str) -> str:
    value = value.strip().lower()
    if len(value) > 254 or not EMAIL_RE.match(value):
        raise ValueError("email inválido")
    return value


class RegisterIn(BaseModel):
    email: str
    password: str
    role: Literal["dueño", "taller"]

    _email = field_validator("email")(normalize_email)

    @field_validator("password")
    @classmethod
    def _password(cls, v: str) -> str:
        # bcrypt only hashes the first 72 bytes; reject rather than silently truncate.
        if len(v) < 8 or len(v.encode()) > 72:
            raise ValueError("la contraseña debe tener entre 8 y 72 caracteres")
        return v


class LoginIn(BaseModel):
    email: str
    password: str


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    email: str
    role: str


class AuthOut(BaseModel):
    user: UserOut
    token: str


class VehicleIn(BaseModel):
    plates: str
    brand: str
    model: str
    year: int

    @field_validator("plates")
    @classmethod
    def _plates(cls, v: str) -> str:
        v = re.sub(r"\s+", "", v).upper()
        if not PLATES_RE.match(v):
            raise ValueError("placas inválidas (letras, números y guiones, de 3 a 15 caracteres)")
        return v

    @field_validator("brand", "model")
    @classmethod
    def _text(cls, v: str) -> str:
        v = v.strip()
        if not v or len(v) > 60:
            raise ValueError("debe tener entre 1 y 60 caracteres")
        return v

    @field_validator("year")
    @classmethod
    def _year(cls, v: int) -> int:
        max_year = today_mx().year + 1
        if not 1980 <= v <= max_year:
            raise ValueError(f"el año debe estar entre 1980 y {max_year}")
        return v


class DocumentOut(BaseModel):
    id: int
    doc_type: str
    issued_on: date | None
    expires_on: date | None
    original_name: str
    content_type: str
    size_bytes: int
    created_at: datetime
    status: Literal["vigente", "vencido", "sin_fecha"]


class ShareOut(BaseModel):
    user_id: int
    email: str


class VehicleOut(BaseModel):
    id: int
    plates: str
    brand: str
    model: str
    year: int
    document_count: int
    expired_count: int


class VehicleDetail(VehicleOut):
    documents: list[DocumentOut]
    shares: list[ShareOut]


class ShareIn(BaseModel):
    email: str

    _email = field_validator("email")(normalize_email)
