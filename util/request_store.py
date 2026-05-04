import threading
import time
import json
from pathlib import Path
import uuid

WORKDIR = Path.cwd()
TEAM_DIR = WORKDIR / ".team"
REQUESTS_DIR = TEAM_DIR / "requests"

class RequestStore:
    """
    Durable request records for protocol workflows.

    Protocol state should survive long enough to inspect, resume, or reconcile.
    This store keeps one JSON file per request_id under .team/requests/.
    """

    def __init__(self, base_dir: Path):
        self.dir = base_dir
        self.dir.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()

    def _path(self, request_id: str) -> Path:
        return self.dir / f"{request_id}.json"

    def create(self, record: dict) -> dict:
        request_id = record["request_id"]
        with self._lock:
            self._path(request_id).write_text(json.dumps(record, indent=2))
        return record

    def get(self, request_id: str) -> dict | None:
        path = self._path(request_id)
        if not path.exists():
            return None
        return json.loads(path.read_text())

    def update(self, request_id: str, **changes) -> dict | None:
        with self._lock:
            record = self.get(request_id)
            if not record:
                return None
            record.update(changes)
            record["updated_at"] = time.time()
            self._path(request_id).write_text(json.dumps(record, indent=2))
        return record


REQUEST_STORE = RequestStore(REQUESTS_DIR)