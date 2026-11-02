"""CLI:  python -m aduns <command> ...

  discover  --focus "solar freezer" --country Nigeria [--depth 1] [--top 5] [--no-missions]
  sense     --focus ... [--country ...]
  fuse      [--focus ...]
  capabilities --hypothesis ID
  analogies --hypothesis ID [--country ...] | --country NGA --domain energy
  gaps      [--domain energy] [--country NGA]
  mission   --hypothesis ID [--country ...]
  serve     [--port 8000]
  show      (top hypotheses)
"""
from __future__ import annotations

import argparse
import json

from . import db


def main() -> None:
    p = argparse.ArgumentParser(prog="aduns")
    sub = p.add_subparsers(dest="cmd", required=True)
    d = sub.add_parser("discover"); d.add_argument("--focus", default=""); d.add_argument("--country", default="")
    d.add_argument("--depth", type=int, default=1); d.add_argument("--top", type=int, default=5)
    d.add_argument("--no-missions", action="store_true")
    s = sub.add_parser("sense"); s.add_argument("--focus", default=""); s.add_argument("--country", default="")
    s.add_argument("--depth", type=int, default=1)
    f = sub.add_parser("fuse"); f.add_argument("--focus", default=""); f.add_argument("--threshold", type=float, default=0.22)
    c = sub.add_parser("capabilities"); c.add_argument("--hypothesis", type=int); c.add_argument("--query", default="")
    a = sub.add_parser("analogies"); a.add_argument("--hypothesis", type=int); a.add_argument("--country", default="")
    a.add_argument("--domain", default="")
    g = sub.add_parser("gaps"); g.add_argument("--domain", default=""); g.add_argument("--country", default="")
    m = sub.add_parser("mission"); m.add_argument("--hypothesis", type=int, required=True); m.add_argument("--country", default="")
    sv = sub.add_parser("serve"); sv.add_argument("--port", type=int, default=8000); sv.add_argument("--host", default="0.0.0.0")
    sv.add_argument("--daemon", action="store_true", help="also run the 24/7 discovery loop inside the server")
    sub.add_parser("show")
    dm = sub.add_parser("daemon", help="run the 24/7 autonomous worldwide discovery loop")
    dm.add_argument("--cycles", type=int, default=None); dm.add_argument("--parallel", type=int, default=2)
    dm.add_argument("--downstream", type=int, default=3)
    dm.add_argument("--max-minutes", type=float, default=None, help="stop gracefully after this many minutes")
    sw = sub.add_parser("sweep", help="sweep one country in its own languages")
    sw.add_argument("--country", required=True)
    sub.add_parser("selftest", help="live check of every data source")
    wk = sub.add_parser("worker", help="remote sweep worker: lease countries from a central server, upload signals")
    wk.add_argument("--server", required=True); wk.add_argument("--token", default="")
    wk.add_argument("--per-continent", type=int, default=1); wk.add_argument("--rounds", type=int, default=None)
    dm.add_argument("--no-sense", action="store_true", help="central mode: only fuse/downstream (workers sense)")
    sub.add_parser("coverage", help="signals per continent / country")
    args = p.parse_args()
    if args.cmd == "selftest":
        from . import selftest
        raise SystemExit(1 if selftest.run() else 0)
    if args.cmd == "daemon":
        from .scheduler import Daemon
        Daemon(parallel_countries=args.parallel, downstream_per_cycle=args.downstream,
               sense_locally=not args.no_sense).run_forever(args.cycles, (args.max_minutes or 0) * 60 or None)
        return
    if args.cmd == "worker":
        import os
        from . import worker
        worker.run(args.server.rstrip("/"), args.token or os.environ.get("ADUNS_WORKER_TOKEN", ""),
                   per_continent=args.per_continent, max_rounds=args.rounds)
        return
    if args.cmd == "coverage":
        from .scheduler import coverage
        cov = coverage()
        for cont, v in cov.items():
            print(f"{cont:15} countries={v['countries']:3} swept={v['swept']:3} signals={v['signals']}")
        return

    from .agents import (CapabilityDiscoveryAgent, CrossBorderAnalogyAgent, NeedSensingAgent,
                         OfflineScoutCoordinator, SignalFusionAgent)

    if args.cmd == "discover":
        from .orchestrator import run_discovery
        out = run_discovery(args.focus, args.country, args.depth, args.top, create_missions=not args.no_missions,
                            progress=lambda msg: print("·", msg, flush=True))
    elif args.cmd == "sweep":
        out = NeedSensingAgent().run(country=args.country)
        out.pop("signal_ids", None)
    elif args.cmd == "sense":
        out = NeedSensingAgent().run(focus=args.focus, country=args.country, depth=args.depth)
        out.pop("signal_ids", None)
    elif args.cmd == "fuse":
        out = SignalFusionAgent().run(query=args.focus, threshold=args.threshold)
    elif args.cmd == "capabilities":
        out = CapabilityDiscoveryAgent().run(hypothesis_id=args.hypothesis, query=args.query)
    elif args.cmd == "analogies":
        out = CrossBorderAnalogyAgent().run(hypothesis_id=args.hypothesis, country=args.country, domain=args.domain)
    elif args.cmd == "gaps":
        ag = NeedSensingAgent()
        out = ag.run(sources=["worldbank_wdi"], focus=args.domain.replace("_", " ") if args.domain else "",
                     country=args.country)
        out.pop("signal_ids", None)
    elif args.cmd == "mission":
        out = OfflineScoutCoordinator().run(hypothesis_id=args.hypothesis, country=args.country)
    elif args.cmd == "serve":
        import os
        import uvicorn
        if args.daemon:
            os.environ["ADUNS_AUTOSTART_DAEMON"] = "1"
        uvicorn.run("aduns.api:app", host=args.host, port=args.port)
        return
    else:
        out = db.q("SELECT id, score, evidence_level, signal_count, source_count, title FROM hypotheses WHERE status != 'superseded' ORDER BY score DESC LIMIT 25")
    print(json.dumps(out, indent=2, default=str))


if __name__ == "__main__":
    main()
