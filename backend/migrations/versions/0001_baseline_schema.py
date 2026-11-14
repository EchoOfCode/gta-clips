"""0001 baseline schema

Revision ID: 0001_baseline
Revises:
Create Date: 2026-11-15 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.engine.reflection import Inspector

# revision identifiers, used by Alembic.
revision: str = "0001_baseline"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = Inspector.from_engine(bind)
    existing_tables = set(inspector.get_table_names())

    # 1. creators
    if "creators" not in existing_tables:
        op.create_table(
            "creators",
            sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
            sa.Column("display_name", sa.Text(), nullable=False),
            sa.Column("contact_email", sa.Text(), nullable=True),
            sa.Column("notes", sa.Text(), nullable=True),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.func.now(),
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.func.now(),
            ),
        )

    # 2. platform_channels
    if "platform_channels" not in existing_tables:
        op.create_table(
            "platform_channels",
            sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
            sa.Column(
                "creator_id",
                sa.BigInteger(),
                sa.ForeignKey("creators.id", ondelete="SET NULL"),
                nullable=True,
            ),
            sa.Column("platform", sa.Text(), nullable=False),
            sa.Column("external_channel_id", sa.Text(), nullable=False),
            sa.Column("handle", sa.Text(), nullable=True),
            sa.Column("channel_url", sa.Text(), nullable=False),
            sa.Column("game_name", sa.Text(), nullable=True),
            sa.Column("current_title", sa.Text(), nullable=True),
            sa.Column(
                "is_live", sa.Boolean(), nullable=False, server_default=sa.text("false")
            ),
            sa.Column("viewer_count", sa.Integer(), nullable=True),
            sa.Column("language_code", sa.Text(), nullable=True),
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
                "platform", "external_channel_id", name="uq_platform_channel"
            ),
            sa.CheckConstraint(
                "viewer_count IS NULL OR viewer_count >= 0",
                name="chk_channel_viewer_count",
            ),
        )

    # 3. rights_grants
    if "rights_grants" not in existing_tables:
        op.create_table(
            "rights_grants",
            sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
            sa.Column(
                "creator_id",
                sa.BigInteger(),
                sa.ForeignKey("creators.id", ondelete="RESTRICT"),
                nullable=False,
            ),
            sa.Column("platform", sa.Text(), nullable=False),
            sa.Column("scope", sa.Text(), nullable=False),
            sa.Column("evidence_uri", sa.Text(), nullable=True),
            sa.Column("status", sa.Text(), nullable=False, server_default="pending"),
            sa.Column(
                "creator_footage_allowed",
                sa.Boolean(),
                nullable=False,
                server_default=sa.text("false"),
            ),
            sa.Column(
                "commercial_use_allowed",
                sa.Boolean(),
                nullable=False,
                server_default=sa.text("false"),
            ),
            sa.Column(
                "game_content_clearance",
                sa.Text(),
                nullable=False,
                server_default="unverified",
            ),
            sa.Column("granted_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.func.now(),
            ),
            sa.CheckConstraint(
                "status IN ('pending', 'active', 'expired', 'revoked', 'rejected')",
                name="chk_rights_grant_status",
            ),
            sa.CheckConstraint(
                "game_content_clearance IN ('unverified', 'approved', 'restricted', 'rejected')",
                name="chk_game_content_clearance",
            ),
            sa.CheckConstraint(
                "expires_at IS NULL OR granted_at IS NULL OR expires_at > granted_at",
                name="chk_grant_expiry_after_grant",
            ),
        )
        op.create_index(
            "idx_rights_grants_creator_status",
            "rights_grants",
            ["creator_id", "status"],
        )

    # 4. media_assets
    if "media_assets" not in existing_tables:
        op.create_table(
            "media_assets",
            sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
            sa.Column(
                "creator_id",
                sa.BigInteger(),
                sa.ForeignKey("creators.id", ondelete="RESTRICT"),
                nullable=False,
            ),
            sa.Column(
                "rights_grant_id",
                sa.BigInteger(),
                sa.ForeignKey("rights_grants.id", ondelete="RESTRICT"),
                nullable=False,
            ),
            sa.Column("platform", sa.Text(), nullable=False),
            sa.Column("source_url", sa.Text(), nullable=True),
            sa.Column("storage_path", sa.Text(), nullable=False),
            sa.Column("sha256", sa.Text(), nullable=True),
            sa.Column("duration_seconds", sa.Numeric(12, 3), nullable=True),
            sa.Column("status", sa.Text(), nullable=False, server_default="received"),
            sa.Column(
                "received_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.func.now(),
            ),
            sa.Column("retention_until", sa.DateTime(timezone=True), nullable=True),
            sa.CheckConstraint(
                "status IN ('received', 'processing', 'processed', 'quarantined', 'deleted')",
                name="chk_media_asset_status",
            ),
        )
        op.create_index("idx_media_assets_status", "media_assets", ["status"])

    # 5. candidate_moments
    if "candidate_moments" not in existing_tables:
        op.create_table(
            "candidate_moments",
            sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
            sa.Column(
                "asset_id",
                sa.BigInteger(),
                sa.ForeignKey("media_assets.id", ondelete="RESTRICT"),
                nullable=False,
            ),
            sa.Column("start_seconds", sa.Numeric(12, 3), nullable=False),
            sa.Column("end_seconds", sa.Numeric(12, 3), nullable=False),
            sa.Column("category", sa.Text(), nullable=True),
            sa.Column("score", sa.Numeric(5, 2), nullable=True),
            sa.Column("explanation", sa.Text(), nullable=True),
            sa.Column("model_version", sa.Text(), nullable=True),
            sa.Column("status", sa.Text(), nullable=False, server_default="candidate"),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.func.now(),
            ),
            sa.CheckConstraint("start_seconds >= 0", name="chk_moment_start_positive"),
            sa.CheckConstraint(
                "end_seconds > start_seconds", name="chk_moment_end_after_start"
            ),
            sa.CheckConstraint(
                "score IS NULL OR (score >= 0 AND score <= 100)",
                name="chk_moment_score_range",
            ),
            sa.CheckConstraint(
                "status IN ('candidate', 'approved', 'rejected', 'duplicate', 'needs_review')",
                name="chk_moment_status",
            ),
        )

    # 6. edited_clips
    if "edited_clips" not in existing_tables:
        op.create_table(
            "edited_clips",
            sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
            sa.Column(
                "candidate_moment_id",
                sa.BigInteger(),
                sa.ForeignKey("candidate_moments.id", ondelete="RESTRICT"),
                nullable=False,
            ),
            sa.Column("storage_path", sa.Text(), nullable=False),
            sa.Column("thumbnail_path", sa.Text(), nullable=True),
            sa.Column("title", sa.Text(), nullable=True),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("duration_seconds", sa.Numeric(12, 3), nullable=True),
            sa.Column("edit_profile", sa.Text(), nullable=True),
            sa.Column(
                "quality_status", sa.Text(), nullable=False, server_default="pending"
            ),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.func.now(),
            ),
            sa.CheckConstraint(
                "quality_status IN ('pending', 'passed', 'failed', 'needs_review')",
                name="chk_clip_quality_status",
            ),
        )

    # 7. publishing_jobs
    if "publishing_jobs" not in existing_tables:
        op.create_table(
            "publishing_jobs",
            sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
            sa.Column(
                "edited_clip_id",
                sa.BigInteger(),
                sa.ForeignKey("edited_clips.id", ondelete="RESTRICT"),
                nullable=False,
            ),
            sa.Column("platform", sa.Text(), nullable=False, server_default="youtube"),
            sa.Column("destination_channel_id", sa.Text(), nullable=True),
            sa.Column("scheduled_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("external_video_id", sa.Text(), nullable=True),
            sa.Column(
                "status", sa.Text(), nullable=False, server_default="pending_review"
            ),
            sa.Column("error_message", sa.Text(), nullable=True),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.func.now(),
            ),
            sa.CheckConstraint(
                "status IN ('pending_review', 'approved', 'scheduled', 'uploading', 'published', 'failed', 'cancelled')",
                name="chk_publishing_job_status",
            ),
        )
        op.create_index(
            "idx_publishing_jobs_status_schedule",
            "publishing_jobs",
            ["status", "scheduled_at"],
        )

    # 8. Trigger for publishing rights gate (PostgreSQL only)
    if bind.dialect.name == "postgresql":
        op.execute("""
            CREATE OR REPLACE FUNCTION enforce_publish_rights_gate()
            RETURNS TRIGGER AS $$
            DECLARE
                grant_record rights_grants%ROWTYPE;
            BEGIN
                IF NEW.status IN ('approved', 'scheduled', 'uploading', 'published') THEN
                    SELECT rg.* INTO grant_record
                    FROM edited_clips ec
                    JOIN candidate_moments cm ON cm.id = ec.candidate_moment_id
                    JOIN media_assets ma ON ma.id = cm.asset_id
                    JOIN rights_grants rg ON rg.id = ma.rights_grant_id
                    WHERE ec.id = NEW.edited_clip_id;

                    IF NOT FOUND
                       OR grant_record.status <> 'active'
                       OR grant_record.creator_footage_allowed IS NOT TRUE
                       OR grant_record.commercial_use_allowed IS NOT TRUE
                       OR grant_record.game_content_clearance <> 'approved'
                       OR grant_record.revoked_at IS NOT NULL
                       OR (grant_record.expires_at IS NOT NULL AND grant_record.expires_at <= NOW()) THEN
                        RAISE EXCEPTION 'Publishing blocked: required active commercial rights clearance is missing';
                    END IF;
                END IF;
                RETURN NEW;
            END;
            $$ LANGUAGE plpgsql;

            DROP TRIGGER IF EXISTS trg_enforce_publish_rights_gate ON publishing_jobs;
            CREATE TRIGGER trg_enforce_publish_rights_gate
            BEFORE INSERT OR UPDATE OF status, edited_clip_id ON publishing_jobs
            FOR EACH ROW EXECUTE FUNCTION enforce_publish_rights_gate();
        """)


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute(
            "DROP TRIGGER IF EXISTS trg_enforce_publish_rights_gate ON publishing_jobs;"
        )
        op.execute("DROP FUNCTION IF EXISTS enforce_publish_rights_gate();")

    op.drop_table("publishing_jobs", if_exists=True)
    op.drop_table("edited_clips", if_exists=True)
    op.drop_table("candidate_moments", if_exists=True)
    op.drop_table("media_assets", if_exists=True)
    op.drop_table("rights_grants", if_exists=True)
    op.drop_table("platform_channels", if_exists=True)
    op.drop_table("creators", if_exists=True)
