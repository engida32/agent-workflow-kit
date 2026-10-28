"""Offline tests for executable-criteria approval and criteria-failure recovery."""
import json
import pathlib
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from workflow.engine import Engine  # noqa: E402
from workflow.providers import Provider, Reply, Resilient  # noqa: E402
from workflow.state import Store  # noqa: E402

SKILLS = pathlib.Path(__file__).resolve().parents[2] / "skill" / "task-skills"
EXEC = [{"id": "c1", "text": "hello.txt exists", "kind": "exec", "must": True,
         "command": "touch exec_ran && test -s hello.txt"}]
RUBRIC = [{"id": "c1", "text": "hello.txt is complete", "kind": "rubric", "must": True}]


class Script(Provider):
    def __init__(self, name, script):
        self.name, self.script, self.calls = name, list(script), 0

    def chat(self, system, messages, tools=None, max_tokens=4096):
        self.calls += 1
        item = self.script.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


class Brain(Provider):
    name = "brain"

    def __init__(self, verdicts=None):
        self.verdicts = list(verdicts or [])
        self.planner_calls = 0

    def chat(self, system, messages, tools=None, max_tokens=4096):
        if "units of work" in system:
            self.planner_calls += 1
            return Reply('{"units":[{"id":"u1","what":"write hello.txt","why":"deliverable"}]}')
        if "independent" in system and "reviewer" in system:
            return Reply(json.dumps(self.verdicts.pop(0)))
        return Reply('{"profile":"coding"}')


def write_call(i=1):
    return Reply("", [{"id": f"t{i}", "name": "write_file", "args": {"path": "hello.txt", "content": "hi"}}])


def make_engine(ws, executor, brain, approve):
    res = lambda ps: Resilient(ps, retries=1, sleep=lambda s: None)  # noqa: E731
    roles = {"router": res([brain]), "planner": res([brain]), "verifier": res([brain]), "executor": res([executor])}
    return Engine(ws, {"limits": {"verifier_votes": 1}}, roles, SKILLS, approve=approve, confirm="auto")


def start(eng, criteria):
    return eng.start(task="write hello.txt", profile="coding", criteria=criteria)


class VerificationGates(unittest.TestCase):
    def test_deny_pauses_without_running_the_command(self):
        with tempfile.TemporaryDirectory() as d:
            ws = pathlib.Path(d)
            ex = Script("ex", [write_call(), Reply("done")])
            eng = make_engine(ws, ex, Brain(), "deny")
            start(eng, EXEC)
            out = eng.run()
            self.assertEqual(out["status"], "needs_human")
            self.assertEqual(out["stage"], "verify")
            self.assertIn("not approved", out["reason"])
            self.assertFalse((ws / "exec_ran").exists())

            resumed = make_engine(ws, ex, Brain(), "auto")
            resumed.start()
            self.assertEqual(resumed.run()["status"], "passed")
            self.assertTrue((ws / "exec_ran").exists())

    def test_ask_prompts_once_for_the_verification_command(self):
        with tempfile.TemporaryDirectory() as d:
            ws = pathlib.Path(d)
            ex = Script("ex", [write_call(), Reply("done")])
            eng = make_engine(ws, ex, Brain(), "ask")
            start(eng, EXEC)
            with patch("workflow.tools.sys.stdin") as fake_stdin, patch("builtins.input", return_value="y") as ask:
                fake_stdin.isatty.return_value = True
                out = eng.run()
            self.assertEqual(out["status"], "passed")
            self.assertEqual(ask.call_count, 1)
            self.assertIn("touch exec_ran", ask.call_args.args[0])
            self.assertTrue((ws / "exec_ran").exists())

    def test_auto_runs_without_prompting(self):
        with tempfile.TemporaryDirectory() as d:
            ws = pathlib.Path(d)
            ex = Script("ex", [write_call(), Reply("done")])
            eng = make_engine(ws, ex, Brain(), "auto")
            start(eng, EXEC)
            with patch("builtins.input") as ask:
                out = eng.run()
            self.assertEqual(out["status"], "passed")
            self.assertEqual(ask.call_count, 0)
            self.assertTrue((ws / "exec_ran").exists())

    def test_criteria_failure_resumes_at_verify_not_work(self):
        with tempfile.TemporaryDirectory() as d:
            ws = pathlib.Path(d)
            brain = Brain([
                [{"id": "c1", "passed": False, "reason": "criterion is ambiguous", "failure_stage": "criteria"}],
                [{"id": "c1", "passed": True, "reason": "hello.txt is complete", "failure_stage": None}],
            ])
            ex = Script("ex", [write_call(), Reply("done")])
            eng = make_engine(ws, ex, brain, "auto")
            start(eng, RUBRIC)
            out = eng.run()
            self.assertEqual(out["status"], "needs_human")
            self.assertEqual(out["stage"], "verify")
            self.assertEqual(out["round"], 2)
            self.assertEqual(ex.calls, 2)

            crit = Store(ws).read("criteria.json")
            crit[0]["text"] = "hello.txt is complete and readable"
            Store(ws).write("criteria.json", crit)
            eng.start()
            self.assertEqual(eng.run()["status"], "passed")
            self.assertEqual(ex.calls, 2)
            self.assertTrue((ws / ".wf" / "verify_1.json").exists())
            self.assertTrue((ws / ".wf" / "verify_2.json").exists())
            self.assertTrue(json.loads((ws / ".wf" / "verify_2.json").read_text())[0]["passed"])


if __name__ == "__main__":
    unittest.main()
