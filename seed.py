"""Carga datos demo. Seguro de repetir: si ya existen los usuarios demo, no hace nada."""

import io
import struct
import zlib
from datetime import timedelta
from pathlib import Path

from sqlalchemy import select

from app import models  # noqa: F401  (F401: registers the tables on Base.metadata)
from app.auth import hash_password
from app.config import DATA_DIR
from app.db import Base, SessionLocal, engine
from app.models import Document, User, Vehicle, VehicleShare
from app.schemas import today_mx
from app.storage import get_storage

OWNER_EMAIL, OWNER_PASSWORD = "dueño@cardocs.local", "Dueño123!"
WORKSHOP_EMAIL, WORKSHOP_PASSWORD = "taller@cardocs.local", "Taller123!"


def sample_pdf(title: str) -> bytes:
    stream = f"BT /F1 18 Tf 72 720 Td ({title}) Tj ET".encode()
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R "
        b"/Resources << /Font << /F1 5 0 R >> >> >>",
        b"<< /Length %d >>\nstream\n" % len(stream) + stream + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    out = io.BytesIO()
    out.write(b"%PDF-1.4\n")
    offsets = []
    for number, body in enumerate(objects, start=1):
        offsets.append(out.tell())
        out.write(b"%d 0 obj\n" % number + body + b"\nendobj\n")
    xref = out.tell()
    out.write(b"xref\n0 %d\n0000000000 65535 f \n" % (len(objects) + 1))
    for offset in offsets:
        out.write(b"%010d 00000 n \n" % offset)
    out.write(b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (len(objects) + 1, xref))
    return out.getvalue()


def sample_png(size: int = 64, rgb: tuple[int, int, int] = (15, 157, 143)) -> bytes:
    def chunk(kind: bytes, data: bytes) -> bytes:
        body = kind + data
        return struct.pack(">I", len(data)) + body + struct.pack(">I", zlib.crc32(body))

    row = b"\x00" + bytes(rgb) * size
    header = struct.pack(">IIBBBBB", size, size, 8, 2, 0, 0, 0)
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", header)
        + chunk(b"IDAT", zlib.compress(row * size))
        + chunk(b"IEND", b"")
    )


def main() -> None:
    Path(DATA_DIR).mkdir(parents=True, exist_ok=True)
    Base.metadata.create_all(engine)
    storage = get_storage()
    today = today_mx()

    with SessionLocal() as db:
        if db.scalar(select(User).where(User.email.in_([OWNER_EMAIL, WORKSHOP_EMAIL]))):
            print("Los datos demo ya existen; no se hizo nada.")
            return

        owner = User(email=OWNER_EMAIL, password_hash=hash_password(OWNER_PASSWORD), role="dueño")
        workshop = User(email=WORKSHOP_EMAIL, password_hash=hash_password(WORKSHOP_PASSWORD), role="taller")
        db.add_all([owner, workshop])
        db.flush()

        versa = Vehicle(owner_id=owner.id, plates="QRO-123-A", brand="Nissan", model="Versa", year=2020)
        jetta = Vehicle(owner_id=owner.id, plates="QRO-456-B", brand="VW", model="Jetta", year=2018)
        db.add_all([versa, jetta])
        db.flush()

        db.add(VehicleShare(vehicle_id=jetta.id, workshop_user_id=workshop.id))

        samples = [
            # (vehicle, doc_type, filename, content_type, data, issued_on, expires_on)
            (versa, "poliza", "poliza_2025.pdf", "application/pdf", sample_pdf("Poliza de seguro"),
             today - timedelta(days=185), today + timedelta(days=180)),
            (versa, "verificacion", "verificacion.pdf", "application/pdf", sample_pdf("Verificacion vehicular"),
             today - timedelta(days=200), today - timedelta(days=20)),
            (versa, "foto", "frente.png", "image/png", sample_png(), None, None),
        ]
        for vehicle, doc_type, name, content_type, data, issued, expires in samples:
            key = storage.save(f"{vehicle.id}/seed_{name}", io.BytesIO(data))
            db.add(
                Document(
                    vehicle_id=vehicle.id,
                    doc_type=doc_type,
                    issued_on=issued,
                    expires_on=expires,
                    original_name=name,
                    content_type=content_type,
                    storage_key=key,
                    size_bytes=len(data),
                )
            )
        db.commit()

    print("Datos demo creados:")
    print(f"  dueño:  {OWNER_EMAIL} / {OWNER_PASSWORD}")
    print(f"  taller: {WORKSHOP_EMAIL} / {WORKSHOP_PASSWORD}")


if __name__ == "__main__":
    main()
