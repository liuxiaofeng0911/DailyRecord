from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """全局配置，全部来自环境变量 / .env。"""

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore", case_sensitive=False
    )

    env: str = "dev"
    log_level: str = "INFO"
    app_version: str = "0.1.0"

    database_url: str = "sqlite:///./data/diary.db"
    data_dir: Path = Path("./data")
    app_timezone: str = "Asia/Shanghai"
    # 开发/测试环境自动建表；生产由 alembic upgrade head 负责
    auto_create: bool = True

    jwt_secret: str = "dev-only-change-me-please-32bytes-minimum-secret"
    jwt_expire_minutes: int = 480
    jwt_refresh_threshold_minutes: int = 60
    session_max: int = 10

    rsa_private_key: str = ""
    rsa_public_key: str = ""
    rsa_private_key_path: str = ""
    rsa_public_key_path: str = ""

    argon2_memory_kib: int = 65536
    argon2_time_cost: int = 3
    argon2_parallelism: int = 2

    redis_url: str = ""

    immich_url: str = ""
    immich_api_key: str = ""
    immich_album_id: str = ""
    immich_write_description: bool = True

    ai_enabled: bool = False
    ollama_url: str = "http://ollama:11434"
    ollama_vlm_model: str = "qwen2.5vl:7b"
    ollama_text_model: str = "qwen2.5:7b"

    max_upload_mb: int = 200
    cors_origins: str = "http://localhost:5173,http://localhost:8080"

    photo_purge_enabled: bool = True
    photo_purge_hour: int = 3
    photo_purge_minute: int = 30

    @property
    def immich_enabled(self) -> bool:
        return bool(self.immich_url and self.immich_api_key)

    @property
    def cors_origin_list(self) -> list[str]:
        return [item.strip() for item in self.cors_origins.split(",") if item.strip()]

    @property
    def uploads_dir(self) -> Path:
        path = self.data_dir / "uploads"
        path.mkdir(parents=True, exist_ok=True)
        return path


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
