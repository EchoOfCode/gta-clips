import logging
import re
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

import httpx

from app.discovery.base import (
    AuthenticationError,
    DiscoveryProvider,
    DiscoveryProviderError,
    QuotaExceededError,
    RateLimitError,
    retry_with_backoff,
)
from app.discovery.schemas import (
    DiscoveredChannelMetadata,
    DiscoveredLiveStreamMetadata,
    DiscoveredVideoMetadata,
    DiscoveryFilter,
    DiscoveryResult,
    ProviderStatusEnum,
    ProviderStatusResponse,
)

logger = logging.getLogger(__name__)

# Regex for parsing ISO 8601 durations like PT1H23M45S or PT45S
ISO8601_DURATION_RE = re.compile(
    r"^P(?:(?P<days>\d+)D)?(?:T(?:(?P<hours>\d+)H)?(?:(?P<minutes>\d+)M)?(?:(?P<seconds>\d+(?:\.\d+)?)S)?)?$"
)


def parse_iso8601_duration(duration_str: str | None) -> Decimal | None:
    """Converts ISO 8601 duration (PT1H2M30S) into Decimal total seconds."""
    if not duration_str:
        return None
    match = ISO8601_DURATION_RE.match(duration_str)
    if not match:
        return None
    parts = match.groupdict()
    total_seconds = Decimal(0)
    if parts.get("days"):
        total_seconds += Decimal(parts["days"]) * 86400
    if parts.get("hours"):
        total_seconds += Decimal(parts["hours"]) * 3600
    if parts.get("minutes"):
        total_seconds += Decimal(parts["minutes"]) * 60
    if parts.get("seconds"):
        total_seconds += Decimal(parts["seconds"])
    return total_seconds


class YouTubeDiscoveryProvider(DiscoveryProvider):
    """Discovery adapter using the official Google YouTube Data API v3."""

    name = "youtube"

    def __init__(
        self,
        api_key: str,
        base_url: str = "https://www.googleapis.com/youtube/v3",
        timeout: float = 10.0,
        client: httpx.Client | None = None,
    ) -> None:
        self.api_key = api_key.strip() if api_key else ""
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._client = client

    @property
    def is_configured(self) -> bool:
        return bool(self.api_key)

    def _get_client(self) -> httpx.Client:
        if self._client is not None:
            return self._client
        return httpx.Client(timeout=self.timeout)

    def get_status(self) -> ProviderStatusResponse:
        if not self.is_configured:
            return ProviderStatusResponse(
                provider=self.name,
                status=ProviderStatusEnum.NOT_CONFIGURED,
                supported=True,
                configured=False,
                details="YOUTUBE_API_KEY environment variable is not set.",
            )
        return ProviderStatusResponse(
            provider=self.name,
            status=ProviderStatusEnum.CONFIGURED,
            supported=True,
            configured=True,
            details="YouTube Data API v3 configured with API key.",
        )

    def _handle_api_error(self, response: httpx.Response) -> None:
        try:
            data = response.json()
            error_obj = data.get("error", {})
            message = error_obj.get("message", response.text)
            errors = error_obj.get("errors", [])
            for err in errors:
                reason = err.get("reason", "")
                if reason in ("quotaExceeded", "dailyLimitExceeded"):
                    raise QuotaExceededError(
                        self.name, f"YouTube API quota exceeded: {message}"
                    )
                if reason in ("keyInvalid", "badRequest"):
                    raise AuthenticationError(
                        self.name, f"YouTube API authentication error: {message}"
                    )
        except (ValueError, KeyError):
            message = response.text

        if response.status_code == 429:
            raise RateLimitError(self.name, f"YouTube rate limit reached: {message}")
        if response.status_code in (401, 403):
            raise AuthenticationError(
                self.name,
                f"YouTube authorization error ({response.status_code}): {message}",
            )

        raise DiscoveryProviderError(
            self.name,
            f"YouTube API returned HTTP {response.status_code}: {message}",
            status_code=response.status_code,
        )

    def discover_videos(self, filter_params: DiscoveryFilter) -> DiscoveryResult:
        if not self.is_configured:
            raise DiscoveryProviderError(
                self.name, "Cannot run discovery: YouTube API is not configured."
            )

        client = self._get_client()
        quota_used = 0

        # Step 1: Perform search call (costs 100 quota units)
        search_params: dict[str, Any] = {
            "part": "snippet",
            "q": filter_params.query,
            "type": "video",
            "maxResults": min(filter_params.max_results, 50),
            "key": self.api_key,
        }
        if filter_params.is_live_only:
            search_params["eventType"] = "live"
        if filter_params.page_token:
            search_params["pageToken"] = filter_params.page_token

        def _do_search() -> httpx.Response:
            resp = client.get(f"{self.base_url}/search", params=search_params)
            if resp.is_error:
                self._handle_api_error(resp)
            return resp

        search_resp = retry_with_backoff(_do_search)
        quota_used += 100
        search_data = search_resp.json()

        items = search_data.get("items", [])
        next_page_token = search_data.get("nextPageToken")

        video_ids = [
            item["id"]["videoId"]
            for item in items
            if "id" in item and "videoId" in item["id"]
        ]
        if not video_ids:
            return DiscoveryResult(
                provider=self.name,
                videos=[],
                live_streams=[],
                channels=[],
                next_page_token=next_page_token,
                quota_used=quota_used,
                raw_response=search_data,
            )

        # Step 2: Fetch detailed video metadata (costs 1 quota unit for up to 50 videos)
        video_params: dict[str, Any] = {
            "part": "snippet,contentDetails,statistics,liveStreamingDetails",
            "id": ",".join(video_ids),
            "key": self.api_key,
        }

        def _do_videos() -> httpx.Response:
            resp = client.get(f"{self.base_url}/videos", params=video_params)
            if resp.is_error:
                self._handle_api_error(resp)
            return resp

        videos_resp = retry_with_backoff(_do_videos)
        quota_used += 1
        videos_data = videos_resp.json()

        discovered_videos: list[DiscoveredVideoMetadata] = []
        discovered_streams: list[DiscoveredLiveStreamMetadata] = []
        discovered_channels: dict[str, DiscoveredChannelMetadata] = {}

        for v in videos_data.get("items", []):
            v_id = v.get("id", "")
            snippet = v.get("snippet", {})
            content_details = v.get("contentDetails", {})
            stats = v.get("statistics", {})
            live_details = v.get("liveStreamingDetails")

            channel_id = snippet.get("channelId", "")
            channel_title = snippet.get("channelTitle", "")
            channel_url = (
                f"https://www.youtube.com/channel/{channel_id}" if channel_id else ""
            )

            title = snippet.get("title", "")
            description = snippet.get("description", "")
            source_url = f"https://www.youtube.com/watch?v={v_id}"
            thumbs = snippet.get("thumbnails", {})
            thumb_url = (
                thumbs.get("high", {}).get("url")
                or thumbs.get("medium", {}).get("url")
                or thumbs.get("default", {}).get("url")
            )

            published_str = snippet.get("publishedAt")
            published_at = None
            if published_str:
                try:
                    published_at = datetime.fromisoformat(
                        published_str.replace("Z", "+00:00")
                    )
                except ValueError:
                    published_at = None

            duration_sec = parse_iso8601_duration(content_details.get("duration"))
            view_count = (
                int(stats.get("viewCount"))
                if stats.get("viewCount", "").isdigit()
                else None
            )
            like_count = (
                int(stats.get("likeCount"))
                if stats.get("likeCount", "").isdigit()
                else None
            )
            is_live = snippet.get("liveBroadcastContent") == "live"

            # Register channel
            if channel_id and channel_id not in discovered_channels:
                discovered_channels[channel_id] = DiscoveredChannelMetadata(
                    platform=self.name,
                    external_channel_id=channel_id,
                    display_name=channel_title or channel_id,
                    channel_url=channel_url,
                    game_name="Grand Theft Auto VI",
                    current_title=title,
                    is_live=is_live,
                    viewer_count=int(live_details.get("concurrentViewers"))
                    if (
                        live_details
                        and str(live_details.get("concurrentViewers", "")).isdigit()
                    )
                    else None,
                    language_code=snippet.get("defaultAudioLanguage")
                    or snippet.get("defaultLanguage"),
                )

            # Register video
            discovered_videos.append(
                DiscoveredVideoMetadata(
                    platform=self.name,
                    external_video_id=v_id,
                    external_channel_id=channel_id,
                    channel_title=channel_title,
                    channel_url=channel_url,
                    title=title,
                    description=description,
                    source_url=source_url,
                    thumbnail_url=thumb_url,
                    published_at=published_at,
                    duration_seconds=duration_sec,
                    view_count=view_count,
                    like_count=like_count,
                    is_live=is_live,
                    raw_metadata={
                        "snippet": snippet,
                        "contentDetails": content_details,
                        "statistics": stats,
                        "liveStreamingDetails": live_details,
                    },
                )
            )

            # If live, register stream
            if is_live:
                started_at = published_at or datetime.now(UTC)
                if live_details and live_details.get("actualStartTime"):
                    try:
                        started_at = datetime.fromisoformat(
                            live_details["actualStartTime"].replace("Z", "+00:00")
                        )
                    except ValueError:
                        pass

                concurrent = (
                    int(live_details.get("concurrentViewers"))
                    if (
                        live_details
                        and str(live_details.get("concurrentViewers", "")).isdigit()
                    )
                    else None
                )

                discovered_streams.append(
                    DiscoveredLiveStreamMetadata(
                        platform=self.name,
                        external_session_id=v_id,
                        external_channel_id=channel_id,
                        channel_title=channel_title,
                        channel_url=channel_url,
                        title=title,
                        game_name="Grand Theft Auto VI",
                        viewer_count=concurrent,
                        started_at=started_at,
                        language_code=snippet.get("defaultAudioLanguage"),
                        raw_metadata={"liveStreamingDetails": live_details},
                    )
                )

        return DiscoveryResult(
            provider=self.name,
            videos=discovered_videos,
            live_streams=discovered_streams,
            channels=list(discovered_channels.values()),
            next_page_token=next_page_token,
            quota_used=quota_used,
            raw_response=videos_data,
        )

    def discover_live_streams(self, filter_params: DiscoveryFilter) -> DiscoveryResult:
        live_filter = filter_params.model_copy(update={"is_live_only": True})
        return self.discover_videos(live_filter)

    def test_connection(self) -> dict[str, Any]:
        if not self.is_configured:
            return {"status": "unconfigured", "message": "YOUTUBE_API_KEY is not set."}

        client = self._get_client()
        params = {
            "part": "snippet",
            "q": "Grand Theft Auto VI",
            "type": "video",
            "maxResults": 1,
            "key": self.api_key,
        }
        try:
            resp = client.get(f"{self.base_url}/search", params=params)
            if resp.is_error:
                self._handle_api_error(resp)
            return {
                "status": "ok",
                "message": "Successfully connected to YouTube Data API v3.",
            }
        except DiscoveryProviderError as exc:
            return {
                "status": "error",
                "message": str(exc),
                "status_code": exc.status_code,
            }
