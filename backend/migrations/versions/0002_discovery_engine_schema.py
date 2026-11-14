"""0002 discovery engine schema

Revision ID: 0002_discovery
Revises: 0001_baseline
Create Date: 2026-11-15 01:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.engine.reflection import Inspector

# revision identifiers, used by Alembic.
revision: str = "0002_discovery"
down_revision: str | None = "0001_baseline"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = Inspector.from_engine(bind)
    existing_tables = set(inspector.get_table_names())

    # 1. discovery_runs
    if "discovery_runs" not in existing_tables:
        op.create_table(
            "discovery_runs",
            sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
            sa.Column("provider", sa.Text(), nullable=False),
            sa.Column(
                "trigger_type", sa.Text(), nullable=False, server_default="manual"
            ),
            sa.Column("status", sa.Text(), nullable=False, server_default="running"),
            sa.Column("query", sa.Text(), nullable=True),
            sa.Column(
                "started_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.func.now(),
            ),
            sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column(
                "items_found", sa.BigInteger(), nullable=False, server_default="0"
            ),
            sa.Column(
                "items_upserted", sa.BigInteger(), nullable=False, server_default="0"
            ),
            sa.Column(
                "quota_used", sa.BigInteger(), nullable=False, server_default="0"
            ),
            sa.Column("error_message", sa.Text(), nullable=True),
            sa.Column("details", sa.Text(), nullable=True),
            sa.CheckConstraint(
                "status IN ('running', 'completed', 'failed', 'partial')",
                name="chk_discovery_run_status",
            ),
        )
        op.create_index(
            "idx_discovery_runs_provider_started",
            "discovery_runs",
            ["provider", "started_at"],
        )
        op.create_index("idx_discovery_runs_status", "discovery_runs", ["status"])

    # 2. discovered_videos
    if "discovered_videos" not in existing_tables:
        op.create_table(
            "discovered_videos",
            sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
            sa.Column("platform", sa.Text(), nullable=False),
            sa.Column("external_video_id", sa.Text(), nullable=False),
            sa.Column(
                "channel_id",
                sa.BigInteger(),
                sa.ForeignKey("platform_channels.id", ondelete="SET NULL"),
                nullable=True,
            ),
            sa.Column("external_channel_id", sa.Text(), nullable=False),
            sa.Column("channel_title", sa.Text(), nullable=True),
            sa.Column("title", sa.Text(), nullable=False),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("source_url", sa.Text(), nullable=False),
            sa.Column("thumbnail_url", sa.Text(), nullable=True),
            sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("duration_seconds", sa.Numeric(12, 3), nullable=True),
            sa.Column("view_count", sa.BigInteger(), nullable=True),
            sa.Column("like_count", sa.BigInteger(), nullable=True),
            sa.Column(
                "is_live", sa.Boolean(), nullable=False, server_default=sa.text("false")
            ),
            sa.Column("raw_metadata", sa.Text(), nullable=True),
            sa.Column(
                "first_discovered_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.func.now(),
            ),
            sa.Column(
                "last_seen_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.func.now(),
            ),
            sa.UniqueConstraint(
                "platform",
                "external_video_id",
                name="uq_discovered_video_platform_ext_id",
            ),
        )
        op.create_index(
            "idx_discovered_videos_channel", "discovered_videos", ["channel_id"]
        )
        op.create_index(
            "idx_discovered_videos_published", "discovered_videos", ["published_at"]
        )
        op.create_index(
            "idx_discovered_videos_live", "discovered_videos", ["platform", "is_live"]
        )

    # 3. live_sessions
    if "live_sessions" not in existing_tables:
        op.create_table(
            "live_sessions",
            sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
            sa.Column("platform", sa.Text(), nullable=False),
            sa.Column(
                "channel_id",
                sa.BigInteger(),
                sa.ForeignKey("platform_channels.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("external_session_id", sa.Text(), nullable=True),
            sa.Column("title", sa.Text(), nullable=True),
            sa.Column(
                "game_name",
                sa.Text(),
                nullable=True,
                server_default="Grand Theft Auto VI",
            ),
            sa.Column("viewer_count", sa.BigInteger(), nullable=True),
            sa.Column(
                "started_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.func.now(),
            ),
            sa.Column(
                "last_seen_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.func.now(),
            ),
            sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column(
                "is_active",
                sa.Boolean(),
                nullable=False,
                server_default=sa.text("true"),
            ),
        )
        op.create_index(
            "idx_live_sessions_channel_active",
            "live_sessions",
            ["channel_id", "is_active"],
        )
        op.create_index(
            "idx_live_sessions_platform_active",
            "live_sessions",
            ["platform", "is_active"],
        )
        op.create_index(
            "idx_live_sessions_ext_session",
            "live_sessions",
            ["platform", "external_session_id"],
        )


def downgrade() -> None:
    op.drop_table("live_sessions", if_exists=True)
    op.drop_table("discovered_videos", if_exists=True)
    op.drop_table("discovery_runs", if_exists=True)
