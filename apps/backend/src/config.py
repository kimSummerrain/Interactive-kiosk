import os
from dataclasses import dataclass
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parent.parent


def load_env() -> None:
    """Read only the backend's .env, independent of the launch directory."""
    path = BACKEND_ROOT / ".env"
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


@dataclass
class Settings:
    sqlite_db_path: str

    @staticmethod
    def load() -> "Settings":
        load_env()
        path = Path(os.getenv("SQLITE_DB_PATH", "instance/kiosk.db"))
        if not path.is_absolute():
            path = BACKEND_ROOT / path
        return Settings(sqlite_db_path=str(path))
