from decimal import Decimal

import httpx
import pytest
from app.discovery.base import (
    AuthenticationError,
    DiscoveryProviderError,
    QuotaExceededError,
)
from app.discovery.schemas import DiscoveryFilter, ProviderStatusEnum
from app.discovery.youtube import YouTubeDiscoveryProvider, parse_iso8601_duration


def test_parse_iso8601_duration():
    assert parse_iso8601_duration("PT15M33S") == Decimal(933)
    assert parse_iso8601_duration("PT1H2M10S") == Decimal(3730)
    assert parse_iso8601_duration("PT45S") == Decimal(45)
    assert parse_iso8601_duration("P1DT2H") == Decimal(93600)
    assert parse_iso8601_duration("") is None
    assert parse_iso8601_duration(None) is None


def test_youtube_unconfigured():
    provider = YouTubeDiscoveryProvider(api_key="")
    assert not provider.is_configured
    status = provider.get_status()
    assert status.status == ProviderStatusEnum.NOT_CONFIGURED
    assert not status.configured

    with pytest.raises(DiscoveryProviderError, match="not configured"):
        provider.discover_videos(DiscoveryFilter())


def test_youtube_discover_videos_success():
    def mock_transport(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if "/search" in url:
            return httpx.Response(
                200,
                json={
                    "items": [
                        {"id": {"kind": "youtube#video", "videoId": "yt_vid_123"}},
                    ],
                    "nextPageToken": "NEXT_PAGE_TOKEN_ABC",
                },
            )
        elif "/videos" in url:
            return httpx.Response(
                200,
                json={
                    "items": [
                        {
                            "id": "yt_vid_123",
                            "snippet": {
                                "title": "GTA VI Official Gameplay Breakdown",
                                "description": "Analyzing Vice City map features.",
                                "channelId": "ch_rockstar_456",
                                "channelTitle": "Rockstar Intel",
                                "publishedAt": "2026-11-14T12:00:00Z",
                                "liveBroadcastContent": "none",
                                "thumbnails": {
                                    "high": {
                                        "url": "https://img.youtube.com/vi/yt_vid_123/hqdefault.jpg"
                                    }
                                },
                            },
                            "contentDetails": {"duration": "PT12M30S"},
                            "statistics": {"viewCount": "45000", "likeCount": "3200"},
                        }
                    ]
                },
            )
        return httpx.Response(404)

    client = httpx.Client(transport=httpx.MockTransport(mock_transport))
    provider = YouTubeDiscoveryProvider(api_key="valid-key", client=client)

    result = provider.discover_videos(DiscoveryFilter(query="GTA VI"))
    assert len(result.videos) == 1
    assert result.quota_used == 101  # 100 for search + 1 for videos
    assert result.next_page_token == "NEXT_PAGE_TOKEN_ABC"

    vid = result.videos[0]
    assert vid.external_video_id == "yt_vid_123"
    assert vid.title == "GTA VI Official Gameplay Breakdown"
    assert vid.duration_seconds == Decimal(750)
    assert vid.view_count == 45000
    assert vid.like_count == 3200
    assert not vid.is_live

    assert len(result.channels) == 1
    ch = result.channels[0]
    assert ch.external_channel_id == "ch_rockstar_456"
    assert ch.display_name == "Rockstar Intel"


def test_youtube_quota_exceeded():
    def mock_transport(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            403,
            json={
                "error": {
                    "errors": [
                        {
                            "reason": "quotaExceeded",
                            "message": "Daily quota limit reached.",
                        }
                    ],
                    "code": 403,
                    "message": "Daily quota limit reached.",
                }
            },
        )

    client = httpx.Client(transport=httpx.MockTransport(mock_transport))
    provider = YouTubeDiscoveryProvider(api_key="valid-key", client=client)

    with pytest.raises(QuotaExceededError, match="quota exceeded"):
        provider.discover_videos(DiscoveryFilter())


def test_youtube_auth_error():
    def mock_transport(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            400,
            json={
                "error": {
                    "errors": [
                        {"reason": "keyInvalid", "message": "API key not valid."}
                    ],
                    "code": 400,
                    "message": "API key not valid.",
                }
            },
        )

    client = httpx.Client(transport=httpx.MockTransport(mock_transport))
    provider = YouTubeDiscoveryProvider(api_key="bad-key", client=client)

    with pytest.raises(AuthenticationError, match="authentication error"):
        provider.discover_videos(DiscoveryFilter())


def test_youtube_empty_results():
    def mock_transport(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"items": []})

    client = httpx.Client(transport=httpx.MockTransport(mock_transport))
    provider = YouTubeDiscoveryProvider(api_key="valid-key", client=client)

    result = provider.discover_videos(DiscoveryFilter(query="NoMatchingQuery12345"))
    assert len(result.videos) == 0
    assert result.quota_used == 100
