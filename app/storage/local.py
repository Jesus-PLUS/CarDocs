import shutil
from pathlib import Path
from typing import BinaryIO


class LocalStorageAdapter:
    def __init__(self, root: str):
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, key: str) -> Path:
        path = (self.root / key).resolve()
        if not path.is_relative_to(self.root):
            raise ValueError("clave de almacenamiento inválida")
        return path

    def save(self, key: str, file: BinaryIO) -> str:
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        try:
            with open(path, "wb") as out:
                shutil.copyfileobj(file, out)
        except OSError:
            path.unlink(missing_ok=True)
            raise
        return key

    def open(self, key: str) -> BinaryIO:
        return open(self._path(key), "rb")

    def delete(self, key: str) -> None:
        self._path(key).unlink(missing_ok=True)
