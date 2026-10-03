import os

DATA_DIR = os.environ.get("DATA_DIR", "/app/data")
DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:////app/data/cardocs.db")
SECRET_KEY = os.environ.get("SECRET_KEY", "cambialo")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.environ.get("ACCESS_TOKEN_EXPIRE_MINUTES", "480"))

USE_S3 = os.environ.get("USE_S3", "false").strip().lower() == "true"
AWS_S3_BUCKET = os.environ.get("AWS_S3_BUCKET", "")
AWS_ACCESS_KEY_ID = os.environ.get("AWS_ACCESS_KEY_ID", "")
AWS_SECRET_ACCESS_KEY = os.environ.get("AWS_SECRET_ACCESS_KEY", "")
AWS_REGION = os.environ.get("AWS_REGION", "us-east-1")

TIMEZONE = "America/Mexico_City"
MAX_UPLOAD_BYTES = 10 * 1024 * 1024
ALLOWED_EXTENSIONS = {
    "pdf": "application/pdf",
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
    "png": "image/png",
}
DOC_TYPES = ("factura", "poliza", "verificacion", "foto", "otro")
