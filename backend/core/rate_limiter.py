import asyncio
import time
from collections import defaultdict


class SlidingWindowRateLimiter:

    def __init__(self):
        self._buckets: dict[str, list[float]] = defaultdict(list)
        self._lock = asyncio.Lock()

    async def check(self, key: str, max_requests: int, window_seconds: int) -> tuple[bool, int, int]:
        async with self._lock:
            self._cleanup(key, window_seconds)
            current = len(self._buckets[key])
            if current >= max_requests:
                oldest = self._buckets[key][0]
                retry_after = int(window_seconds - (time.time() - oldest))
                return False, 0, max(1, retry_after)
            self._buckets[key].append(time.time())
            remaining = max_requests - current - 1
            return True, remaining, 0

    async def get_remaining(self, key: str, max_requests: int, window_seconds: int) -> int:
        async with self._lock:
            self._cleanup(key, window_seconds)
            return max(0, max_requests - len(self._buckets[key]))

    def _cleanup(self, key: str, window_seconds: int):
        now = time.time()
        cutoff = now - window_seconds
        self._buckets[key] = [t for t in self._buckets[key] if t > cutoff]

    def reset(self):
        self._buckets.clear()
