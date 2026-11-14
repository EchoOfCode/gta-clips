from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )

    app_name: str = "GTA Clip Engine"
    environment: str = "production"
    api_host: str = "0.0.0.0"
    api_port: int = Field(default=18090, alias="API_PORT")

    # Storage paths
    media_root: str = Field(default="/media", alias="MEDIA_ROOT")

    # Database & Queue
    database_url: str = Field(
        default="postgresql+psycopg://gta_clip:password@db:5432/gta_clip_engine",
        alias="DATABASE_URL",
    )
    redis_url: str = Field(default="redis://redis:6379/0", alias="REDIS_URL")

    # Internal Authentication
    internal_api_key: str = Field(default="", alias="INTERNAL_API_KEY")

    # YouTube Data API v3
    youtube_api_key: str = Field(default="", alias="YOUTUBE_API_KEY")
    youtube_api_base_url: str = "https://www.googleapis.com/youtube/v3"

    # Twitch Helix API
    twitch_client_id: str = Field(default="", alias="TWITCH_CLIENT_ID")
    twitch_client_secret: str = Field(default="", alias="TWITCH_CLIENT_SECRET")
    twitch_token_url: str = "https://id.twitch.tv/oauth2/token"
    twitch_helix_base_url: str = "https://api.twitch.tv/helix"

    # Logging
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    log_json: bool = Field(default=True, alias="LOG_JSON")

    @field_validator("api_port", mode="before")
    @classmethod
    def parse_api_port(cls, v: object) -> int:
        if isinstance(v, str) and v.isdigit():
            return int(v)
        if isinstance(v, int):
            return v
        return 18090

    @property
    def is_youtube_configured(self) -> bool:
        return bool(self.youtube_api_key and self.youtube_api_key.strip())

    @property
    def is_twitch_configured(self) -> bool:
        return bool(
            self.twitch_client_id
            and self.twitch_client_id.strip()
            and self.twitch_client_secret
            and self.twitch_client_secret.strip()
        )

    def __repr__(self) -> str:
        """Custom repr to prevent leaking credentials in prints and logs."""
        return (
            f"<Settings app_name={self.app_name!r} environment={self.environment!r} "
            f"api_port={self.api_port} "
            f"database_url='***MASKED***' "
            f"youtube_configured={self.is_youtube_configured} "
            f"twitch_configured={self.is_twitch_configured}>"
        )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
