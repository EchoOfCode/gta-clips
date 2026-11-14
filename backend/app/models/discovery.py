from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Optional

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base

if TYPE_CHECKING:
    from app.models.core import PlatformChannel


class DiscoveryRun(Base):
    __tablename__ = "discovery_runs"

    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"),
        primary_key=True,
        autoincrement=True,
    )
    provider: Mapped[str] = mapped_column(Text, nullable=False)
    trigger_type: Mapped[str] = mapped_column(Text, nullable=False, default="manual")
    status: Mapped[str] = mapped_column(Text, nullable=False, default="running")
    query: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    items_found: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    items_upserted: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    quota_used: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    details: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        Index("idx_discovery_runs_provider_started", "provider", "started_at"),
        Index("idx_discovery_runs_status", "status"),
        CheckConstraint(
            "status IN ('running', 'completed', 'failed', 'partial')",
            name="chk_discovery_run_status",
        ),
    )


class DiscoveredVideo(Base):
    __tablename__ = "discovered_videos"

    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"),
        primary_key=True,
        autoincrement=True,
    )
    platform: Mapped[str] = mapped_column(Text, nullable=False)
    external_video_id: Mapped[str] = mapped_column(Text, nullable=False)
    channel_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("platform_channels.id", ondelete="SET NULL"),
        nullable=True,
    )
    external_channel_id: Mapped[str] = mapped_column(Text, nullable=False)
    channel_title: Mapped[str | None] = mapped_column(Text, nullable=True)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_url: Mapped[str] = mapped_column(Text, nullable=False)
    thumbnail_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    duration_seconds: Mapped[Decimal | None] = mapped_column(
        Numeric(12, 3), nullable=True
    )
    view_count: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    like_count: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    is_live: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    raw_metadata: Mapped[str | None] = mapped_column(Text, nullable=True)
    first_discovered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    channel: Mapped[Optional["PlatformChannel"]] = relationship(  # type: ignore[name-defined]
        "PlatformChannel", back_populates="discovered_videos"
    )

    __table_args__ = (
        Index(
            "uq_discovered_video_platform_ext_id",
            "platform",
            "external_video_id",
            unique=True,
        ),
        Index("idx_discovered_videos_channel", "channel_id"),
        Index("idx_discovered_videos_published", "published_at"),
        Index("idx_discovered_videos_live", "platform", "is_live"),
    )


class LiveSession(Base):
    __tablename__ = "live_sessions"

    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"),
        primary_key=True,
        autoincrement=True,
    )
    platform: Mapped[str] = mapped_column(Text, nullable=False)
    channel_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("platform_channels.id", ondelete="CASCADE"),
        nullable=False,
    )
    external_session_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    title: Mapped[str | None] = mapped_column(Text, nullable=True)
    game_name: Mapped[str | None] = mapped_column(
        Text, nullable=True, default="Grand Theft Auto VI"
    )
    viewer_count: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    ended_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    channel: Mapped["PlatformChannel"] = relationship(  # type: ignore[name-defined]
        "PlatformChannel", back_populates="live_sessions"
    )

    __table_args__ = (
        Index("idx_live_sessions_channel_active", "channel_id", "is_active"),
        Index("idx_live_sessions_platform_active", "platform", "is_active"),
        Index("idx_live_sessions_ext_session", "platform", "external_session_id"),
    )
