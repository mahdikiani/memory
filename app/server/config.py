"""FastAPI server configuration."""

import dataclasses
import json
import logging.config
import os
from pathlib import Path

import dotenv
from singleton import Singleton

dotenv.load_dotenv()


@dataclasses.dataclass
class Settings(metaclass=Singleton):
    """Server config settings."""

    # base_dir: Path = Path(__file__).resolve().parent.parent
    root_url: str = os.getenv("DOMAIN") or "http://localhost:8000"
    project_name: str = os.getenv("PROJECT_NAME") or "PROJECT"
    base_path: str = "/api/v1"
    worker_update_time: int = int(os.getenv("WORKER_UPDATE_TIME", default=180)) or 180
    debug: bool = os.getenv("DEBUG", default="false").lower() == "true"

    _cors_origins_str: str | None = os.getenv("CORS_ORIGINS")

    page_max_limit: int = 100
    redis_uri: str = os.getenv("REDIS_URI", default="redis://redis:6379/")

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

    @property
    def cors_origins(self) -> list[str]:
        """Get the CORS origins."""

        if self._cors_origins_str and "[" in self._cors_origins_str:
            return json.loads(self._cors_origins_str)
        elif self._cors_origins_str:
            return [s.strip() for s in self._cors_origins_str.split(",")]
        return ["http://localhost:8000"]

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

    @classmethod
    def get_coverage_dir(cls) -> str:
        """Get the coverage directory."""

        return getattr(cls, "base_dir", Path(".")) / "htmlcov"

    @classmethod
    def config_logger(cls) -> None:
        """Configure the logger."""

        log_config = cls.get_log_config()

        if log_config["handlers"].get("file"):
            (getattr(cls, "base_dir", Path(".")) / "logs").mkdir(
                parents=True, exist_ok=True
            )

        logging.config.dictConfig(log_config)
