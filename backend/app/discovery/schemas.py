from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ProviderStatusEnum(str, Enum):
    CONFIGURED = "configured"
    NOT_CONFIGURED = "not_configured"
    UNSUPPORTED = "unsupported"
    ERROR = "error"


class DiscoveryFilter(BaseModel):
    query: str = "Grand Theft Auto VI"
    is_live_only: bool = False
    max_results: int = Field(default=25, ge=1, le=100)
    page_token: str | None = None


class DiscoveredChannelMetadata(BaseModel):
    model_config = ConfigDict(extra="ignore")

    platform: str
    external_channel_id: str
    handle: str | None = None
    channel_url: str
    display_name: str
    game_name: str | None = None
    current_title: str | None = None
    is_live: bool = False
    viewer_count: int | None = None
    language_code: str | None = None


class DiscoveredVideoMetadata(BaseModel):
    model_config = ConfigDict(extra="ignore")

    platform: str
    external_video_id: str
    external_channel_id: str
    channel_title: str | None = None
    channel_url: str | None = None
    title: str
    description: str | None = None
    source_url: str
    thumbnail_url: str | None = None
    published_at: datetime | None = None
    duration_seconds: Decimal | None = None
    view_count: int | None = None
    like_count: int | None = None
    is_live: bool = False
    raw_metadata: dict[str, Any] = Field(default_factory=dict)


class DiscoveredLiveStreamMetadata(BaseModel):
    model_config = ConfigDict(extra="ignore")

    platform: str
    external_session_id: str | None = None
    external_channel_id: str
    channel_title: str
    channel_url: str
    title: str
    game_name: str = "Grand Theft Auto VI"
    viewer_count: int | None = None
    started_at: datetime
    language_code: str | None = None
    raw_metadata: dict[str, Any] = Field(default_factory=dict)


class DiscoveryResult(BaseModel):
    model_config = ConfigDict(extra="ignore")

    provider: str
    videos: list[DiscoveredVideoMetadata] = Field(default_factory=list)
    live_streams: list[DiscoveredLiveStreamMetadata] = Field(default_factory=list)
    channels: list[DiscoveredChannelMetadata] = Field(default_factory=list)
    next_page_token: str | None = None
    quota_used: int = 0
    raw_response: dict[str, Any] | None = None


class ProviderStatusResponse(BaseModel):
    provider: str
    status: ProviderStatusEnum
    supported: bool
    configured: bool
    details: str | None = None
    quota_info: dict[str, Any] | None = None
