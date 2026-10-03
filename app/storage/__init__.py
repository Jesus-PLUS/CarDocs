import os
from functools import lru_cache

from app import config
from app.storage.base import StorageAdapter


@lru_cache
def get_storage() -> StorageAdapter:
    if not config.USE_S3:
        from app.storage.local import LocalStorageAdapter

        return LocalStorageAdapter(os.path.join(config.DATA_DIR, "storage"))

    required = {
        "AWS_S3_BUCKET": config.AWS_S3_BUCKET,
        "AWS_ACCESS_KEY_ID": config.AWS_ACCESS_KEY_ID,
        "AWS_SECRET_ACCESS_KEY": config.AWS_SECRET_ACCESS_KEY,
        "AWS_REGION": config.AWS_REGION,
    }
    missing = [name for name, value in required.items() if not value]
    if missing:
        raise RuntimeError(
            f"USE_S3=true pero faltan variables en .env: {', '.join(missing)}. "
            "Complétalas o pon USE_S3=false para usar el almacenamiento local."
        )
    from app.storage.s3 import S3Adapter

    return S3Adapter(
        config.AWS_S3_BUCKET,
        config.AWS_REGION,
        config.AWS_ACCESS_KEY_ID,
        config.AWS_SECRET_ACCESS_KEY,
    )
