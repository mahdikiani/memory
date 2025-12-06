"""FastAPI server configuration."""

import dataclasses
import os
from pathlib import Path

import dotenv
from fastapi_mongo_base.core import config

dotenv.load_dotenv()


@dataclasses.dataclass
class Settings(config.Settings):
    """Server config settings."""

    project_name: str = os.getenv("PROJECT_NAME", "memory")
    base_dir: Path = Path(__file__).resolve().parent.parent
    base_path: str = "/api/memory/v1"
    storage_path: str = os.getenv("STORAGE_PATH", str(base_dir / "storage"))

    surrealdb_uri: str = os.getenv("SURREALDB_URI", "ws://surrealdb:8000/rpc")
    surrealdb_username: str = os.getenv("SURREALDB_USERNAME", "root")
    surrealdb_password: str = os.getenv("SURREALDB_PASSWORD", "root")
    surrealdb_namespace: str = os.getenv("SURREALDB_NAMESPACE", "knowledge")
    surrealdb_database: str = os.getenv("SURREALDB_DATABASE", "default")

    redis_queue_name: str = os.getenv("REDIS_QUEUE_NAME", "knowledge:ingest:queue")

    openrouter_api_key: str = os.getenv("OPENROUTER_API_KEY", "")
    openrouter_base_url: str = os.getenv(
        "OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"
    )
    llm_model: str = os.getenv("LLM_MODEL", "google/gemini-2.5-flash")
    embedding_model: str = os.getenv("EMBEDDING_MODEL", "openai/text-embedding-3-small")

    prompt_source: str | None = os.getenv(
        "PROMPT_SOURCE", None
    )  # File path or API URL for prompts

    coverage_dir: Path = base_dir / "htmlcov"

    @classmethod
    def get_log_config(cls, console_level: str = "INFO", **kwargs: object) -> dict:
        """
        Get the log configuration.

        Args:
            console_level: The level of the console log.
            **kwargs: Additional keyword arguments.

        """
        log_config = {
            "formatters": {
                "standard": {
                    "format": (
                        "[{levelname} {name} : {filename}:{lineno} : {asctime} "
                        "-> {funcName:10}] {message}"
                    ),
                    "style": "{",
                }
            },
            "handlers": {
                "console": {
                    "class": "logging.StreamHandler",
                    "level": console_level,
                    "formatter": "standard",
                },
                "file": {
                    "class": "logging.FileHandler",
                    "level": "INFO",
                    "formatter": "standard",
                    "filename": "logs/app.log",
                },
            },
            "loggers": {
                "": {
                    "handlers": [
                        "console",
                        "file",
                    ],
                    "level": console_level,
                    "propagate": True,
                },
            },
            "version": 1,
        }
        return log_config
