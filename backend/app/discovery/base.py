import abc
import random
import time
from collections.abc import Callable
from typing import Any, TypeVar

import httpx

from app.discovery.schemas import (
    DiscoveryFilter,
    DiscoveryResult,
    ProviderStatusResponse,
)

T = TypeVar("T")


class DiscoveryProviderError(Exception):
    """Base exception for provider discovery errors."""

    def __init__(
        self, provider: str, message: str, status_code: int | None = None
    ) -> None:
        super().__init__(f"[{provider}] {message}")
        self.provider = provider
        self.message = message
        self.status_code = status_code


class QuotaExceededError(DiscoveryProviderError):
    """Raised when provider API quota has been exhausted."""


class RateLimitError(DiscoveryProviderError):
    """Raised when provider rate limit is encountered."""

    def __init__(
        self, provider: str, message: str, retry_after: float | None = None
    ) -> None:
        super().__init__(provider, message, status_code=429)
        self.retry_after = retry_after


class AuthenticationError(DiscoveryProviderError):
    """Raised when credentials are invalid or expired."""


def retry_with_backoff(
    fn: Callable[[], T],
    max_retries: int = 3,
    initial_delay: float = 0.5,
    backoff_factor: float = 2.0,
    jitter: bool = True,
) -> T:
    """Execute a function with exponential backoff and jitter for transient errors."""
    delay = initial_delay
    last_exc: Exception | None = None

    for attempt in range(max_retries):
        try:
            return fn()
        except (httpx.TimeoutException, httpx.NetworkError) as exc:
            last_exc = exc
            if attempt == max_retries - 1:
                raise
            sleep_time = delay * (1 + (random.random() * 0.2 if jitter else 0))
            time.sleep(sleep_time)
            delay *= backoff_factor
        except httpx.HTTPStatusError as exc:
            last_exc = exc
            # Transient server errors (500, 502, 503, 504) or rate limit (429)
            if exc.response.status_code in (429, 500, 502, 503, 504):
                if attempt == max_retries - 1:
                    raise
                retry_header = exc.response.headers.get("Retry-After")
                if retry_header and retry_header.isdigit():
                    sleep_time = float(retry_header)
                else:
                    sleep_time = delay * (1 + (random.random() * 0.2 if jitter else 0))
                time.sleep(sleep_time)
                delay *= backoff_factor
            else:
                raise

    if last_exc:
        raise last_exc
    raise RuntimeError("Unexpected retry loop termination")


class DiscoveryProvider(abc.ABC):
    """Abstract base class for all platform discovery adapters."""

    name: str

    @property
    @abc.abstractmethod
    def is_configured(self) -> bool:
        """Returns True if required credentials are present."""

    @abc.abstractmethod
    def get_status(self) -> ProviderStatusResponse:
        """Returns the current status of the provider."""

    @abc.abstractmethod
    def discover_live_streams(self, filter_params: DiscoveryFilter) -> DiscoveryResult:
        """Discover active live streams matching the filter."""

    @abc.abstractmethod
    def discover_videos(self, filter_params: DiscoveryFilter) -> DiscoveryResult:
        """Discover public videos matching the filter."""

    @abc.abstractmethod
    def test_connection(self) -> dict[str, Any]:
        """Test API connectivity and credential validity."""
