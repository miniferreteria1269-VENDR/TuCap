from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "TuCap API"
    environment: str = "development"
    database_url: str = "sqlite:///./tucap.db"
    cors_origins: str = "http://localhost:5173,https://tu-cap.vercel.app"
    bootstrap_tenant_id: str = "00000000-0000-0000-0000-000000000001"
    bootstrap_tenant_name: str = "TuCap Pilot"
    bootstrap_admin_email: str | None = None
    bootstrap_admin_password: str | None = None
    bootstrap_admin_name: str = "Administrador"
    jwt_secret: str | None = None
    jwt_expire_minutes: int = 480
    session_idle_minutes: int = 5

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
