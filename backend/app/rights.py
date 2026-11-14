from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.core import (
    CandidateMoment,
    EditedClip,
    MediaAsset,
    RightsGrant,
)


class RightsGateError(Exception):
    """Raised when media ingestion or publishing fails rights clearance validation."""


def validate_rights_grant_record(grant: RightsGrant) -> tuple[bool, str | None]:
    """
    Validates that a rights grant satisfies all legal prerequisites for media usage:
    1. Status must be active (not pending, expired, revoked, or rejected)
    2. Creator footage permission must be explicitly true
    3. Commercial use permission must be explicitly true
    4. Game-content clearance must be approved (Rockstar/publisher terms compliance)
    5. Grant must not be revoked
    6. Expiration timestamp (if present) must be in the future
    """
    now = datetime.now(UTC)

    if grant.status != "active":
        return (
            False,
            f"Rights grant {grant.id} status is '{grant.status}', expected 'active'",
        )

    if not grant.creator_footage_allowed:
        return False, f"Rights grant {grant.id} does not permit creator footage reuse"

    if not grant.commercial_use_allowed:
        return False, f"Rights grant {grant.id} does not permit commercial use"

    if grant.game_content_clearance != "approved":
        return False, (
            f"Rights grant {grant.id} game content clearance is '{grant.game_content_clearance}', "
            "expected 'approved'"
        )

    if grant.revoked_at is not None:
        return (
            False,
            f"Rights grant {grant.id} was revoked at {grant.revoked_at.isoformat()}",
        )

    if grant.expires_at is not None:
        exp = grant.expires_at
        if exp.tzinfo is None:
            exp = exp.replace(tzinfo=UTC)
        if exp <= now:
            return (
                False,
                f"Rights grant {grant.id} expired at {grant.expires_at.isoformat()}",
            )

    return True, None


def verify_asset_rights(db: Session, asset_id: int) -> tuple[bool, str | None]:
    """Verify that a media asset is bound to a matching creator and valid rights grant."""
    asset = db.get(MediaAsset, asset_id)
    if not asset:
        return False, f"Media asset {asset_id} not found"

    grant = db.get(RightsGrant, asset.rights_grant_id)
    if not grant:
        return False, f"No rights grant found for media asset {asset_id}"

    if grant.creator_id != asset.creator_id:
        return False, (
            f"Creator mismatch: asset {asset_id} creator {asset.creator_id} "
            f"does not match grant creator {grant.creator_id}"
        )

    return validate_rights_grant_record(grant)


def verify_clip_for_publishing(
    db: Session, edited_clip_id: int
) -> tuple[bool, str | None]:
    """
    Pre-publishing verification gate.
    Mirrors the PostgreSQL enforce_publish_rights_gate trigger in application code
    to provide clear, structured exceptions before attempting database writes.
    """
    stmt = (
        select(RightsGrant)
        .join(MediaAsset, MediaAsset.rights_grant_id == RightsGrant.id)
        .join(CandidateMoment, CandidateMoment.asset_id == MediaAsset.id)
        .join(EditedClip, EditedClip.candidate_moment_id == CandidateMoment.id)
        .where(EditedClip.id == edited_clip_id)
    )
    grant = db.scalars(stmt).first()

    if not grant:
        return (
            False,
            f"No associated rights grant found for edited clip {edited_clip_id}",
        )

    return validate_rights_grant_record(grant)


def assert_publishing_allowed(db: Session, edited_clip_id: int) -> None:
    """Raises RightsGateError if publishing rights cannot be verified."""
    is_valid, reason = verify_clip_for_publishing(db, edited_clip_id)
    if not is_valid:
        raise RightsGateError(f"Publishing blocked by rights gate: {reason}")
