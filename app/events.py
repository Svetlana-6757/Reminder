import queue
import threading


class Hub:
    """Простой бродкаст для SSE (события на открытые страницы)."""

    def __init__(self):
        self._queues = set()
        self._lock = threading.Lock()

    def subscribe(self):
        q = queue.Queue(maxsize=50)
        with self._lock:
            self._queues.add(q)
        return q

    def unsubscribe(self, q):
        with self._lock:
            self._queues.discard(q)

    def publish(self, message):
        with self._lock:
            for q in list(self._queues):
                try:
                    q.put_nowait(message)
                except queue.Full:
                    pass


hub = Hub()
