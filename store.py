"""The comments, in a JSON file.

A file and not a database so the demo has nothing to set up and the only code worth reading
is the moderation. Swap it for your own storage: nothing else depends on it.
"""

from __future__ import annotations

import json
import threading
from datetime import datetime, timezone
from pathlib import Path


class Comments:
    """Published and held comments, kept in one JSON file."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.lock = threading.Lock()

    def published(self) -> list[dict]:
        """Published comments, newest first."""
        return [c for c in reversed(self._read().values()) if c["status"] == "published"]

    def next_id(self) -> int:
        """The id the next comment will get, so the call to ToxicFilter can carry it."""
        return max((int(i) for i in self._read()), default=0) + 1

    def add(self, id: int, name: str, body: str, status: str, verdict_id: str | None) -> None:
        """Store a comment as `published` or `held`."""
        with self.lock:
            comments = self._read()
            comments[str(id)] = {
                "id": id,
                "name": name,
                "body": body,
                "status": status,
                "verdict": verdict_id,
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
            self._write(comments)

    def publish(self, id: int) -> None:
        """Publish a held comment."""
        with self.lock:
            comments = self._read()
            if str(id) in comments:
                comments[str(id)]["status"] = "published"
                self._write(comments)

    def remove(self, id: int) -> None:
        """Drop a comment."""
        with self.lock:
            comments = self._read()
            comments.pop(str(id), None)
            self._write(comments)

    def _read(self) -> dict:
        if not self.path.exists():
            return {}
        return json.loads(self.path.read_text() or "{}")

    def _write(self, comments: dict) -> None:
        self.path.write_text(json.dumps(comments, indent=2))
