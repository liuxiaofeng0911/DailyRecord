"""Twitter Snowflake ID 生成器。

ID 为 64 位整数，接口序列化为字符串，避免前端精度丢失。
"""

import os
import threading
import time

_EPOCH = 1735689600000  # 2025-01-01 00:00:00 UTC+8
_SEQUENCE_BITS = 12
_WORKER_BITS = 10
_MAX_SEQUENCE = (1 << _SEQUENCE_BITS) - 1


class Snowflake:
    def __init__(self, worker_id: int = 1) -> None:
        self.worker_id = worker_id & ((1 << _WORKER_BITS) - 1)
        self._lock = threading.Lock()
        self._last_ts = -1
        self._sequence = 0

    def next_id(self) -> int:
        with self._lock:
            ts = int(time.time() * 1000)
            if ts < _EPOCH:
                ts = _EPOCH
            if ts == self._last_ts:
                self._sequence = (self._sequence + 1) & _MAX_SEQUENCE
                if self._sequence == 0:
                    while ts <= self._last_ts:
                        ts = int(time.time() * 1000)
            else:
                self._sequence = 0
            self._last_ts = ts
            return ((ts - _EPOCH) << (_WORKER_BITS + _SEQUENCE_BITS)) | (
                self.worker_id << _SEQUENCE_BITS
            ) | self._sequence


_generator = Snowflake(worker_id=int(os.getenv("SNOWFLAKE_WORKER_ID", "1")))


def next_id() -> int:
    return _generator.next_id()
