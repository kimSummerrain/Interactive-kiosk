import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


def _load_dotenv_if_exists(dotenv_path: str = ".env") -> None:
    """
    python-dotenv 없이 .env 읽기
    """
    p = Path(dotenv_path)
    if not p.exists():
        return

    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        os.environ.setdefault(
            key.strip(),
            value.strip().strip('"').strip("'")
        )


@dataclass
class Settings:
    # ✅ SQLite (필수)
    sqlite_db_path: str

    # ✅ OpenAI (선택)
    openai_api_key: Optional[str]
    openai_model: str

    # ✅ Azure Face (지금은 선택)
    azure_face_endpoint: Optional[str]
    azure_face_key: Optional[str]

    @staticmethod
    def load() -> "Settings":
        _load_dotenv_if_exists(".env")

        return Settings(
            sqlite_db_path=os.getenv(
                "SQLITE_DB_PATH",
                "/home/8273/hackathon-season3/kiosk.db"
            ),

            openai_api_key=os.getenv("OPENAI_API_KEY"),
            openai_model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),

            azure_face_endpoint=os.getenv("AZURE_FACE_ENDPOINT"),
            azure_face_key=os.getenv("AZURE_FACE_KEY"),
        )
