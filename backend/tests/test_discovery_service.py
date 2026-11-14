from datetime import UTC, datetime
from decimal import Decimal

import pytest
from app.discovery.base import DiscoveryProvider, DiscoveryProviderError
from app.discovery.registry import ProviderRegistry
from app.discovery.schemas import (
    DiscoveredChannelMetadata,
    DiscoveredLiveStreamMetadata,
    DiscoveredVideoMetadata,
    DiscoveryFilter,
    DiscoveryResult,
    ProviderStatusEnum,
    ProviderStatusResponse,
)
from app.discovery.service import DiscoveryService
from app.models.core import PlatformChannel
from app.models.discovery import DiscoveredVideo, DiscoveryRun, LiveSession
from sqlalchemy import select
from sqlalchemy.orm import Session


class MockTestProvider(DiscoveryProvider):
    name = "mock_provider"

    def __init__(self, should_fail: bool = False):
        self.should_fail = should_fail

    @property
    def is_configured(self) -> bool:
        return True

    def get_status(self) -> ProviderStatusResponse:
        return ProviderStatusResponse(
            provider=self.name,
            status=ProviderStatusEnum.CONFIGURED,
            supported=True,
            configured=True,
        )

    def discover_videos(self, filter_params: DiscoveryFilter) -> DiscoveryResult:
        if self.should_fail:
            raise DiscoveryProviderError(
                self.name, "Simulated provider upstream failure"
            )

        ch = DiscoveredChannelMetadata(
            platform=self.name,
            external_channel_id="ch_100",
            display_name="Speedrun Master",
            channel_url="https://example.com/ch_100",
            is_live=True,
            viewer_count=500,
        )
        vid = DiscoveredVideoMetadata(
            platform=self.name,
            external_video_id="vid_200",
            external_channel_id="ch_100",
            title="GTA VI Helicopter Stunt",
            source_url="https://example.com/v/vid_200",
            duration_seconds=Decimal(60),
            view_count=1000,
        )
        stream = DiscoveredLiveStreamMetadata(
            platform=self.name,
            external_session_id="stream_300",
            external_channel_id="ch_100",
            channel_title="Speedrun Master",
            channel_url="https://example.com/ch_100",
            title="GTA VI 100% Run Live",
            viewer_count=500,
            started_at=datetime.now(UTC),
        )
        return DiscoveryResult(
            provider=self.name,
            videos=[vid],
            live_streams=[stream],
            channels=[ch],
            quota_used=5,
        )

    def discover_live_streams(self, filter_params: DiscoveryFilter) -> DiscoveryResult:
        return self.discover_videos(filter_params)

    def test_connection(self):
        return {"status": "ok"}


def test_discovery_service_successful_run_and_idempotency(db_session: Session):
    reg = ProviderRegistry()
    provider = MockTestProvider()
    reg.register(provider)

    service = DiscoveryService(reg)
    run_record = service.run_provider_discovery(db_session, "mock_provider")

    assert run_record.status == "completed"
    assert run_record.items_found == 2  # 1 video + 1 stream
    assert run_record.items_upserted == 3  # 1 channel + 1 video + 1 stream
    assert run_record.quota_used == 5

    # Verify database contents
    channels = list(db_session.scalars(select(PlatformChannel)).all())
    assert len(channels) == 1
    assert channels[0].external_channel_id == "ch_100"

    videos = list(db_session.scalars(select(DiscoveredVideo)).all())
    assert len(videos) == 1
    assert videos[0].external_video_id == "vid_200"

    sessions = list(db_session.scalars(select(LiveSession)).all())
    assert len(sessions) == 1
    assert sessions[0].external_session_id == "stream_300"

    # Re-running discovery should update existing records without creating duplicates
    run_record_2 = service.run_provider_discovery(db_session, "mock_provider")
    assert run_record_2.status == "completed"

    assert len(list(db_session.scalars(select(PlatformChannel)).all())) == 1
    assert len(list(db_session.scalars(select(DiscoveredVideo)).all())) == 1
    assert len(list(db_session.scalars(select(LiveSession)).all())) == 1


def test_discovery_service_failure_recording(db_session: Session):
    reg = ProviderRegistry()
    failing_provider = MockTestProvider(should_fail=True)
    reg.register(failing_provider)

    service = DiscoveryService(reg)
    with pytest.raises(
        DiscoveryProviderError, match="Simulated provider upstream failure"
    ):
        service.run_provider_discovery(db_session, "mock_provider")

    runs = list(db_session.scalars(select(DiscoveryRun)).all())
    assert len(runs) == 1
    assert runs[0].status == "failed"
    assert "Simulated provider upstream failure" in (runs[0].error_message or "")
