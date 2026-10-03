from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from app import models  # noqa: F401  (F401: registers the tables on Base.metadata)
from app.config import DATA_DIR
from app.db import Base, engine
from app.routers import auth, documents, shares, vehicles
from app.storage import get_storage

BASE_DIR = Path(__file__).parent


@asynccontextmanager
async def lifespan(_app: FastAPI):
    Path(DATA_DIR).mkdir(parents=True, exist_ok=True)
    get_storage()  # with USE_S3=true and missing credentials this aborts startup with a clear message
    Base.metadata.create_all(engine)
    yield


app = FastAPI(title="CarDocs", lifespan=lifespan)


@app.exception_handler(RequestValidationError)
async def validation_error(_request: Request, exc: RequestValidationError):
    # The spec asks for 400 (not FastAPI's default 422) with a message the UI can show.
    problems = []
    for err in exc.errors():
        field = str(err["loc"][-1]) if err["loc"] else "solicitud"
        message = str(err["msg"]).removeprefix("Value error, ")
        problems.append(f"{field}: {message}")
    return JSONResponse(status_code=400, content={"detail": "; ".join(problems)})


app.include_router(auth.router)
app.include_router(vehicles.router)
app.include_router(documents.router)
app.include_router(shares.router)

app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")


def _page(name: str):
    return FileResponse(BASE_DIR / "templates" / name)


@app.get("/", include_in_schema=False)
def index():
    return RedirectResponse("/garage")


@app.get("/login", include_in_schema=False)
def login_page():
    return _page("login.html")


@app.get("/register", include_in_schema=False)
def register_page():
    return _page("register.html")


@app.get("/garage", include_in_schema=False)
def garage_page():
    return _page("garage.html")


@app.get("/vehicles/new", include_in_schema=False)
def new_vehicle_page():
    return _page("vehicle_new.html")


@app.get("/vehicles/{vehicle_id:int}", include_in_schema=False)
def vehicle_page(vehicle_id: int):
    return _page("vehicle.html")
