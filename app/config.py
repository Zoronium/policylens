"""Settings from environment (and an optional .env file). Read on every call so tests can patch."""

import os
from dataclasses import dataclass
from pathlib import Path


def _load_dotenv(path: Path = Path(".env")) -> None:
    if not path.is_file():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


_load_dotenv()


@dataclass(frozen=True)
class Settings:
    llm_base_url: str
    llm_api_key: str
    llm_model: str
    database_url: str
    review_threshold: float


def get_settings() -> Settings:
    env = os.environ.get
    return Settings(
        llm_base_url=env("LLM_BASE_URL") or "https://api.openai.com/v1",
        llm_api_key=env("LLM_API_KEY") or "",
        llm_model=env("LLM_MODEL") or "gpt-4o-mini",
        database_url=env("DATABASE_URL") or "sqlite:///./policylens.db",
        review_threshold=float(env("REVIEW_THRESHOLD") or 0.7),
    )
