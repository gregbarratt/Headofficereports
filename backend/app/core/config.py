from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


BACKEND_DIR = Path(__file__).resolve().parents[2]
PROJECT_ROOT = BACKEND_DIR.parent


class Settings(BaseSettings):
    project_name: str = "Head Office Reporting & Trust Reconciliation System"
    environment: str = "development"
    database_url: str = ""
    frontend_url: str = "http://127.0.0.1:5173"
    upload_dir: Path = BACKEND_DIR / "uploads"
    max_upload_size_mb: int = 100
    jwt_secret_key: str = ""
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 720
    initial_super_admin_email: str = ""
    initial_super_admin_password: str = ""
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_from_email: str = ""
    smtp_use_tls: bool = True
    sings_api_base_url: str = ""
    sings_api_key: str = ""
    sings_api_secret: str = ""
    felloh_api_base_url: str = "https://api.felloh.com"
    felloh_public_key: str = ""
    felloh_private_key: str = ""
    felloh_organisation_id: str = ""
    traveltek_api_base_url: str = "https://fusionapi.traveltek.net/0.9/interface.pl"
    traveltek_secure_api_base_url: str = "https://secure.traveltek.net/fusionapi/0.9/interface.pl"
    traveltek_username: str = ""
    traveltek_password: str = ""
    traveltek_sitename: str = ""
    traveltek_max_calls_per_run: int = 25

    model_config = SettingsConfigDict(
        env_file=(PROJECT_ROOT / ".env", BACKEND_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def database_configured(self) -> bool:
        return bool(self.database_url.strip())

    @property
    def sqlalchemy_database_url(self) -> str:
        if self.database_url.startswith("postgresql://"):
            return self.database_url.replace("postgresql://", "postgresql+psycopg://", 1)
        return self.database_url

    @property
    def cors_allowed_origins(self) -> list[str]:
        origins = {
            self.frontend_url,
            "http://127.0.0.1:5173",
            "http://localhost:5173",
        }
        return sorted(origin for origin in origins if origin)

    @property
    def max_upload_size_bytes(self) -> int:
        return self.max_upload_size_mb * 1024 * 1024

    @property
    def smtp_configured(self) -> bool:
        return bool(self.smtp_host.strip() and self.smtp_from_email.strip())

    @property
    def sings_api_configured(self) -> bool:
        return bool(self.sings_api_base_url.strip() and self.sings_api_key.strip())

    @property
    def felloh_api_configured(self) -> bool:
        return bool(
            self.felloh_api_base_url.strip()
            and self.felloh_public_key.strip()
            and self.felloh_private_key.strip()
            and self.felloh_organisation_id.strip()
        )

    @property
    def traveltek_api_configured(self) -> bool:
        return bool(
            self.traveltek_api_base_url.strip()
            and self.traveltek_secure_api_base_url.strip()
            and self.traveltek_username.strip()
            and self.traveltek_password.strip()
            and self.traveltek_sitename.strip()
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
