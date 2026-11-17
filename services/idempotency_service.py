import time
import threading
from typing import Dict

class IdempotencyService:
    def __init__(self, ttl_seconds: int = 86400):
        self._seen: Dict[str, float] = {}
        self._lock = threading.Lock()
        self.ttl_seconds = ttl_seconds

        self._eviction_thread = threading.Thread(target=self._evict_expired, daemon=True)
        self._eviction_thread.start()

    def claim(self, packet_hash: str) -> bool:
        with self._lock:
            if packet_hash in self._seen:
                return False
            self._seen[packet_hash] = time.time()
            return True

    def size(self) -> int:
        with self._lock:
            return len(self._seen)

    def clear(self):
        with self._lock:
            self._seen.clear()

    def _evict_expired(self):
        while True:
            time.sleep(60)
            cutoff = time.time() - self.ttl_seconds
            with self._lock:
                expired = [k for k, v in self._seen.items() if v < cutoff]
                for k in expired:
                    del self._seen[k]