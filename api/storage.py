
from __future__ import annotations
from typing import Dict, List, Optional
from .models import Pipeline, Run
from threading import RLock
from datetime import datetime

class InMemoryDB:
    def __init__(self) -> None:
        self._pipelines: Dict[str, Pipeline] = {}
        self._runs: Dict[str, Run] = {}
        self._lock = RLock()

    def create_pipeline(self, p: Pipeline) -> Pipeline:
        with self._lock:
            self._pipelines[p.id] = p
            return p

    def list_pipelines(self) -> List[Pipeline]:
        with self._lock:
            return list(self._pipelines.values())

    def get_pipeline(self, pid: str) -> Optional[Pipeline]:
        with self._lock:
            return self._pipelines.get(pid)

    def update_pipeline(self, pid: str, updated: Pipeline) -> Optional[Pipeline]:
        with self._lock:
            if pid not in self._pipelines:
                return None
            updated.updated_at = datetime.utcnow()
            self._pipelines[pid] = updated
            return updated

    def delete_pipeline(self, pid: str) -> bool:
        with self._lock:
            return self._pipelines.pop(pid, None) is not None

    def create_run(self, r: Run) -> Run:
        with self._lock:
            self._runs[r.id] = r
            return r

    def get_run(self, rid: str) -> Optional[Run]:
        with self._lock:
            return self._runs.get(rid)

    def update_run(self, rid: str, r: Run) -> Optional[Run]:
        with self._lock:
            if rid not in self._runs:
                return None
            self._runs[rid] = r
            return r

db = InMemoryDB()
