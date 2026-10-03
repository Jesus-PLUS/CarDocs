# CarDocs

Expediente digital del automóvil. El dueño guarda la factura, la póliza, la verificación y las fotos de cada auto, ve qué se venció y puede autorizar a un taller para que consulte y descargue esos documentos.

**Stack:** FastAPI · SQLite · JWT · HTML/CSS/JS · Docker Compose.

## Requisitos

Docker con Compose v2.

## Arranque

```bash
cp .env.example .env
docker compose up --build -d
docker compose run --rm web python seed.py
```

Abre <http://localhost:8000>.

`.env` contiene el `SECRET_KEY` con el que se firman los tokens. Cámbialo antes de usar la app con datos reales.

## Comandos

| Acción | Comando |
|---|---|
| Construir y levantar | `docker compose up --build -d` |
| Cargar datos demo (se puede repetir) | `docker compose run --rm web python seed.py` |
| Ver logs | `docker compose logs -f web` |
| Detener | `docker compose down` |

La base de datos y los archivos viven en `./data` (`cardocs.db` y `storage/`), así que sobreviven a `docker compose down`. Para empezar de cero, detén el servicio y borra la carpeta `data`.

## Usuarios demo

| Rol | Email | Contraseña |
|---|---|---|
| dueño | `dueño@cardocs.local` | `Dueño123!` |
| taller | `taller@cardocs.local` | `Taller123!` |

El dueño tiene dos autos: **QRO-123-A** (Nissan Versa 2020, con póliza vigente, verificación vencida y una foto) y **QRO-456-B** (VW Jetta 2018, sin documentos, compartido con el taller).

## Almacenamiento en S3 (opcional)

Por defecto los archivos se guardan en disco (`./data/storage`). Para usar un bucket S3 propio, edita `.env`:

```
USE_S3=true
AWS_S3_BUCKET=mi-bucket
AWS_ACCESS_KEY_ID=...
AWS_SECRET_ACCESS_KEY=...
AWS_REGION=us-east-1
```

Luego `docker compose up --build -d`. Si falta alguna variable, el contenedor no arranca y el log indica cuál. Los objetos se guardan sin ACL pública, con la configuración privada por defecto del bucket. La base de datos sigue siendo SQLite en `./data`.
