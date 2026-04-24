"""
Thread-safe port pool for allocating RTP UDP ports.

Each concurrent SIP call needs a unique port pair (RTP + RTCP).
Includes a cooldown period after release to avoid stale-packet crossover
when a port is reused immediately.
"""

import threading
import time

from .config import RTP_PORT_START, RTP_PORT_END
from src.core.logger import logger, setup_logging
setup_logging()


class PortPool:
    """Thread-safe pool of UDP ports for RTP sockets."""

    COOLDOWN_SECONDS = 5  # minimum seconds before a released port can be reused

    def __init__(self, start: int, end: int):
        # Step by 2 so port+1 is free for RTCP
        # Map port → release_timestamp (0.0 = immediately eligible)
        self._free: dict[int, float] = {p: 0.0 for p in range(start, end, 2)}
        self._lock = threading.Lock()
        logger.info(f"[PortPool] Ready with {len(self._free)} ports ({start}-{end})")

    def acquire(self) -> int:
        with self._lock:
            now = time.time()
            eligible = [
                p for p, released_at in self._free.items()
                if now - released_at >= self.COOLDOWN_SECONDS
            ]
            if not eligible:
                raise RuntimeError(
                    f"No free RTP ports in {RTP_PORT_START}-{RTP_PORT_END}. "
                    "Increase RTP_PORT_END or reduce concurrent calls."
                )
            port = min(eligible)
            del self._free[port]
            logger.debug(f"[PortPool] Acquired {port}. Remaining: {len(self._free)}")
            return port

    def release(self, port: int) -> None:
        with self._lock:
            self._free[port] = time.time()  # start cooldown
            logger.debug(f"[PortPool] Released {port}. Remaining: {len(self._free)}")


_port_pool: PortPool | None = None
_port_pool_lock = threading.Lock()


def get_port_pool() -> PortPool:
    global _port_pool
    with _port_pool_lock:
        if _port_pool is None:
            _port_pool = PortPool(RTP_PORT_START, RTP_PORT_END)
        return _port_pool
