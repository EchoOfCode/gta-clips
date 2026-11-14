from app.config import Settings
from app.discovery.registry import ProviderRegistry, create_default_registry
from app.discovery.schemas import ProviderStatusEnum
from app.discovery.youtube import YouTubeDiscoveryProvider


def test_registry_registration_and_lookup():
    reg = ProviderRegistry()
    yt = YouTubeDiscoveryProvider(api_key="mock-key")
    reg.register(yt)

    assert reg.is_supported("youtube")
    assert reg.is_supported("YOUTUBE")
    assert reg.get("youtube") is yt
    assert not reg.is_supported("unknown_platform")
    assert reg.get("unknown_platform") is None


def test_registry_unsupported_future_connectors():
    reg = ProviderRegistry()
    kick_status = reg.get_status("kick")
    assert kick_status.status == ProviderStatusEnum.UNSUPPORTED
    assert not kick_status.supported
    assert "planned for future" in (kick_status.details or "")


def test_registry_default_factory():
    settings = Settings(
        database_url="sqlite:///:memory:",
        youtube_api_key="yt-key",
        twitch_client_id="t-id",
        twitch_client_secret="t-secret",
    )
    reg = create_default_registry(settings)
    statuses = {s.provider: s for s in reg.list_statuses()}

    assert "youtube" in statuses
    assert statuses["youtube"].status == ProviderStatusEnum.CONFIGURED
    assert "twitch" in statuses
    assert statuses["twitch"].status == ProviderStatusEnum.CONFIGURED
    assert "kick" in statuses
    assert statuses["kick"].status == ProviderStatusEnum.UNSUPPORTED
