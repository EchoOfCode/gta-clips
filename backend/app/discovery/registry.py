import logging

from app.config import Settings, get_settings
from app.discovery.base import DiscoveryProvider
from app.discovery.schemas import ProviderStatusEnum, ProviderStatusResponse
from app.discovery.twitch import TwitchDiscoveryProvider
from app.discovery.youtube import YouTubeDiscoveryProvider

logger = logging.getLogger(__name__)

# Known future connectors that are not yet officially implemented
KNOWN_FUTURE_CONNECTORS = ["kick", "tiktok", "twitter", "rumble"]


class ProviderRegistry:
    """Registry maintaining active discovery provider adapters."""

    def __init__(self) -> None:
        self._providers: dict[str, DiscoveryProvider] = {}

    def register(self, provider: DiscoveryProvider) -> None:
        """Register a supported provider adapter."""
        self._providers[provider.name.lower()] = provider

    def get(self, name: str) -> DiscoveryProvider | None:
        """Retrieve a registered provider by name."""
        return self._providers.get(name.lower())

    def is_supported(self, name: str) -> bool:
        """Checks if a platform is registered as supported."""
        return name.lower() in self._providers

    def get_status(self, name: str) -> ProviderStatusResponse:
        """Get the status of a specific provider."""
        lower_name = name.lower()
        if lower_name in self._providers:
            return self._providers[lower_name].get_status()

        if lower_name in KNOWN_FUTURE_CONNECTORS:
            return ProviderStatusResponse(
                provider=lower_name,
                status=ProviderStatusEnum.UNSUPPORTED,
                supported=False,
                configured=False,
                details=f"Platform '{lower_name}' is planned for future official API integration, but no authorized adapter is currently registered.",
            )

        return ProviderStatusResponse(
            provider=lower_name,
            status=ProviderStatusEnum.UNSUPPORTED,
            supported=False,
            configured=False,
            details=f"Platform '{lower_name}' is unsupported.",
        )

    def list_statuses(self) -> list[ProviderStatusResponse]:
        """List statuses for all registered providers and recognized future platforms."""
        statuses: list[ProviderStatusResponse] = []
        for provider in self._providers.values():
            statuses.append(provider.get_status())

        for future_p in KNOWN_FUTURE_CONNECTORS:
            if future_p not in self._providers:
                statuses.append(self.get_status(future_p))

        return statuses


def create_default_registry(settings: Settings | None = None) -> ProviderRegistry:
    """Factory creating a default ProviderRegistry initialized from current Settings."""
    cfg = settings or get_settings()
    registry = ProviderRegistry()

    # YouTube adapter
    youtube_provider = YouTubeDiscoveryProvider(
        api_key=cfg.youtube_api_key,
        base_url=cfg.youtube_api_base_url,
    )
    registry.register(youtube_provider)

    # Twitch adapter
    twitch_provider = TwitchDiscoveryProvider(
        client_id=cfg.twitch_client_id,
        client_secret=cfg.twitch_client_secret,
        token_url=cfg.twitch_token_url,
        helix_base_url=cfg.twitch_helix_base_url,
    )
    registry.register(twitch_provider)

    return registry
