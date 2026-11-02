"""Remote sweep worker — scale the worldwide sweep horizontally across free machines / IPs.

    ADUNS_WORKER_TOKEN=secret python -m aduns worker --server https://central.example.org

The worker leases countries from the central server (one per continent, so coverage stays equal), sweeps them
locally with its own IP and rate-limit budget (local cache DB), and uploads the resulting signals and newly
discovered channels. Fusion, capabilities, analogies and missions stay on the central server.
"""
from __future__ import annotations

import json
import os
import socket
import time

import requests


def run(server: str, token: str, worker_id: str | None = None, per_continent: int = 1, max_rounds: int | None = None,
        local_db: str | None = None) -> None:
    os.environ["ADUNS_DB"] = local_db or os.path.join(os.getcwd(), "data", "worker-cache.db")
    from . import config, db
    config.DB_PATH = os.environ["ADUNS_DB"]
    db.reset_connections()
    from .agents import NeedSensingAgent

    wid = worker_id or f"worker:{socket.gethostname()}:{os.getpid()}"
    hdr = {"X-Aduns-Token": token}
    rounds = 0
    while max_rounds is None or rounds < max_rounds:
        rounds += 1
        try:
            lease = requests.post(f"{server}/api/worker/lease", json={"worker_id": wid, "per_continent": per_continent},
                                  headers=hdr, timeout=60).json()
        except requests.RequestException as e:
            print("lease failed:", e, flush=True)
            time.sleep(60)
            continue
        for iso in lease.get("countries", []):
            t0 = time.time()
            r = NeedSensingAgent().run(country=iso)
            sigs = db.q("SELECT * FROM signals WHERE run_id=?", (r["run_id"],))
            reg = db.q("SELECT kind, handle, country, discovered_from FROM source_registry WHERE discovered_at >= ?", (t0,))
            st = r["stats"]
            stats = {"sources_ok": sorted({k.split(":", 1)[1] for k in st if k.startswith("fetched:") and st[k] > 0}),
                     "sources_failed": sorted({e.split(":", 1)[0] for e in st.get("errors", [])})}
            try:
                resp = requests.post(f"{server}/api/worker/report", headers=hdr, timeout=300,
                                     data=json.dumps({"worker_id": wid, "country": iso, "signals": sigs, "registry": reg,
                                                      "stats": stats}, default=str),
                                     ).json()
                print(f"{iso}: swept {len(sigs)} → central stored {resp.get('stored')}", flush=True)
            except requests.RequestException as e:
                print(f"{iso}: upload failed: {e}", flush=True)
        if not lease.get("countries"):
            time.sleep(120)
