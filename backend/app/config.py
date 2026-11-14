from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=None, extra="ignore")

    app_name: str = "GTA Clip Engine"
    environment: str = "development"
    database_url: str
    redis_url: str = "redis://redis:6379/0"
    media_root: str = "/media"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
