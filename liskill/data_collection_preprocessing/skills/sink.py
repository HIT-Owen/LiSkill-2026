"""Record sinks and cursor checkpoints.

``JsonlSink`` is the default so the collector runs without any database;
``MongoSink`` keeps the paper's storage design (§3.1.1: one document per skill,
``skill_id`` as primary key) for full-scale runs and imports ``pymongo`` lazily.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, Iterable, List, Optional


class BaseSink:
    def write(self, records: Iterable[Dict[str, object]]) -> int:  # pragma: no cover
        raise NotImplementedError

    def close(self) -> None:
        pass


class MemorySink(BaseSink):
    """Collects records in memory — used by tests and the demo."""

    def __init__(self) -> None:
        self.records: List[Dict[str, object]] = []

    def write(self, records: Iterable[Dict[str, object]]) -> int:
        count = 0
        for record in records:
            self.records.append(record)
            count += 1
        return count

    def __len__(self) -> int:
        return len(self.records)


class JsonlSink(BaseSink):
    """Append-only JSON Lines sink."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._handle = self.path.open("a", encoding="utf-8")
        self.written = 0

    def write(self, records: Iterable[Dict[str, object]]) -> int:
        count = 0
        for record in records:
            self._handle.write(json.dumps(record, ensure_ascii=False) + "\n")
            count += 1
        self._handle.flush()
        self.written += count
        return count

    def close(self) -> None:
        self._handle.close()


class MongoSink(BaseSink):
    """``UpdateOne`` upserts keyed by ``skill_id`` (§3.1.1 storage design)."""

    def __init__(
        self,
        uri: str = "mongodb://localhost:27017",
        db_name: str = "liskill",
        col_name: str = "skills",
        batch_size: int = 500,
    ) -> None:
        try:
            from pymongo import MongoClient, UpdateOne  # local import: optional dep
        except ImportError as exc:  # pragma: no cover - environment dependent
            raise RuntimeError(
                "MongoSink requires pymongo: pip install 'liskill[store]'"
            ) from exc
        self._update_one = UpdateOne
        self._client = MongoClient(uri)
        self._collection = self._client[db_name][col_name]
        self._buffer: List[dict] = []
        self._batch_size = batch_size
        self.written = 0

    def write(self, records: Iterable[Dict[str, object]]) -> int:
        count = 0
        for record in records:
            key = {"skill_id": record.get("skill_id") or record.get("_id")}
            self._buffer.append(self._update_one(key, {"$set": record}, upsert=True))
            count += 1
            if len(self._buffer) >= self._batch_size:
                self._flush()
        return count

    def _flush(self) -> None:
        if not self._buffer:
            return
        self._collection.bulk_write(self._buffer, ordered=False)
        self.written += len(self._buffer)
        self._buffer.clear()

    def close(self) -> None:
        self._flush()
        self._client.close()


class CursorStore:
    """JSON checkpoint so a run can resume instead of restarting (§3.1.1)."""

    def __init__(self, path: Optional[str | Path]) -> None:
        self.path = Path(path) if path else None
        self.state: Dict[str, object] = {}
        if self.path and self.path.exists():
            try:
                self.state = json.loads(self.path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                self.state = {}

    def get(self, platform: str, default: object = None) -> object:
        return self.state.get(platform, default)

    def set(self, platform: str, value: object) -> None:
        self.state[platform] = value
        self._save()

    def _save(self) -> None:
        if self.path is None:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self.state, indent=2), encoding="utf-8")
