from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from app.models.core import (
    CandidateMoment,
    Creator,
    EditedClip,
    MediaAsset,
    RightsGrant,
)
from app.rights import (
    RightsGateError,
    assert_publishing_allowed,
    validate_rights_grant_record,
    verify_asset_rights,
    verify_clip_for_publishing,
)
from sqlalchemy.orm import Session


def test_valid_rights_grant():
    grant = RightsGrant(
        creator_id=1,
        platform="youtube",
        scope="full_gameplay_and_voice",
        status="active",
        creator_footage_allowed=True,
        commercial_use_allowed=True,
        game_content_clearance="approved",
        granted_at=datetime.now(UTC) - timedelta(days=5),
        expires_at=datetime.now(UTC) + timedelta(days=365),
    )
    is_valid, reason = validate_rights_grant_record(grant)
    assert is_valid
    assert reason is None


def test_inactive_grant_rejections():
    for bad_status in ("pending", "expired", "revoked", "rejected"):
        grant = RightsGrant(
            creator_id=1,
            platform="youtube",
            scope="full",
            status=bad_status,
            creator_footage_allowed=True,
            commercial_use_allowed=True,
            game_content_clearance="approved",
        )
        is_valid, reason = validate_rights_grant_record(grant)
        assert not is_valid
        assert bad_status in (reason or "")


def test_missing_footage_or_commercial_permission():
    grant_no_footage = RightsGrant(
        creator_id=1,
        platform="youtube",
        scope="full",
        status="active",
        creator_footage_allowed=False,
        commercial_use_allowed=True,
        game_content_clearance="approved",
    )
    is_valid, reason = validate_rights_grant_record(grant_no_footage)
    assert not is_valid
    assert "creator footage" in (reason or "")

    grant_no_commercial = RightsGrant(
        creator_id=1,
        platform="youtube",
        scope="full",
        status="active",
        creator_footage_allowed=True,
        commercial_use_allowed=False,
        game_content_clearance="approved",
    )
    is_valid, reason = validate_rights_grant_record(grant_no_commercial)
    assert not is_valid
    assert "commercial" in (reason or "")


def test_unapproved_game_content_clearance():
    grant = RightsGrant(
        creator_id=1,
        platform="youtube",
        scope="full",
        status="active",
        creator_footage_allowed=True,
        commercial_use_allowed=True,
        game_content_clearance="unverified",
    )
    is_valid, reason = validate_rights_grant_record(grant)
    assert not is_valid
    assert "game content clearance" in (reason or "")


def test_revoked_or_expired_grant():
    grant_revoked = RightsGrant(
        creator_id=1,
        platform="youtube",
        scope="full",
        status="active",
        creator_footage_allowed=True,
        commercial_use_allowed=True,
        game_content_clearance="approved",
        revoked_at=datetime.now(UTC) - timedelta(hours=1),
    )
    is_valid, reason = validate_rights_grant_record(grant_revoked)
    assert not is_valid
    assert "revoked" in (reason or "")

    grant_expired = RightsGrant(
        creator_id=1,
        platform="youtube",
        scope="full",
        status="active",
        creator_footage_allowed=True,
        commercial_use_allowed=True,
        game_content_clearance="approved",
        expires_at=datetime.now(UTC) - timedelta(minutes=10),
    )
    is_valid, reason = validate_rights_grant_record(grant_expired)
    assert not is_valid
    assert "expired" in (reason or "")


def test_end_to_end_publishing_rights_verification(db_session: Session):
    # 1. Create creator
    creator = Creator(
        display_name="Authorized Streamer", contact_email="streamer@example.com"
    )
    db_session.add(creator)
    db_session.flush()

    # 2. Create active verified rights grant
    grant = RightsGrant(
        creator_id=creator.id,
        platform="youtube",
        scope="commercial_shorts",
        status="active",
        creator_footage_allowed=True,
        commercial_use_allowed=True,
        game_content_clearance="approved",
        granted_at=datetime.now(UTC),
        expires_at=datetime.now(UTC) + timedelta(days=90),
    )
    db_session.add(grant)
    db_session.flush()

    # 3. Create media asset
    asset = MediaAsset(
        creator_id=creator.id,
        rights_grant_id=grant.id,
        platform="youtube",
        storage_path="/media/incoming/test.mp4",
        status="processed",
    )
    db_session.add(asset)
    db_session.flush()

    # Verify asset rights
    is_valid, reason = verify_asset_rights(db_session, asset.id)
    assert is_valid
    assert reason is None

    # 4. Create candidate moment & edited clip
    moment = CandidateMoment(
        asset_id=asset.id,
        start_seconds=Decimal("10.0"),
        end_seconds=Decimal("45.0"),
        score=Decimal("92.5"),
        status="approved",
    )
    db_session.add(moment)
    db_session.flush()

    clip = EditedClip(
        candidate_moment_id=moment.id,
        storage_path="/media/rendered/clip1.mp4",
        quality_status="passed",
    )
    db_session.add(clip)
    db_session.commit()

    # Verification passes
    is_clip_valid, _ = verify_clip_for_publishing(db_session, clip.id)
    assert is_clip_valid
    assert_publishing_allowed(db_session, clip.id)

    # Now revoke grant and verify publishing is immediately blocked
    grant.revoked_at = datetime.now(UTC)
    db_session.commit()

    is_clip_valid, block_reason = verify_clip_for_publishing(db_session, clip.id)
    assert not is_clip_valid
    assert "revoked" in (block_reason or "")

    with pytest.raises(RightsGateError, match="blocked by rights gate"):
        assert_publishing_allowed(db_session, clip.id)
