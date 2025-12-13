"""Rate limiting utilities for API calls."""

import asyncio
import time
from typing import Any


class RateLimiter:
    """Simple rate limiter for API calls."""

    def __init__(self, config: dict[str, Any]):
        """Initialize the rate limiter.

        Args:
            config: Rate limit configuration with 'per_source_delays' and 'global_delay'.
        """
        self.delays = config.get("per_source_delays", {})
        self.global_delay = config.get("global_delay", 1.0)
        self.last_call: dict[str, float] = {}
        self._lock = asyncio.Lock()

    async def wait(self, source: str) -> None:
        """Wait appropriate time before next call.

        Args:
            source: The source identifier to rate limit.
        """
        async with self._lock:
            delay = self.delays.get(source, self.global_delay)
            last = self.last_call.get(source, 0)
            elapsed = time.time() - last

            if elapsed < delay:
                await asyncio.sleep(delay - elapsed)

            self.last_call[source] = time.time()

    def get_delay(self, source: str) -> float:
        """Get the delay for a specific source.

        Args:
            source: The source identifier.

        Returns:
            The delay in seconds.
        """
        return self.delays.get(source, self.global_delay)
