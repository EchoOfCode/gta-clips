from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

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
    from app.models.discovery import DiscoveredVideo, LiveSession


class Creator(Base):
    __tablename__ = "creators"

    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"),
        primary_key=True,
        autoincrement=True,
    )
    display_name: Mapped[str] = mapped_column(Text, nullable=False)
    contact_email: Mapped[str | None] = mapped_column(Text, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    channels: Mapped[list["PlatformChannel"]] = relationship(
        "PlatformChannel", back_populates="creator"
    )
    rights_grants: Mapped[list["RightsGrant"]] = relationship(
        "RightsGrant", back_populates="creator"
    )
    media_assets: Mapped[list["MediaAsset"]] = relationship(
        "MediaAsset", back_populates="creator"
    )


class PlatformChannel(Base):
    __tablename__ = "platform_channels"

    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"),
        primary_key=True,
        autoincrement=True,
    )
    creator_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("creators.id", ondelete="SET NULL"), nullable=True
    )
    platform: Mapped[str] = mapped_column(Text, nullable=False)
    external_channel_id: Mapped[str] = mapped_column(Text, nullable=False)
    handle: Mapped[str | None] = mapped_column(Text, nullable=True)
    channel_url: Mapped[str] = mapped_column(Text, nullable=False)
    game_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    current_title: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_live: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    viewer_count: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    language_code: Mapped[str | None] = mapped_column(Text, nullable=True)
    first_discovered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    creator: Mapped[Creator | None] = relationship("Creator", back_populates="channels")
    discovered_videos: Mapped[list["DiscoveredVideo"]] = relationship(  # type: ignore[name-defined]
        "DiscoveredVideo", back_populates="channel"
    )
    live_sessions: Mapped[list["LiveSession"]] = relationship(  # type: ignore[name-defined]
        "LiveSession", back_populates="channel"
    )

    __table_args__ = (
        Index("uq_platform_channel", "platform", "external_channel_id", unique=True),
        CheckConstraint(
            "viewer_count IS NULL OR viewer_count >= 0", name="chk_channel_viewer_count"
        ),
    )


class RightsGrant(Base):
    __tablename__ = "rights_grants"

    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"),
        primary_key=True,
        autoincrement=True,
    )
    creator_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("creators.id", ondelete="RESTRICT"), nullable=False
    )
    platform: Mapped[str] = mapped_column(Text, nullable=False)
    scope: Mapped[str] = mapped_column(Text, nullable=False)
    evidence_uri: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(Text, nullable=False, default="pending")
    creator_footage_allowed: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    commercial_use_allowed: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    game_content_clearance: Mapped[str] = mapped_column(
        Text, nullable=False, default="unverified"
    )
    granted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    creator: Mapped[Creator] = relationship("Creator", back_populates="rights_grants")
    media_assets: Mapped[list["MediaAsset"]] = relationship(
        "MediaAsset", back_populates="rights_grant"
    )

    __table_args__ = (
        Index("idx_rights_grants_creator_status", "creator_id", "status"),
        CheckConstraint(
            "status IN ('pending', 'active', 'expired', 'revoked', 'rejected')",
            name="chk_rights_grant_status",
        ),
        CheckConstraint(
            "game_content_clearance IN ('unverified', 'approved', 'restricted', 'rejected')",
            name="chk_game_content_clearance",
        ),
        CheckConstraint(
            "expires_at IS NULL OR granted_at IS NULL OR expires_at > granted_at",
            name="chk_grant_expiry_after_grant",
        ),
    )


class MediaAsset(Base):
    __tablename__ = "media_assets"

    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"),
        primary_key=True,
        autoincrement=True,
    )
    creator_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("creators.id", ondelete="RESTRICT"), nullable=False
    )
    rights_grant_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("rights_grants.id", ondelete="RESTRICT"), nullable=False
    )
    platform: Mapped[str] = mapped_column(Text, nullable=False)
    source_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    storage_path: Mapped[str] = mapped_column(Text, nullable=False)
    sha256: Mapped[str | None] = mapped_column(Text, nullable=True)
    duration_seconds: Mapped[Decimal | None] = mapped_column(
        Numeric(12, 3), nullable=True
    )
    status: Mapped[str] = mapped_column(Text, nullable=False, default="received")
    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    retention_until: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    creator: Mapped[Creator] = relationship("Creator", back_populates="media_assets")
    rights_grant: Mapped[RightsGrant] = relationship(
        "RightsGrant", back_populates="media_assets"
    )
    candidate_moments: Mapped[list["CandidateMoment"]] = relationship(
        "CandidateMoment", back_populates="asset"
    )

    __table_args__ = (
        Index("idx_media_assets_status", "status"),
        CheckConstraint(
            "status IN ('received', 'processing', 'processed', 'quarantined', 'deleted')",
            name="chk_media_asset_status",
        ),
    )


class CandidateMoment(Base):
    __tablename__ = "candidate_moments"

    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"),
        primary_key=True,
        autoincrement=True,
    )
    asset_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("media_assets.id", ondelete="RESTRICT"), nullable=False
    )
    start_seconds: Mapped[Decimal] = mapped_column(Numeric(12, 3), nullable=False)
    end_seconds: Mapped[Decimal] = mapped_column(Numeric(12, 3), nullable=False)
    category: Mapped[str | None] = mapped_column(Text, nullable=True)
    score: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    explanation: Mapped[str | None] = mapped_column(Text, nullable=True)
    model_version: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(Text, nullable=False, default="candidate")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    asset: Mapped[MediaAsset] = relationship(
        "MediaAsset", back_populates="candidate_moments"
    )
    edited_clips: Mapped[list["EditedClip"]] = relationship(
        "EditedClip", back_populates="candidate_moment"
    )

    __table_args__ = (
        CheckConstraint("start_seconds >= 0", name="chk_moment_start_positive"),
        CheckConstraint(
            "end_seconds > start_seconds", name="chk_moment_end_after_start"
        ),
        CheckConstraint(
            "score IS NULL OR (score >= 0 AND score <= 100)",
            name="chk_moment_score_range",
        ),
        CheckConstraint(
            "status IN ('candidate', 'approved', 'rejected', 'duplicate', 'needs_review')",
            name="chk_moment_status",
        ),
    )


class EditedClip(Base):
    __tablename__ = "edited_clips"

    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"),
        primary_key=True,
        autoincrement=True,
    )
    candidate_moment_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("candidate_moments.id", ondelete="RESTRICT"),
        nullable=False,
    )
    storage_path: Mapped[str] = mapped_column(Text, nullable=False)
    thumbnail_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    title: Mapped[str | None] = mapped_column(Text, nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    duration_seconds: Mapped[Decimal | None] = mapped_column(
        Numeric(12, 3), nullable=True
    )
    edit_profile: Mapped[str | None] = mapped_column(Text, nullable=True)
    quality_status: Mapped[str] = mapped_column(Text, nullable=False, default="pending")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    candidate_moment: Mapped[CandidateMoment] = relationship(
        "CandidateMoment", back_populates="edited_clips"
    )
    publishing_jobs: Mapped[list["PublishingJob"]] = relationship(
        "PublishingJob", back_populates="edited_clip"
    )

    __table_args__ = (
        CheckConstraint(
            "quality_status IN ('pending', 'passed', 'failed', 'needs_review')",
            name="chk_clip_quality_status",
        ),
    )


class PublishingJob(Base):
    __tablename__ = "publishing_jobs"

    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"),
        primary_key=True,
        autoincrement=True,
    )
    edited_clip_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("edited_clips.id", ondelete="RESTRICT"), nullable=False
    )
    platform: Mapped[str] = mapped_column(Text, nullable=False, default="youtube")
    destination_channel_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    scheduled_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    published_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    external_video_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(Text, nullable=False, default="pending_review")
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    edited_clip: Mapped[EditedClip] = relationship(
        "EditedClip", back_populates="publishing_jobs"
    )

    __table_args__ = (
        Index("idx_publishing_jobs_status_schedule", "status", "scheduled_at"),
        CheckConstraint(
            "status IN ('pending_review', 'approved', 'scheduled', 'uploading', 'published', 'failed', 'cancelled')",
            name="chk_publishing_job_status",
        ),
    )
