"""Offline tests for per-stage token and cost accounting."""
import contextlib
import io
import json
import pathlib
import sys
import tempfile
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from workflow import cost, cli  # noqa: E402
from workflow.engine import Engine  # noqa: E402
from workflow.providers import Provider, Reply, Resilient  # noqa: E402
from workflow.state import Store  # noqa: E402

SKILLS = pathlib.Path(__file__).resolve().parents[2] / "skill" / "task-skills"


class Counter(Provider):
    def __init__(self, name, tokens):
        self.name, self.tokens = name, tokens

    def chat(self, system, messages, tools=None, max_tokens=4096):
        return Reply('{"profile":"coding"}', tokens=self.tokens)


class CostAccounting(unittest.TestCase):
    def test_record_accumulates_per_role_and_provider(self):
        state = {}
        cost.record(state, "planner", "claude", 1000)
        cost.record(state, "planner", "claude", 500)
        cost.record(state, "executor", "cli", 2000)
        self.assertEqual(state["spend"]["planner"], {"calls": 2, "tokens": 1500, "providers": {"claude": 1500}})
        self.assertEqual(state["spend"]["executor"]["providers"], {"cli": 2000})

    def test_pricing_turns_tokens_into_dollars(self):
        state = {"tokens": 1500}
        cost.record(state, "planner", "claude", 1500)
        out = cost.summarize(state, {"pricing": {"claude": {"usd_per_mtok": 3}}})
        self.assertEqual(out["stages"]["planner"]["cost_usd"], 0.0045)
        self.assertEqual(out["cost_usd"], 0.0045)
        self.assertEqual(out["unpriced"], [])

    def test_without_pricing_the_cost_is_unknown(self):
        state = {}
        cost.record(state, "planner", "cli", 2000)
        out = cost.summarize(state, {})
        self.assertIsNone(out["stages"]["planner"]["cost_usd"])
        self.assertIsNone(out["cost_usd"])
        self.assertEqual(out["unpriced"], ["cli"])

    def test_one_unpriced_provider_blocks_the_total(self):
        state = {}
        cost.record(state, "planner", "claude", 1000)
        cost.record(state, "executor", "cli", 1000)
        out = cost.summarize(state, {"pricing": {"claude": {"usd_per_mtok": 3}}})
        self.assertEqual(out["stages"]["planner"]["cost_usd"], 0.003)
        self.assertIsNone(out["stages"]["executor"]["cost_usd"])
        self.assertIsNone(out["cost_usd"])
        self.assertEqual(out["unpriced"], ["cli"])

    def test_engine_calls_are_recorded(self):
        with tempfile.TemporaryDirectory() as d:
            brain = Counter("brain", 120)
            roles = {r: Resilient([brain], retries=1, sleep=lambda s: None)
                     for r in ("router", "planner", "verifier", "executor")}
            eng = Engine(d, {"limits": {"verifier_votes": 1}}, roles, SKILLS, approve="auto", confirm="auto")
            eng.start("say hello", "coding", [{"id": "c1", "text": "hello", "kind": "rubric", "must": True}])
            eng.call("planner", "plan", [{"role": "user", "text": "hi"}])
            eng.call("planner", "plan", [{"role": "user", "text": "hi"}])
            self.assertEqual(eng.state["tokens"], 240)
            self.assertEqual(eng.state["spend"]["planner"], {"calls": 2, "tokens": 240, "providers": {"brain": 240}})

    def test_status_cost_reads_a_pricing_config(self):
        with tempfile.TemporaryDirectory() as d:
            Store(d).write("state.json", {
                "status": "passed", "reason": "", "stage": "done", "round": 1, "profile": "coding",
                "tokens": 1500, "elapsed": 1.0, "failed": [],
                "spend": {"planner": {"calls": 1, "tokens": 1500, "providers": {"claude": 1500}}},
            })
            cfg = pathlib.Path(d) / "config.json"
            cfg.write_text(json.dumps({"pricing": {"claude": {"usd_per_mtok": 3}}}))
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                code = cli.main(["status", d, "--cost", "--config", str(cfg)])
            self.assertEqual(code, 0)
            out = json.loads(buf.getvalue())
            self.assertEqual(out["cost"]["cost_usd"], 0.0045)
            self.assertEqual(out["cost"]["stages"]["planner"]["tokens"], 1500)

    def test_status_without_the_flag_is_unchanged(self):
        with tempfile.TemporaryDirectory() as d:
            Store(d).write("state.json", {"status": "passed", "tokens": 10})
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                cli.main(["status", d])
            self.assertNotIn("cost", json.loads(buf.getvalue()))


if __name__ == "__main__":
    unittest.main()
