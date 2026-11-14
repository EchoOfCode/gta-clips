from decimal import Decimal

import httpx
import pytest
from app.discovery.base import (
    DiscoveryProviderError,
    RateLimitError,
)
from app.discovery.schemas import DiscoveryFilter, ProviderStatusEnum
from app.discovery.twitch import TwitchDiscoveryProvider


def test_twitch_unconfigured():
    provider = TwitchDiscoveryProvider(client_id="", client_secret="")
    assert not provider.is_configured
    status = provider.get_status()
    assert status.status == ProviderStatusEnum.NOT_CONFIGURED

    with pytest.raises(DiscoveryProviderError, match="not configured"):
        provider.discover_videos(DiscoveryFilter())


def test_twitch_oauth_and_streams_discovery():
    auth_called = 0

    def mock_transport(request: httpx.Request) -> httpx.Response:
        nonlocal auth_called
        url = str(request.url)

        if "/oauth2/token" in url:
            auth_called += 1
            return httpx.Response(
                200,
                json={
                    "access_token": "twitch_mock_token_999",
                    "expires_in": 3600,
                    "token_type": "bearer",
                },
            )
        elif "/games" in url:
            return httpx.Response(
                200,
                json={"data": [{"id": "1046473138", "name": "Grand Theft Auto VI"}]},
            )
        elif "/streams" in url:
            assert request.headers["Authorization"] == "Bearer twitch_mock_token_999"
            assert request.headers["Client-Id"] == "mock_client_id"
            return httpx.Response(
                200,
                json={
                    "data": [
                        {
                            "id": "stream_live_101",
                            "user_id": "twitch_user_777",
                            "user_login": "gta_speedrunner",
                            "user_name": "GTA Speedrunner",
                            "game_id": "1046473138",
                            "game_name": "Grand Theft Auto VI",
                            "type": "live",
                            "title": "Vice City Mission 1 World Record Pace!",
                            "viewer_count": 1420,
                            "started_at": "2026-11-14T10:00:00Z",
                            "language": "en",
                        }
                    ],
                    "pagination": {"cursor": "CURSOR_XYZ"},
                },
            )
        return httpx.Response(404)

    client = httpx.Client(transport=httpx.MockTransport(mock_transport))
    provider = TwitchDiscoveryProvider(
        client_id="mock_client_id",
        client_secret="mock_client_secret",
        client=client,
    )

    result = provider.discover_live_streams(
        DiscoveryFilter(query="Grand Theft Auto VI")
    )
    assert auth_called == 1
    assert len(result.live_streams) == 1
    assert result.next_page_token == "CURSOR_XYZ"

    stream = result.live_streams[0]
    assert stream.external_session_id == "stream_live_101"
    assert stream.external_channel_id == "twitch_user_777"
    assert stream.viewer_count == 1420
    assert stream.channel_url == "https://www.twitch.tv/gta_speedrunner"

    assert len(result.channels) == 1
    ch = result.channels[0]
    assert ch.external_channel_id == "twitch_user_777"
    assert ch.is_live is True
    assert ch.handle == "gta_speedrunner"


def test_twitch_clips_discovery():
    def mock_transport(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if "/oauth2/token" in url:
            return httpx.Response(
                200, json={"access_token": "token", "expires_in": 3600}
            )
        elif "/games" in url:
            return httpx.Response(
                200,
                json={"data": [{"id": "1046473138", "name": "Grand Theft Auto VI"}]},
            )
        elif "/clips" in url:
            return httpx.Response(
                200,
                json={
                    "data": [
                        {
                            "id": "HilariousMomentViceCity",
                            "url": "https://clips.twitch.tv/HilariousMomentViceCity",
                            "broadcaster_id": "streamer_555",
                            "broadcaster_name": "TopStreamer",
                            "creator_name": "ClipperPro",
                            "title": "Insane car flip across neon bridge",
                            "view_count": 8900,
                            "created_at": "2026-11-14T15:30:00Z",
                            "duration": 30.5,
                        }
                    ],
                    "pagination": {},
                },
            )
        return httpx.Response(404)

    client = httpx.Client(transport=httpx.MockTransport(mock_transport))
    provider = TwitchDiscoveryProvider(
        client_id="cid", client_secret="csec", client=client
    )

    result = provider.discover_videos(DiscoveryFilter(query="Grand Theft Auto VI"))
    assert len(result.videos) == 1
    vid = result.videos[0]
    assert vid.external_video_id == "HilariousMomentViceCity"
    assert vid.duration_seconds == Decimal("30.5")
    assert vid.view_count == 8900
    assert vid.channel_title == "TopStreamer"


def test_twitch_rate_limit_error():
    def mock_transport(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if "/oauth2/token" in url:
            return httpx.Response(
                200, json={"access_token": "token", "expires_in": 3600}
            )
        return httpx.Response(
            429,
            headers={"Ratelimit-Reset": "1731630000", "Ratelimit-Remaining": "0"},
            text="Too Many Requests",
        )

    client = httpx.Client(transport=httpx.MockTransport(mock_transport))
    provider = TwitchDiscoveryProvider(
        client_id="cid", client_secret="csec", client=client
    )

    with pytest.raises(RateLimitError):
        provider.discover_live_streams(DiscoveryFilter())
