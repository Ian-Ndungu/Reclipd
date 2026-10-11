from pathlib import Path
from typing import Protocol
from .config import settings


class Storage(Protocol):
    def path(self, key: str) -> Path: ...
    def delete(self, key: str) -> None: ...


class LocalStorage:
    def __init__(self):
        self.root = Path(settings().storage_root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def path(self, key: str) -> Path:
        path = (self.root / key).resolve()
        if not path.is_relative_to(self.root) or path == self.root:
            raise ValueError("Invalid storage key")
        path.parent.mkdir(parents=True, exist_ok=True)
        return path

    def delete(self, key: str):
        self.path(key).unlink(missing_ok=True)


storage = LocalStorage()
