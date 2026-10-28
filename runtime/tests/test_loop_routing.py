"""Offline tests for stage routing: research before plan, and failure-stage recovery."""
import json
import pathlib
import sys
import tempfile
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from workflow.engine import Engine  # noqa: E402
from workflow.providers import Provider, Reply, Resilient  # noqa: E402

SKILLS = pathlib.Path(__file__).resolve().parents[2] / "skill" / "task-skills"
CRIT = [{"id": "c1", "text": "hello.txt exists", "kind": "exec", "must": True, "command": "test -s hello.txt"}]
RUBRIC = [{"id": "c1", "text": "hello.txt is complete", "kind": "rubric", "must": True}]


class Script(Provider):
    def __init__(self, name, script):
        self.name, self.script, self.calls = name, list(script), 0

    def chat(self, system, messages, tools=None, max_tokens=4096):
        self.calls += 1
        return self.script.pop(0)


class StageBrain(Provider):
    """Returns queued verifier verdicts and records every planner input."""

    name = "brain"

    def __init__(self, verdicts):
        self.verdicts = list(verdicts)
        self.planner_calls = 0
        self.planner_inputs = []

    def chat(self, system, messages, tools=None, max_tokens=4096):
        if "units of work" in system:
            self.planner_calls += 1
            self.planner_inputs.append(messages[-1]["text"])
            return Reply('{"units":[{"id":"u1","what":"create hello.txt","why":"deliverable"}]}')
        if "independent" in system and "reviewer" in system:
            return Reply(json.dumps(self.verdicts.pop(0)))
        return Reply('{"profile":"coding"}')


def write_call(path, i=1):
    return Reply("", [{"id": f"t{i}", "name": "write_file", "args": {"path": path, "content": "done"}}])


def make_engine(ws, executor, brain):
    res = lambda ps: Resilient(ps, retries=1, sleep=lambda s: None)  # noqa: E731
    roles = {"router": res([brain]), "planner": res([brain]), "verifier": res([brain]), "executor": res([executor])}
    return Engine(ws, {"limits": {"verifier_votes": 1}}, roles, SKILLS, approve="auto", confirm="auto")


def stages(ws):
    rows = (pathlib.Path(ws) / ".wf" / "journal.jsonl").read_text().splitlines()
    return [json.loads(r)["stage"] for r in rows if json.loads(r).get("event") == "stage"]


class LoopRouting(unittest.TestCase):
    def test_plan_failure_replans_with_feedback(self):
        with tempfile.TemporaryDirectory() as d:
            brain = StageBrain([
                [{"id": "c1", "passed": False, "reason": "plan misses the file", "failure_stage": "plan"}],
                [{"id": "c1", "passed": True, "reason": "hello.txt exists", "failure_stage": None}],
            ])
            ex = Script("ex", [write_call("hello.txt", 1), Reply("done"), write_call("hello.txt", 2), Reply("done")])
            eng = make_engine(d, ex, brain)
            eng.start("build hello", "coding", RUBRIC)
            out = eng.run()
            self.assertEqual(out["status"], "passed")
            self.assertEqual(brain.planner_calls, 2)
            self.assertIn("approach itself is wrong", brain.planner_inputs[1])
            self.assertIn("plan", stages(d))

    def test_research_failure_researches_then_replans(self):
        with tempfile.TemporaryDirectory() as d:
            brain = StageBrain([
                [{"id": "c1", "passed": False, "reason": "missing knowledge", "failure_stage": "research"}],
                [{"id": "c1", "passed": True, "reason": "hello.txt exists", "failure_stage": None}],
            ])
            ex = Script("ex", [
                write_call("hello.txt", 1), Reply("done"),
                write_call("research.md", 2), Reply("learned enough"),
                write_call("hello.txt", 3), Reply("done"),
            ])
            eng = make_engine(d, ex, brain)
            eng.start("build hello", "coding", RUBRIC)
            out = eng.run()
            self.assertEqual(out["status"], "passed")
            self.assertEqual(brain.planner_calls, 2)
            self.assertIn("Research notes", brain.planner_inputs[1])
            self.assertIn("missing knowledge", brain.planner_inputs[1])
            self.assertTrue((pathlib.Path(d) / "research.md").exists())
            self.assertIn("research", stages(d))

    def test_research_profile_researches_before_plan(self):
        crit = [{"id": "c1", "text": "research exists", "kind": "exec", "must": True,
                 "command": "test -s research.md"},
                {"id": "c2", "text": "hello exists", "kind": "exec", "must": True, "command": "test -s hello.txt"}]
        with tempfile.TemporaryDirectory() as d:
            brain = StageBrain([])
            ex = Script("ex", [write_call("research.md", 1), Reply("learned"), write_call("hello.txt", 2), Reply("built")])
            eng = make_engine(d, ex, brain)
            eng.start("research then build", "research", crit)
            out = eng.run()
            self.assertEqual(out["status"], "passed")
            order = stages(d)
            self.assertLess(order.index("research"), order.index("plan"))
            self.assertEqual(brain.planner_calls, 1)


if __name__ == "__main__":
    unittest.main()
