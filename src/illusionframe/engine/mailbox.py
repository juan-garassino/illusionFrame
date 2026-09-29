"""Latest-wins hand-off between the mutation worker and the UI thread.

A Queue(1) can deadlock a worker blocked on put() during shutdown; a slot that overwrites
cannot, and the UI only ever wants the newest result anyway.
"""

from __future__ import annotations

import threading
from typing import Any


class Mailbox:
    def __init__(self):
        self._cond = threading.Condition()
        self._item: Any = None
        self._has = False
        self.closed = False

    def put(self, item: Any) -> None:
        with self._cond:
            self._item, self._has = item, True
            self._cond.notify_all()

    def get(self, timeout: float | None = 0.0) -> Any:
        """The newest item (removing it), or None if nothing arrives within `timeout`."""
        with self._cond:
            if not self._has and timeout:
                self._cond.wait_for(lambda: self._has or self.closed, timeout=timeout)
            if not self._has:
                return None
            item, self._item, self._has = self._item, None, False
            return item

    def close(self) -> None:
        with self._cond:
            self.closed = True
            self._cond.notify_all()
