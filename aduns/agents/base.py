"""Common agent machinery: run bookkeeping, audit trail, error isolation per source."""
from __future__ import annotations

import json
import time
import traceback
from typing import Any, Callable

from .. import db, http


class Agent:
    name = "agent"

    def __init__(self) -> None:
        self.run_id: int | None = None
        self.stats: dict[str, Any] = {}
        self.errors: list[str] = []

    # ---- lifecycle -------------------------------------------------------
    def run(self, **params) -> dict:
        self.stats, self.errors = {}, []
        self.run_id = db.insert("agent_runs", {"agent": self.name, "params": json.dumps(params, default=str),
                                               "status": "running", "started_at": time.time()})
        db.audit(self.name, "run_started", "agent_run", self.run_id, params)
        try:
            result = self.execute(**params) or {}
            status = "ok" if not self.errors else "partial"
        except Exception as e:  # noqa: BLE001 — agent must always close its run record
            self.errors.append(f"{type(e).__name__}: {e}")
            result = {"traceback": traceback.format_exc()[-2000:]}
            status = "error"
        self.stats["errors"] = self.errors[-25:]
        db.update("agent_runs", self.run_id, {"status": status, "finished_at": time.time(),
                                              "stats": json.dumps(self.stats, default=str),
                                              "error": "\n".join(self.errors[-10:]) or None})
        db.audit(self.name, "run_finished", "agent_run", self.run_id, {"status": status, **self.stats})
        return {"run_id": self.run_id, "status": status, "stats": self.stats, **result}

    def execute(self, **params) -> dict:  # pragma: no cover - abstract
        raise NotImplementedError

    # ---- helpers -----------------------------------------------------------
    def safe(self, label: str, fn: Callable[[], Any], default: Any = None) -> Any:
        """Call one external source; record failure and continue (one dead feed never kills a run)."""
        try:
            return fn()
        except http.FetchError as e:
            self.errors.append(f"{label}: {e}"[:400])
        except Exception as e:  # noqa: BLE001
            self.errors.append(f"{label}: {type(e).__name__}: {e}"[:400])
        return default

    def bump(self, key: str, n: int = 1) -> None:
        self.stats[key] = self.stats.get(key, 0) + n
