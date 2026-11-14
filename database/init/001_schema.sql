-- Initial schema. PostgreSQL runs this automatically only when its data directory is empty.
CREATE TABLE IF NOT EXISTS creators (
    id BIGSERIAL PRIMARY KEY,
    display_name TEXT NOT NULL,
    contact_email TEXT,
    notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS platform_channels (
    id BIGSERIAL PRIMARY KEY,
    creator_id BIGINT REFERENCES creators(id) ON DELETE SET NULL,
    platform TEXT NOT NULL,
    external_channel_id TEXT NOT NULL,
    handle TEXT,
    channel_url TEXT NOT NULL,
    game_name TEXT,
    current_title TEXT,
    is_live BOOLEAN NOT NULL DEFAULT FALSE,
    viewer_count INTEGER,
    language_code TEXT,
    first_discovered_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (platform, external_channel_id),
    CHECK (viewer_count IS NULL OR viewer_count >= 0)
);

CREATE TABLE IF NOT EXISTS rights_grants (
    id BIGSERIAL PRIMARY KEY,
    creator_id BIGINT NOT NULL REFERENCES creators(id) ON DELETE RESTRICT,
    platform TEXT NOT NULL,
    scope TEXT NOT NULL,
    evidence_uri TEXT,
    status TEXT NOT NULL DEFAULT 'pending',
    creator_footage_allowed BOOLEAN NOT NULL DEFAULT FALSE,
    commercial_use_allowed BOOLEAN NOT NULL DEFAULT FALSE,
    game_content_clearance TEXT NOT NULL DEFAULT 'unverified',
    granted_at TIMESTAMPTZ,
    expires_at TIMESTAMPTZ,
    revoked_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CHECK (status IN ('pending', 'active', 'expired', 'revoked', 'rejected')),
    CHECK (game_content_clearance IN ('unverified', 'approved', 'restricted', 'rejected')),
    CHECK (expires_at IS NULL OR granted_at IS NULL OR expires_at > granted_at)
);

CREATE INDEX IF NOT EXISTS idx_rights_grants_creator_status ON rights_grants (creator_id, status);

CREATE TABLE IF NOT EXISTS media_assets (
    id BIGSERIAL PRIMARY KEY,
    creator_id BIGINT NOT NULL REFERENCES creators(id) ON DELETE RESTRICT,
    rights_grant_id BIGINT NOT NULL REFERENCES rights_grants(id) ON DELETE RESTRICT,
    platform TEXT NOT NULL,
    source_url TEXT,
    storage_path TEXT NOT NULL,
    sha256 TEXT,
    duration_seconds NUMERIC(12,3),
    status TEXT NOT NULL DEFAULT 'received',
    received_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    retention_until TIMESTAMPTZ,
    CHECK (status IN ('received', 'processing', 'processed', 'quarantined', 'deleted'))
);

CREATE INDEX IF NOT EXISTS idx_media_assets_status ON media_assets (status);

CREATE TABLE IF NOT EXISTS candidate_moments (
    id BIGSERIAL PRIMARY KEY,
    asset_id BIGINT NOT NULL REFERENCES media_assets(id) ON DELETE RESTRICT,
    start_seconds NUMERIC(12,3) NOT NULL,
    end_seconds NUMERIC(12,3) NOT NULL,
    category TEXT,
    score NUMERIC(5,2),
    explanation TEXT,
    model_version TEXT,
    status TEXT NOT NULL DEFAULT 'candidate',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CHECK (start_seconds >= 0),
    CHECK (end_seconds > start_seconds),
    CHECK (score IS NULL OR (score >= 0 AND score <= 100)),
    CHECK (status IN ('candidate', 'approved', 'rejected', 'duplicate', 'needs_review'))
);

CREATE TABLE IF NOT EXISTS edited_clips (
    id BIGSERIAL PRIMARY KEY,
    candidate_moment_id BIGINT NOT NULL REFERENCES candidate_moments(id) ON DELETE RESTRICT,
    storage_path TEXT NOT NULL,
    thumbnail_path TEXT,
    title TEXT,
    description TEXT,
    duration_seconds NUMERIC(12,3),
    edit_profile TEXT,
    quality_status TEXT NOT NULL DEFAULT 'pending',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CHECK (quality_status IN ('pending', 'passed', 'failed', 'needs_review'))
);

CREATE TABLE IF NOT EXISTS publishing_jobs (
    id BIGSERIAL PRIMARY KEY,
    edited_clip_id BIGINT NOT NULL REFERENCES edited_clips(id) ON DELETE RESTRICT,
    platform TEXT NOT NULL DEFAULT 'youtube',
    destination_channel_id TEXT,
    scheduled_at TIMESTAMPTZ,
    published_at TIMESTAMPTZ,
    external_video_id TEXT,
    status TEXT NOT NULL DEFAULT 'pending_review',
    error_message TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CHECK (status IN ('pending_review', 'approved', 'scheduled', 'uploading', 'published', 'failed', 'cancelled'))
);

CREATE INDEX IF NOT EXISTS idx_publishing_jobs_status_schedule ON publishing_jobs (status, scheduled_at);

-- Publishing must only be enabled after both creator and game-content rights checks pass.
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
