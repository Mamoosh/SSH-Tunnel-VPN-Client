import time
from collections import deque


class Stats:
    """Tracks live speed, session totals, uptime and a rolling history."""

    def __init__(self, history_len=60):
        self.reset()
        self.history = deque(maxlen=history_len)

    def reset(self):
        self.start_time = None
        self.session_down = 0
        self.session_up = 0
        self._last_down = 0
        self._last_up = 0
        self._last_t = None
        self.speed_down = 0
        self.speed_up = 0
        self.history = deque(maxlen=60)

    def begin(self):
        self.reset()
        self.start_time = time.time()
        self._last_t = self.start_time

    def tick(self, total_down, total_up):
        """Call ~once per second with cumulative counter values."""
        now = time.time()
        self.session_down = total_down
        self.session_up = total_up
        if self._last_t is not None:
            dt = max(0.001, now - self._last_t)
            self.speed_down = max(0, (total_down - self._last_down) / dt)
            self.speed_up = max(0, (total_up - self._last_up) / dt)
        self._last_down = total_down
        self._last_up = total_up
        self._last_t = now
        self.history.append((self.speed_down, self.speed_up))

    def uptime(self):
        if not self.start_time:
            return 0
        return int(time.time() - self.start_time)

    def avg_speed_mbps(self):
        """Average download speed of session in MB/s."""
        up = self.uptime()
        if up <= 0:
            return 0.0
        return (self.session_down / up) / (1024 * 1024)
