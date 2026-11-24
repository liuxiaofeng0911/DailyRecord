"""登录/注册限流。

优先使用 Redis；不可用时退化为进程内滑动窗口计数（设计文档 17.1）。
"""

import logging
import threading
import time
from collections import defaultdict, deque

from ..config import settings

logger = logging.getLogger(__name__)


class _MemoryLimiter:
    def __init__(self) -> None:
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def allow(self, key: str, limit: int, window_seconds: int) -> bool:
        now = time.time()
        with self._lock:
            bucket = self._hits[key]
            while bucket and bucket[0] <= now - window_seconds:
                bucket.popleft()
            if len(bucket) >= limit:
                return False
            bucket.append(now)
            return True


_memory = _MemoryLimiter()
_redis_client = None
_redis_checked = False


def _redis():
    global _redis_client, _redis_checked
    if _redis_checked:
        return _redis_client
    _redis_checked = True
    if not settings.redis_url:
        return None
    try:
        import redis

        client = redis.Redis.from_url(settings.redis_url, decode_responses=True, socket_timeout=1)
        client.ping()
        _redis_client = client
    except Exception as exc:  # pragma: no cover - 依赖外部服务
        logger.warning("Redis 不可用，限流退化为进程内计数: %s", exc)
        _redis_client = None
    return _redis_client


def allow(key: str, limit: int, window_seconds: int) -> bool:
    client = _redis()
    if client is None:
        return _memory.allow(key, limit, window_seconds)
    try:
        redis_key = f"dr:rate:{key}"
        pipe = client.pipeline()
        pipe.incr(redis_key)
        pipe.expire(redis_key, window_seconds, nx=True)
        count, _ = pipe.execute()
        return int(count) <= limit
    except Exception:  # pragma: no cover
        return _memory.allow(key, limit, window_seconds)


def reset() -> None:
    """清空进程内计数（测试与运维使用）。"""
    with _memory._lock:
        _memory._hits.clear()
