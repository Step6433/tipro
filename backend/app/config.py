from functools import lru_cache
from pathlib import Path
from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[1]

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ROOT / '.env', extra='ignore')
    database_url: str
    jwt_secret: SecretStr
    webhook_secret: SecretStr
    frontend_url: str = 'http://localhost:5173'
    cors_origins: list[str] = ['http://localhost:5173', 'http://127.0.0.1:5173']
    access_token_minutes: int = Field(default=480, ge=5, le=1440)
    cookie_secure: bool = False
    cookie_name: str = 'tipro_session'
    allow_demo_controls: bool = True
    allow_admin_registration: bool = False
    legacy_currency: str = 'RUB'
    demo_password: SecretStr | None = None
    demo_delay_seconds: float = Field(default=1.0, ge=0, le=60)

    @field_validator('jwt_secret', 'webhook_secret')
    @classmethod
    def secret_length(cls, value):
        if len(value.get_secret_value()) < 32:
            raise ValueError('Use a random secret of at least 32 characters')
        return value

    @field_validator('database_url')
    @classmethod
    def postgres_only(cls, value):
        if not value.startswith('postgresql+asyncpg://'):
            raise ValueError('DATABASE_URL must use PostgreSQL with asyncpg')
        return value

@lru_cache
def get_settings() -> Settings:
    return Settings()
