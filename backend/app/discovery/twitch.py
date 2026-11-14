import logging
import time
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

import httpx

from app.discovery.base import (
    AuthenticationError,
    DiscoveryProvider,
    DiscoveryProviderError,
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


class TwitchDiscoveryProvider(DiscoveryProvider):
    """Discovery adapter using the official Twitch Helix API and App Access Token OAuth flow."""

    name = "twitch"

    def __init__(
        self,
        client_id: str,
        client_secret: str,
        token_url: str = "https://id.twitch.tv/oauth2/token",
        helix_base_url: str = "https://api.twitch.tv/helix",
        timeout: float = 10.0,
        client: httpx.Client | None = None,
    ) -> None:
        self.client_id = client_id.strip() if client_id else ""
        self.client_secret = client_secret.strip() if client_secret else ""
        self.token_url = token_url
        self.helix_base_url = helix_base_url.rstrip("/")
        self.timeout = timeout
        self._client = client

        # Token caching state
        self._access_token: str | None = None
        self._token_expires_at: float = 0.0
        self._resolved_game_id: str | None = None

    @property
    def is_configured(self) -> bool:
        return bool(self.client_id and self.client_secret)

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
                details="TWITCH_CLIENT_ID and/or TWITCH_CLIENT_SECRET environment variables are not set.",
            )
        return ProviderStatusResponse(
            provider=self.name,
            status=ProviderStatusEnum.CONFIGURED,
            supported=True,
            configured=True,
            details="Twitch Helix API configured with Client ID & Secret.",
        )

    def _ensure_access_token(self) -> str:
        """Acquire or reuse an OAuth2 app access token using the Client Credentials flow."""
        now = time.time()
        # Return cached token if valid for at least 60 more seconds
        if self._access_token and now < (self._token_expires_at - 60):
            return self._access_token

        if not self.is_configured:
            raise AuthenticationError(
                self.name, "Twitch Client ID or Secret is missing."
            )

        client = self._get_client()
        payload = {
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "grant_type": "client_credentials",
        }

        try:
            resp = client.post(self.token_url, data=payload)
            if resp.status_code in (400, 401, 403):
                raise AuthenticationError(
                    self.name, f"Twitch token acquisition failed: {resp.text}"
                )
            resp.raise_for_status()
            data = resp.json()
            self._access_token = data["access_token"]
            expires_in = float(data.get("expires_in", 3600))
            self._token_expires_at = now + expires_in
            return self._access_token
        except httpx.HTTPError as exc:
            raise DiscoveryProviderError(
                self.name, f"Failed to connect to Twitch token endpoint: {exc}"
            )

    def _get_auth_headers(self) -> dict[str, str]:
        token = self._ensure_access_token()
        return {
            "Client-Id": self.client_id,
            "Authorization": f"Bearer {token}",
        }

    def _handle_response_errors(self, response: httpx.Response) -> None:
        remaining = response.headers.get("Ratelimit-Remaining")
        reset_header = response.headers.get("Ratelimit-Reset")

        if remaining == "0":
            logger.debug("Twitch Helix rate limit remaining is 0; reset at %s", reset_header)

        if response.status_code == 429:
            retry_after = 1.0
            if reset_header and reset_header.isdigit():
                retry_after = max(0.5, float(reset_header) - time.time())
            raise RateLimitError(
                self.name,
                f"Twitch Helix rate limit reached: {response.text}",
                retry_after=retry_after,
            )

        if response.status_code == 401:
            # Invalidate cached token on 401
            self._access_token = None
            raise AuthenticationError(
                self.name, f"Twitch authentication invalid or expired: {response.text}"
            )

        if response.is_error:
            raise DiscoveryProviderError(
                self.name,
                f"Twitch Helix API error {response.status_code}: {response.text}",
                status_code=response.status_code,
            )

    def resolve_game_id(self, game_name: str = "Grand Theft Auto VI") -> str | None:
        """Resolves the Twitch game/category ID for a given title."""
        if self._resolved_game_id:
            return self._resolved_game_id

        client = self._get_client()
        headers = self._get_auth_headers()
        params = {"name": game_name}

        def _fetch_game() -> httpx.Response:
            resp = client.get(
                f"{self.helix_base_url}/games", headers=headers, params=params
            )
            if resp.is_error:
                self._handle_response_errors(resp)
            return resp

        try:
            resp = retry_with_backoff(_fetch_game)
            data = resp.json().get("data", [])
            if data:
                self._resolved_game_id = data[0].get("id")
                return self._resolved_game_id
        except Exception as exc:
            logger.warning(
                "Failed to resolve Twitch game ID for '%s': %s", game_name, exc
            )

        return None

    def discover_live_streams(self, filter_params: DiscoveryFilter) -> DiscoveryResult:
        """Discovers live GTA VI streams from Twitch Helix."""
        if not self.is_configured:
            raise DiscoveryProviderError(
                self.name, "Cannot run discovery: Twitch API is not configured."
            )

        client = self._get_client()
        headers = self._get_auth_headers()

        game_id = self.resolve_game_id(filter_params.query)
        params: dict[str, Any] = {
            "first": min(filter_params.max_results, 100),
        }
        if game_id:
            params["game_id"] = game_id

        if filter_params.page_token:
            params["after"] = filter_params.page_token

        def _fetch_streams() -> httpx.Response:
            resp = client.get(
                f"{self.helix_base_url}/streams", headers=headers, params=params
            )
            if resp.is_error:
                self._handle_response_errors(resp)
            return resp

        resp = retry_with_backoff(_fetch_streams)
        data = resp.json()

        streams_data = data.get("data", [])
        pagination = data.get("pagination", {})
        next_cursor = pagination.get("cursor")

        discovered_streams: list[DiscoveredLiveStreamMetadata] = []
        discovered_channels: dict[str, DiscoveredChannelMetadata] = {}

        for stream in streams_data:
            user_id = stream.get("user_id", "")
            user_login = stream.get("user_login", "")
            user_name = stream.get("user_name", "")
            title = stream.get("title", "")
            viewer_count = stream.get("viewer_count")
            game_name = stream.get("game_name", "Grand Theft Auto VI")
            channel_url = f"https://www.twitch.tv/{user_login}" if user_login else ""
            stream_id = stream.get("id")

            started_at_str = stream.get("started_at")
            started_at = datetime.now(UTC)
            if started_at_str:
                try:
                    started_at = datetime.fromisoformat(
                        started_at_str.replace("Z", "+00:00")
                    )
                except ValueError:
                    pass

            if user_id and user_id not in discovered_channels:
                discovered_channels[user_id] = DiscoveredChannelMetadata(
                    platform=self.name,
                    external_channel_id=user_id,
                    handle=user_login,
                    display_name=user_name or user_login,
                    channel_url=channel_url,
                    game_name=game_name,
                    current_title=title,
                    is_live=True,
                    viewer_count=viewer_count,
                    language_code=stream.get("language"),
                )

            discovered_streams.append(
                DiscoveredLiveStreamMetadata(
                    platform=self.name,
                    external_session_id=stream_id,
                    external_channel_id=user_id,
                    channel_title=user_name or user_login,
                    channel_url=channel_url,
                    title=title,
                    game_name=game_name,
                    viewer_count=viewer_count,
                    started_at=started_at,
                    language_code=stream.get("language"),
                    raw_metadata=stream,
                )
            )

        return DiscoveryResult(
            provider=self.name,
            videos=[],
            live_streams=discovered_streams,
            channels=list(discovered_channels.values()),
            next_page_token=next_cursor,
            quota_used=1,
            raw_response=data,
        )

    def discover_videos(self, filter_params: DiscoveryFilter) -> DiscoveryResult:
        """Discovers GTA VI clips and video metadata via Twitch Helix."""
        if not self.is_configured:
            raise DiscoveryProviderError(
                self.name, "Cannot run discovery: Twitch API is not configured."
            )

        # If live only requested, delegate to discover_live_streams
        if filter_params.is_live_only:
            return self.discover_live_streams(filter_params)

        client = self._get_client()
        headers = self._get_auth_headers()

        game_id = self.resolve_game_id(filter_params.query)
        params: dict[str, Any] = {
            "first": min(filter_params.max_results, 100),
        }
        if game_id:
            params["game_id"] = game_id

        if filter_params.page_token:
            params["after"] = filter_params.page_token

        def _fetch_clips() -> httpx.Response:
            resp = client.get(
                f"{self.helix_base_url}/clips", headers=headers, params=params
            )
            if resp.is_error:
                self._handle_response_errors(resp)
            return resp

        resp = retry_with_backoff(_fetch_clips)
        data = resp.json()

        clips_data = data.get("data", [])
        pagination = data.get("pagination", {})
        next_cursor = pagination.get("cursor")

        discovered_videos: list[DiscoveredVideoMetadata] = []
        discovered_channels: dict[str, DiscoveredChannelMetadata] = {}

        for clip in clips_data:
            clip_id = clip.get("id", "")
            broadcaster_id = clip.get("broadcaster_id", "")
            broadcaster_name = clip.get("broadcaster_name", "")
            title = clip.get("title", "")
            source_url = clip.get("url", f"https://clips.twitch.tv/{clip_id}")
            thumb_url = clip.get("thumbnail_url")
            view_count = clip.get("view_count")
            duration_val = clip.get("duration")
            duration_sec = (
                Decimal(str(duration_val)) if duration_val is not None else None
            )

            created_at_str = clip.get("created_at")
            published_at = None
            if created_at_str:
                try:
                    published_at = datetime.fromisoformat(
                        created_at_str.replace("Z", "+00:00")
                    )
                except ValueError:
                    pass

            channel_url = (
                f"https://www.twitch.tv/{broadcaster_name.lower()}"
                if broadcaster_name
                else ""
            )

            if broadcaster_id and broadcaster_id not in discovered_channels:
                discovered_channels[broadcaster_id] = DiscoveredChannelMetadata(
                    platform=self.name,
                    external_channel_id=broadcaster_id,
                    handle=broadcaster_name.lower(),
                    display_name=broadcaster_name,
                    channel_url=channel_url,
                    game_name="Grand Theft Auto VI",
                    current_title=title,
                    is_live=False,
                    viewer_count=None,
                    language_code=clip.get("language"),
                )

            discovered_videos.append(
                DiscoveredVideoMetadata(
                    platform=self.name,
                    external_video_id=clip_id,
                    external_channel_id=broadcaster_id,
                    channel_title=broadcaster_name,
                    channel_url=channel_url,
                    title=title,
                    description=f"Twitch Clip created by {clip.get('creator_name', 'unknown')}",
                    source_url=source_url,
                    thumbnail_url=thumb_url,
                    published_at=published_at,
                    duration_seconds=duration_sec,
                    view_count=view_count,
                    like_count=None,
                    is_live=False,
                    raw_metadata=clip,
                )
            )

        return DiscoveryResult(
            provider=self.name,
            videos=discovered_videos,
            live_streams=[],
            channels=list(discovered_channels.values()),
            next_page_token=next_cursor,
            quota_used=1,
            raw_response=data,
        )

    def test_connection(self) -> dict[str, Any]:
        if not self.is_configured:
            return {
                "status": "unconfigured",
                "message": "TWITCH_CLIENT_ID and/or TWITCH_CLIENT_SECRET not set.",
            }

        try:
            self._ensure_access_token()
            return {
                "status": "ok",
                "message": "Successfully authenticated with Twitch Helix OAuth.",
            }
        except Exception as exc:
            return {"status": "error", "message": str(exc)}
