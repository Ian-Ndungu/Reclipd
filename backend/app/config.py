from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, field_validator


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    database_url: str = "sqlite:///./reclipd.db"
    redis_url: str = "redis://localhost:6379/0"
    secret_key: str = Field(min_length=32)
    storage_root: str = "./data"
    cors_origins: list[str] = ["http://localhost:5173"]
    cookie_secure: bool = False
    max_upload_mb: int = 2048
    max_media_seconds: int = 3600
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_from: str = ""
    app_url: str = "http://localhost:5173"
    paypal_client_id: str = ""
    paypal_client_secret: str = ""
    paypal_merchant_id: str = ""
    paypal_webhook_id: str = ""
    paypal_sandbox_enabled: bool = False
    paystack_secret_key: str = ""
    billing_packs: list[dict] = []
    billing_return_url: str = "http://localhost:5173/studio/billing"
    free_minutes: int = 120
    unlimited_user_ids: list[str] = []
    low_memory_mode: bool = False
    whisper_model: str = "base"
    whisper_beam_size: int = Field(default=1, ge=1, le=5)
    whisper_cpu_threads: int = Field(default=2, ge=1, le=32)
    whisper_device: str = "cpu"
    whisper_compute_type: str = "int8"
    import_allowed_hosts: list[str] = []
    youtube_api_key: str = ""
    videoscale_enabled: bool = False
    videoscale_auth_header: str = Field(default="", repr=False)
    videoscale_budget_bytes: int = Field(default=0, ge=0)
    videoscale_max_import_mb: int = Field(default=512, ge=1, le=2048)
    youtube_download_enabled: bool = False
    youtube_download_timeout: int = Field(default=600, ge=30, le=1800)
    llm_base_url: str = ""
    llm_model: str = ""
    llm_api_key: str = ""
    speaker_model_path: str = ""
    task_always_eager: bool = False

    @field_validator("secret_key")
    @classmethod
    def reject_placeholder(cls, value):
        if value.startswith("replace-this-"):
            raise ValueError("Generate a random SECRET_KEY with scripts/bootstrap.py")
        return value


@lru_cache
def settings():
    return Settings()
