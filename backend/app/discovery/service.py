import json
import logging
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.discovery.base import DiscoveryProviderError
from app.discovery.registry import ProviderRegistry
from app.discovery.schemas import (
    DiscoveryFilter,
    DiscoveryResult,
)
from app.models.core import PlatformChannel
from app.models.discovery import DiscoveredVideo, DiscoveryRun, LiveSession

logger = logging.getLogger(__name__)


class DiscoveryService:
    """Orchestrates metadata discovery across providers and safe PostgreSQL persistence."""

    def __init__(self, registry: ProviderRegistry) -> None:
        self.registry = registry

    def run_provider_discovery(
        self,
        db: Session,
        provider_name: str,
        filter_params: DiscoveryFilter | None = None,
        trigger_type: str = "manual",
    ) -> DiscoveryRun:
        """Execute a discovery run for a specific provider and persist results."""
        provider = self.registry.get(provider_name)
        if not provider:
            raise DiscoveryProviderError(
                provider_name,
                f"Provider '{provider_name}' is not registered or supported.",
            )

        if not provider.is_configured:
            raise DiscoveryProviderError(
                provider_name,
                f"Provider '{provider_name}' is not configured with credentials.",
            )

        flt = filter_params or DiscoveryFilter()

        # Step 1: Record running discovery run
        run_record = DiscoveryRun(
            provider=provider.name,
            trigger_type=trigger_type,
            status="running",
            query=flt.query,
            started_at=datetime.now(UTC),
        )
        db.add(run_record)
        db.commit()
        db.refresh(run_record)

        try:
            # Step 2: Query provider for video and live metadata
            result: DiscoveryResult = provider.discover_videos(flt)

            # Also discover live streams if not already covered
            if not flt.is_live_only and provider.name == "twitch":
                live_res = provider.discover_live_streams(flt)
                result.live_streams.extend(live_res.live_streams)
                result.channels.extend(live_res.channels)
                result.quota_used += live_res.quota_used

            items_found = len(result.videos) + len(result.live_streams)
            items_upserted = 0

            # Step 3: Upsert channels
            channel_id_map: dict[str, int] = {}
            for ch in result.channels:
                stmt = select(PlatformChannel).where(
                    PlatformChannel.platform == ch.platform,
                    PlatformChannel.external_channel_id == ch.external_channel_id,
                )
                existing_ch = db.scalars(stmt).first()
                if existing_ch:
                    existing_ch.display_name = ch.display_name  # type: ignore[attr-defined]
                    existing_ch.current_title = ch.current_title
                    existing_ch.is_live = ch.is_live
                    existing_ch.viewer_count = ch.viewer_count
                    existing_ch.last_seen_at = datetime.now(UTC)
                    db.flush()
                    channel_id_map[ch.external_channel_id] = existing_ch.id
                else:
                    new_ch = PlatformChannel(
                        platform=ch.platform,
                        external_channel_id=ch.external_channel_id,
                        handle=ch.handle,
                        channel_url=ch.channel_url,
                        game_name=ch.game_name,
                        current_title=ch.current_title,
                        is_live=ch.is_live,
                        viewer_count=ch.viewer_count,
                        language_code=ch.language_code,
                    )
                    db.add(new_ch)
                    db.flush()
                    channel_id_map[ch.external_channel_id] = new_ch.id
                items_upserted += 1

            # Step 4: Upsert discovered videos
            for vid in result.videos:
                ch_id = channel_id_map.get(vid.external_channel_id)
                stmt = select(DiscoveredVideo).where(
                    DiscoveredVideo.platform == vid.platform,
                    DiscoveredVideo.external_video_id == vid.external_video_id,
                )
                existing_vid = db.scalars(stmt).first()
                raw_json = json.dumps(vid.raw_metadata) if vid.raw_metadata else None

                if existing_vid:
                    existing_vid.title = vid.title
                    existing_vid.description = vid.description
                    existing_vid.view_count = vid.view_count
                    existing_vid.like_count = vid.like_count
                    existing_vid.is_live = vid.is_live
                    existing_vid.raw_metadata = raw_json
                    existing_vid.last_seen_at = datetime.now(UTC)
                else:
                    new_vid = DiscoveredVideo(
                        platform=vid.platform,
                        external_video_id=vid.external_video_id,
                        channel_id=ch_id,
                        external_channel_id=vid.external_channel_id,
                        channel_title=vid.channel_title,
                        title=vid.title,
                        description=vid.description,
                        source_url=vid.source_url,
                        thumbnail_url=vid.thumbnail_url,
                        published_at=vid.published_at,
                        duration_seconds=vid.duration_seconds,
                        view_count=vid.view_count,
                        like_count=vid.like_count,
                        is_live=vid.is_live,
                        raw_metadata=raw_json,
                    )
                    db.add(new_vid)
                items_upserted += 1

            # Step 5: Upsert live sessions
            for stream in result.live_streams:
                ch_id = channel_id_map.get(stream.external_channel_id)
                if ch_id:
                    stmt = select(LiveSession).where(
                        LiveSession.platform == stream.platform,
                        LiveSession.channel_id == ch_id,
                        LiveSession.is_active.is_(True),
                    )
                    active_session = db.scalars(stmt).first()
                    if active_session:
                        active_session.viewer_count = stream.viewer_count
                        active_session.title = stream.title
                        active_session.last_seen_at = datetime.now(UTC)
                    else:
                        new_session = LiveSession(
                            platform=stream.platform,
                            channel_id=ch_id,
                            external_session_id=stream.external_session_id,
                            title=stream.title,
                            game_name=stream.game_name,
                            viewer_count=stream.viewer_count,
                            started_at=stream.started_at,
                            is_active=True,
                        )
                        db.add(new_session)
                    items_upserted += 1

            # Step 6: Finalize run record
            run_record.status = "completed"
            run_record.items_found = items_found
            run_record.items_upserted = items_upserted
            run_record.quota_used = result.quota_used
            run_record.completed_at = datetime.now(UTC)
            run_record.details = json.dumps(
                {
                    "videos_count": len(result.videos),
                    "streams_count": len(result.live_streams),
                    "channels_count": len(result.channels),
                }
            )
            db.commit()
            db.refresh(run_record)
            return run_record

        except Exception as exc:
            db.rollback()
            logger.error(
                "Discovery run failed for %s: %s", provider_name, exc, exc_info=True
            )
            run_record.status = "failed"
            run_record.error_message = str(exc)
            run_record.completed_at = datetime.now(UTC)
            db.add(run_record)
            db.commit()
            db.refresh(run_record)
            raise
