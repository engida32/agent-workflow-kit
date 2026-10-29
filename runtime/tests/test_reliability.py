import io
import json
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from types import SimpleNamespace

from workflow.cli import SKILLS, main, run_eval
from workflow.engine import Engine, normalize_criteria
from workflow.providers import Provider, Reply
from workflow.state import Store
from unittest.mock import patch

RUBRIC = [{"id": "r1", "text": "the result is complete", "kind": "rubric", "must": True}]


class Script(Provider):
    def __init__(self, replies):
        self.name = "script"
        self.replies = list(replies)
        self.calls = 0

    @property
    def last_provider(self):
        return self.name

    def chat(self, system, messages, tools=None, max_tokens=4096):
        self.calls += 1
        return self.replies.pop(0)


def state(**changes):
    value = {
        "schema_version": 1,
        "task": "check the thing",
        "profile": "coding",
        "stage": "verify",
        "status": "running",
        "reason": "",
        "round": 1,
        "tokens": 0,
        "elapsed": 0.0,
        "best_failed": None,
        "stale": 0,
        "feedback": "",
        "failed": [],
        "limits": {
            "max_rounds": 4,
            "max_tokens": 100000,
            "max_seconds": 7200,
            "max_turns": 10,
            "max_context_chars": 150000,
            "verifier_votes": 3,
        },
        "providers_used": {},
    }
    value.update(changes)
    return value


def verdict(passed, reason="", stage=None):
    return Reply(json.dumps([{"id": "r1", "passed": passed, "reason": reason, "failure_stage": stage}]))


class Reliability(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.ws = self.tmp.name
        self.store = Store(self.ws)

    def tearDown(self):
        self.tmp.cleanup()

    def test_old_state_is_migrated_to_the_current_schema(self):
        self.store.write("state.json", state(schema_version=None, status="paused", stage="work"))
        eng = Engine(self.ws, {}, {}, SKILLS, approve="auto", confirm="auto")
        st = eng.start(None)
        self.assertEqual(st["schema_version"], 1)
        self.assertIn("schema_migrated", (Path(self.ws) / ".wf" / "journal.jsonl").read_text())

    def test_newer_state_schema_is_rejected(self):
        self.store.write("state.json", state(schema_version=99, status="paused", stage="work"))
        eng = Engine(self.ws, {}, {}, SKILLS, approve="auto", confirm="auto")
        with self.assertRaisesRegex(ValueError, "newer"):
            eng.start(None)

    def test_failed_run_requires_an_explicit_retry(self):
        self.store.write("state.json", state(status="failed", stage="work", reason="provider failed"))
        eng = Engine(self.ws, {}, {}, SKILLS, approve="auto", confirm="auto")
        with self.assertRaisesRegex(ValueError, "retry-failed"):
            eng.start(None)
        st = eng.start(None, retry_failed=True)
        self.assertEqual(st["status"], "running")
        self.assertEqual(st["reason"], "")

    def test_rubric_majority_and_evidence_are_recorded(self):
        self.store.write("state.json", state())
        verifier = Script([verdict(True, "ok"), verdict(False, "missing", "plan"), verdict(True, "ok")])
        eng = Engine(self.ws, {}, {"verifier": verifier}, SKILLS, approve="auto", confirm="auto")
        out = eng.verify(RUBRIC)[0]
        self.assertTrue(out["passed"])
        self.assertEqual(verifier.calls, 3)
        self.assertEqual(len(out["votes"]), 3)
        self.assertTrue(out["checked_at"].endswith("Z"))

    def test_rubric_without_a_majority_fails(self):
        self.store.write("state.json", state())
        verifier = Script([verdict(True), verdict(False, "not sure", "plan"), Reply("{}")])
        eng = Engine(self.ws, {}, {"verifier": verifier}, SKILLS, approve="auto", confirm="auto")
        out = eng.verify(RUBRIC)[0]
        self.assertFalse(out["passed"])
        self.assertIn("no majority", out["reason"])
        self.assertEqual(len(out["votes"]), 3)
        self.assertTrue(out["votes"][2]["missing"])

    def test_verifier_votes_are_clamped_and_must_be_an_integer(self):
        self.store.write("state.json", state(limits={"verifier_votes": 1000}))
        eng = Engine(self.ws, {}, {}, SKILLS, approve="auto", confirm="auto")
        self.assertEqual(eng.start(None)["limits"]["verifier_votes"], 9)
        self.store.write("state.json", state(limits={"verifier_votes": "many"}))
        eng = Engine(self.ws, {}, {}, SKILLS, approve="auto", confirm="auto")
        with self.assertRaisesRegex(ValueError, "integer"):
            eng.start(None)

    def test_failure_stage_uses_the_majority_of_failing_votes(self):
        self.store.write("state.json", state())
        verifier = Script([
            verdict(False, "wrong approach", "plan"),
            verdict(False, "missing knowledge", "research"),
            verdict(False, "still wrong", "plan"),
        ])
        eng = Engine(self.ws, {}, {"verifier": verifier}, SKILLS, approve="auto", confirm="auto")
        out = eng.verify(RUBRIC)[0]
        self.assertFalse(out["passed"])
        self.assertEqual(out["failure_stage"], "plan")

    def test_eval_skips_a_failed_run_instead_of_crashing(self):
        out = Path(self.ws) / "eval_runs"
        ws = out / "one"
        ws.mkdir(parents=True)
        Store(str(ws)).write("state.json", state(status="failed", reason="bad", stage="work"))
        cfg = Path(self.ws) / "config.json"
        cfg.write_text(json.dumps({
            "providers": {"p": {"type": "command", "command": "true"}},
            "roles": {r: ["p"] for r in ("router", "planner", "executor", "verifier")},
        }))
        tasks = Path(self.ws) / "tasks.json"
        tasks.write_text(json.dumps([{"id": "one", "task": "x", "profile": "coding", "criteria": RUBRIC}]))
        with redirect_stdout(io.StringIO()):
            rc = run_eval(SimpleNamespace(out=str(out), config=str(cfg), approve="auto",
                                          confirm="auto", file=str(tasks)))
        self.assertEqual(rc, 2)
        self.assertEqual(json.loads((out / "results.json").read_text())[0]["status"], "failed")

    def test_eval_reports_an_incomplete_prior_state_without_a_traceback(self):
        out = Path(self.ws) / "eval_runs"
        ws = out / "one"
        ws.mkdir(parents=True)
        Store(str(ws)).write("state.json", {"task": "x"})
        cfg = Path(self.ws) / "config.json"
        cfg.write_text(json.dumps({
            "providers": {"p": {"type": "command", "command": "true"}},
            "roles": {r: ["p"] for r in ("router", "planner", "executor", "verifier")},
        }))
        tasks = Path(self.ws) / "tasks.json"
        tasks.write_text(json.dumps([{"id": "one", "task": "x", "profile": "coding", "criteria": RUBRIC}]))
        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            rc = main(["eval", str(tasks), "--out", str(out), "--config", str(cfg),
                       "--approve", "auto", "--confirm", "auto"])
        self.assertEqual(rc, 2)

    def test_exec_evidence_includes_command_exit_duration_and_output(self):
        self.store.write("state.json", state())
        eng = Engine(self.ws, {}, {}, SKILLS, approve="auto", confirm="auto")
        out = eng.verify([{
            "id": "c1",
            "text": "the command fails",
            "kind": "exec",
            "must": True,
            "command": "printf out; printf err >&2; exit 3",
        }])[0]
        self.assertFalse(out["passed"])
        self.assertEqual(out["command"], "printf out; printf err >&2; exit 3")
        self.assertEqual(out["exit_code"], 3)
        self.assertGreaterEqual(out["duration_seconds"], 0)
        self.assertTrue(out["checked_at"].endswith("Z"))
        self.assertIn("out", out["output"])
        self.assertIn("err", out["output"])


    def test_corrupt_state_is_rejected_without_overwriting_progress(self):
        self.store.write("state.json", "{broken", text=True)
        progress = Path(self.ws) / "progress.md"
        progress.write_text("important progress")
        eng = Engine(self.ws, {}, {}, SKILLS, approve="auto", confirm="auto")
        with self.assertRaisesRegex(ValueError, "not valid JSON"):
            eng.start("new task")
        self.assertEqual(progress.read_text(), "important progress")

    def test_empty_state_object_is_rejected(self):
        self.store.write("state.json", {})
        eng = Engine(self.ws, {}, {}, SKILLS, approve="auto", confirm="auto")
        with self.assertRaisesRegex(ValueError, "incomplete"):
            eng.start("new task")

    def test_partial_state_gets_default_limits(self):
        self.store.write("state.json", state(limits={"max_rounds": 2}))
        eng = Engine(self.ws, {}, {}, SKILLS, approve="auto", confirm="auto")
        st = eng.start(None)
        self.assertEqual(st["limits"]["max_rounds"], 2)
        self.assertEqual(st["limits"]["max_tokens"], 600000)

    def test_non_integer_schema_version_is_rejected(self):
        self.store.write("state.json", state(schema_version="1"))
        eng = Engine(self.ws, {}, {}, SKILLS, approve="auto", confirm="auto")
        with self.assertRaisesRegex(ValueError, "non-integer"):
            eng.start(None)


    def test_malformed_criteria_is_a_clean_error(self):
        for bad in ([{"id": "a"}, "oops"], {"criteria": "no"}, [{"id": "a", "text": ""}]):
            with self.assertRaises(ValueError):
                normalize_criteria(bad)

    def test_non_tty_criteria_review_holds_at_the_criteria_stage(self):
        self.store.write("state.json", state(stage="criteria", status="running"))
        planner = Script([Reply(json.dumps([{"id": "c1", "text": "the result exists"}]))])
        eng = Engine(self.ws, {}, {"planner": planner}, SKILLS, confirm="ask")
        with patch("sys.stdin.isatty", return_value=False):
            eng.step_criteria()
        self.assertEqual(eng.state["stage"], "criteria")
        self.assertEqual(eng.state["status"], "needs_human")
        self.assertTrue(eng.state["criteria_pending"])
        eng.start(None)
        self.assertFalse(eng.state["criteria_pending"])
        eng.step_criteria()
        self.assertEqual(eng.state["stage"], "plan")


if __name__ == "__main__":
    unittest.main()
