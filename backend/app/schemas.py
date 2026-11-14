from datetime import datetime
from decimal import Decimal
from typing import Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field

T = TypeVar("T")


class PaginatedResponse(BaseModel, Generic[T]):
    items: list[T]
    total: int
    page: int
    page_size: int
    pages: int


class DiscoveryTriggerRequest(BaseModel):
    provider: str = Field(..., description="Provider name: 'youtube' or 'twitch'")
    query: str = Field(
        default="Grand Theft Auto VI", description="Search query or game title"
    )
    is_live_only: bool = Field(
        default=False, description="Filter for active live broadcasts only"
    )
    max_results: int = Field(
        default=25, ge=1, le=100, description="Maximum items to query"
    )


class DiscoveredVideoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    platform: str
    external_video_id: str
    channel_id: int | None
    external_channel_id: str
    channel_title: str | None
    title: str
    description: str | None
    source_url: str
    thumbnail_url: str | None
    published_at: datetime | None
    duration_seconds: Decimal | None
    view_count: int | None
    like_count: int | None
    is_live: bool
    first_discovered_at: datetime
    last_seen_at: datetime


class LiveSessionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    platform: str
    channel_id: int
    external_session_id: str | None
    title: str | None
    game_name: str | None
    viewer_count: int | None
    started_at: datetime
    last_seen_at: datetime
    ended_at: datetime | None
    is_active: bool


class PlatformChannelOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    creator_id: int | None
    platform: str
    external_channel_id: str
    handle: str | None
    channel_url: str
    game_name: str | None
    current_title: str | None
    is_live: bool
    viewer_count: int | None
    language_code: str | None
    first_discovered_at: datetime
    last_seen_at: datetime


class DiscoveryRunOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    provider: str
    trigger_type: str
    status: str
    query: str | None
    started_at: datetime
    completed_at: datetime | None
    items_found: int
    items_upserted: int
    quota_used: int
    error_message: str | None
