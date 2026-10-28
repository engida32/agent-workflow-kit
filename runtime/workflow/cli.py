"""CLI: run | resume | status | eval.   Exit codes: 0 passed, 75 paused (resume later), 3 needs human, 2 other."""
import argparse
import json
import os
import pathlib
import site
import sys
import sysconfig

from . import __version__
from .engine import Engine, TERMINAL
from .providers import Resilient, build_provider
from .state import Locked, Store

ROLES = ("router", "planner", "executor", "verifier")


def task_skills_dir():
    """Locate the packaged task skills in a source checkout or an installed wheel."""
    env = os.getenv("WF_TASK_SKILLS_DIR")
    if env:
        return pathlib.Path(env).expanduser()
    here = pathlib.Path(__file__).resolve()
    candidates = [
        here.parents[2] / "skill" / "task-skills",
        pathlib.Path(sysconfig.get_path("data")) / "share" / "agent-workflow" / "task-skills",
    ]
    if site.USER_BASE:
        candidates.append(pathlib.Path(site.USER_BASE) / "share" / "agent-workflow" / "task-skills")
    for c in candidates:
        if c.is_dir():
            return c
    return candidates[0]


SKILLS = task_skills_dir()


def default_config():
    prov = {}
    if os.getenv("ANTHROPIC_API_KEY"):
        prov["claude"] = {"type": "anthropic", "model": os.getenv("WF_ANTHROPIC_MODEL", "claude-sonnet-5-5")}
    if os.getenv("OPENAI_API_KEY") and os.getenv("WF_OPENAI_MODEL"):
        prov["openai"] = {"type": "openai_compat", "model": os.environ["WF_OPENAI_MODEL"],
                          "base_url": os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")}
    if not prov:
        raise ValueError("No model configured. Pass --config FILE (see config.example.json) or set "
                         "ANTHROPIC_API_KEY, or OPENAI_API_KEY with WF_OPENAI_MODEL.")
    names = list(prov)
    return {"providers": prov, "roles": {r: names for r in ROLES} | {"verifier": names[::-1]}}


def make_engine(workspace, args):
    cfg = json.load(open(args.config)) if args.config else default_config()
    if not isinstance(cfg, dict):
        raise ValueError("config must be a JSON object")
    specs = cfg.get("providers")
    if not isinstance(specs, dict) or not specs:
        raise ValueError("no providers configured; add a non-empty providers object to the config")
    provs = {n: build_provider(n, s) for n, s in specs.items()}
    res = cfg.get("resilience", {})
    store = Store(workspace)
    log = lambda **k: store.journal(**k)  # noqa: E731
    roles = {}
    for r in ROLES:
        names = cfg.get("roles", {}).get(r) or list(provs)
        try:
            chain = [provs[n] for n in names]
        except KeyError as e:
            raise ValueError(f"role {r!r} names unknown provider {e.args[0]!r}; "
                             f"known providers: {', '.join(sorted(provs))}") from None
        roles[r] = Resilient(chain, res.get("max_retries", 5), res.get("base_delay", 2),
                             res.get("max_delay", 60), res.get("outage_wait_seconds", 0), log=log)
    return Engine(workspace, cfg, roles, SKILLS, approve=args.approve, confirm=args.confirm)


def code(summary):
    return {"passed": 0, "paused": 75, "needs_human": 3}.get(summary["status"], 2)


def main(argv=None):
    ap = argparse.ArgumentParser(prog="workflow")
    ap.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = ap.add_subparsers(dest="cmd", required=True)

    def common(p):
        p.add_argument("--config")
        p.add_argument("--approve", choices=["ask", "auto", "deny"], default="ask",
                       help="shell command approval; use auto only inside a sandbox")
        p.add_argument("--confirm", choices=["ask", "auto"], default="ask", help="criteria confirmation")

    r = sub.add_parser("run", help="start a task (re-running the same command resumes it)")
    r.add_argument("task")
    r.add_argument("--workspace", "-w", default="workspace")
    r.add_argument("--profile", choices=["coding", "research", "design", "evaluation"])
    r.add_argument("--criteria", help="JSON file with acceptance criteria (skips drafting)")
    common(r)
    s = sub.add_parser("resume", help="continue a paused or interrupted run")
    s.add_argument("workspace")
    s.add_argument("--add-rounds", type=int, default=0)
    s.add_argument("--add-tokens", type=int, default=0)
    common(s)
    t = sub.add_parser("status")
    t.add_argument("workspace")
    e = sub.add_parser("eval", help="run an eval set; resumable, finished tasks are skipped")
    e.add_argument("file")
    e.add_argument("--out", default="eval_runs")
    common(e)
    a = ap.parse_args(argv)

    try:
        if a.cmd == "status":
            st = Store(a.workspace).read("state.json") if (pathlib.Path(a.workspace) / ".wf").exists() else None
            if st is not None and not isinstance(st, dict):
                raise ValueError("state.json is not a JSON object")
            keys = ("status", "reason", "stage", "round", "profile", "tokens", "elapsed", "failed")
            print(json.dumps({k: st.get(k) for k in keys} if st else {"status": "no run here"}, indent=1))
            return 0
        if a.cmd == "run":
            crit = json.load(open(a.criteria)) if a.criteria else None
            eng = make_engine(a.workspace, a)
            eng.start(a.task, a.profile, crit)
        elif a.cmd == "resume":
            eng = make_engine(a.workspace, a)
            eng.start(None, add_rounds=a.add_rounds, add_tokens=a.add_tokens)
        else:
            return run_eval(a)
        s = eng.run()
        print(json.dumps(s, indent=1))
        return code(s)
    except Locked as ex:
        print(f"locked: {ex}", file=sys.stderr)
        return 2
    except (ValueError, KeyError, OSError, json.JSONDecodeError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 2


def run_eval(a):
    out = pathlib.Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    rows = []
    for t in json.load(open(a.file)):
        ws = out / t["id"]
        prior = Store(ws).read("state.json") if ws.exists() else None
        if not isinstance(prior, dict):
            prior = None
        eng = make_engine(ws, a)
        eng.start(t["task"], t.get("profile"), t["criteria"])
        s = eng.run() if not prior or prior["status"] not in TERMINAL else eng.summary()
        rows.append({"id": t["id"], **{k: s[k] for k in ("status", "round", "tokens", "elapsed", "failed")}})
        print(f"[{t['id']}] {s['status']} rounds={s['round']} tokens={s['tokens']}", flush=True)
        (out / "results.json").write_text(json.dumps(rows, indent=1))
    done = sum(r["status"] == "passed" for r in rows)
    print(f"completed {done}/{len(rows)}; total tokens {sum(r['tokens'] for r in rows)}; results in {out}/results.json")
    return 0 if done == len(rows) else 2
