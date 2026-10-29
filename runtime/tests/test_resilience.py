"""Offline tests (no API key, no network). Run:  python -m unittest discover -s runtime/tests -v  (from the kit root)"""
import json
import os
import pathlib
import sys
import tempfile
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from workflow.engine import Engine  # noqa: E402
from workflow.providers import (AnthropicProvider, CommandProvider, Disruption, Fatal, OpenAICompatProvider,  # noqa: E402
                                Provider, Reply, Resilient, Transient)
from workflow.state import Locked, Store  # noqa: E402

SKILLS = pathlib.Path(__file__).resolve().parents[2] / "skill" / "task-skills"
CRIT = [{"id": "c1", "text": "hello.txt exists", "kind": "exec", "must": True, "command": "test -s hello.txt"}]


class Script(Provider):
    """Replays a list of Replies/Exceptions; counts calls."""

    def __init__(self, name, script):
        self.name, self.script, self.calls = name, list(script), 0

    def chat(self, system, messages, tools=None, max_tokens=4096):
        self.calls += 1
        item = self.script.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


class Brain(Provider):
    """Stands in for router/planner/verifier and counts planner calls."""
    name = "brain"

    def __init__(self):
        self.planner_calls = 0

    def chat(self, system, messages, tools=None, max_tokens=4096):
        if "units of work" in system:
            self.planner_calls += 1
            return Reply('{"units":[{"id":"u1","what":"create hello.txt","why":"deliverable"}]}', tokens=10)
        return Reply('{"profile":"coding"}', tokens=5)


def write_call(i=1):
    return Reply("", [{"id": f"t{i}", "name": "write_file", "args": {"path": "hello.txt", "content": "hi"}}], tokens=20)


def make(ws, executor, brain, retries=1):
    res = lambda ps: Resilient(ps, retries=retries, sleep=lambda s: None)  # noqa: E731
    roles = {"router": res([brain]), "planner": res([brain]), "verifier": res([brain]), "executor": res(executor)}
    return Engine(ws, {"limits": {"verifier_votes": 1}}, roles, SKILLS, approve="auto", confirm="auto")


class Resilience(unittest.TestCase):
    def test_backoff_then_success_and_retry_after(self):
        sleeps = []
        p = Script("a", [Transient("503"), Transient("429", retry_after=7), Reply("ok")])
        r = Resilient([p], retries=3, sleep=sleeps.append)
        self.assertEqual(r.complete("s", "u"), "ok")
        self.assertEqual(len(sleeps), 2)
        self.assertEqual(sleeps[1], 7)

    def test_fallback_to_next_provider(self):
        bad = Script("bad", [Transient("down")] * 4)
        good = Script("good", [Reply("from good")])
        r = Resilient([bad, good], retries=1, sleep=lambda s: None)
        self.assertEqual(r.complete("s", "u"), "from good")
        self.assertEqual(r.last_provider, "good")

    def test_fatal_everywhere_raises_fatal_and_outage_raises_disruption(self):
        with self.assertRaises(Fatal):
            Resilient([Script("a", [Fatal("401")])], sleep=lambda s: None).complete("s", "u")
        with self.assertRaises(Disruption):
            Resilient([Script("a", [Transient("x")] * 3)], retries=2, sleep=lambda s: None).complete("s", "u")

    def test_outage_wait_recovers(self):
        p = Script("a", [Transient("x"), Transient("x"), Reply("back")])
        r = Resilient([p], retries=1, outage_wait=600, sleep=lambda s: None)
        self.assertEqual(r.complete("s", "u"), "back")


class Resume(unittest.TestCase):
    def test_outage_pauses_then_resume_completes_without_replanning(self):
        ws = tempfile.mkdtemp()
        brain = Brain()
        down = Script("down", [Transient("503")] * 4)
        e1 = make(ws, [down], brain)
        e1.start("make hello", "coding", CRIT)
        s1 = e1.run()
        self.assertEqual(s1["status"], "paused")
        self.assertEqual(s1["stage"], "work")
        self.assertEqual(brain.planner_calls, 1)

        up = Script("up", [write_call(), Reply("done")])  # a different provider picks up the run
        e2 = make(ws, [up], brain)
        e2.start()
        s2 = e2.run()
        self.assertEqual(s2["status"], "passed")
        self.assertEqual(brain.planner_calls, 1, "plan must not be redone on resume")
        self.assertEqual(s2["failed"], [])

    def test_resume_mid_transcript_does_not_repeat_finished_turns(self):
        ws = tempfile.mkdtemp()
        brain = Brain()
        ex1 = Script("m1", [write_call(), Transient("cut"), Transient("cut")])
        e1 = make(ws, [ex1], brain, retries=1)
        e1.start("make hello", "coding", CRIT)
        self.assertEqual(e1.run()["status"], "paused")
        self.assertEqual(ex1.calls, 3)
        t = Store(ws).read("transcript.json")
        self.assertEqual([m["role"] for m in t], ["user", "assistant", "tool"])

        ex2 = Script("m2", [Reply("finished")])
        e2 = make(ws, [ex2], brain)
        e2.start()
        self.assertEqual(e2.run()["status"], "passed")
        self.assertEqual(ex2.calls, 1, "only the missing turn is requested")

    def test_crash_between_assistant_turn_and_tool_execution(self):
        ws = tempfile.mkdtemp()
        brain = Brain()
        e1 = make(ws, [Script("m1", [Reply("ok")])], brain)
        e1.start("make hello", "coding", CRIT)
        e1.step_route(); e1.step_criteria(); e1.step_plan()
        Store(ws).write("transcript.json", [
            {"role": "user", "text": "go"},
            {"role": "assistant", "text": "", "calls": [{"id": "t1", "name": "write_file",
                                                          "args": {"path": "hello.txt", "content": "hi"}}]}])
        ex = Script("m2", [Reply("done")])
        e2 = make(ws, [ex], brain)
        e2.start()
        self.assertEqual(e2.run()["status"], "passed")  # tools ran on resume, then one model turn

    def test_failed_verification_loops_then_passes(self):
        ws = tempfile.mkdtemp()
        brain = Brain()
        ex = Script("m", [Reply("claims done without writing"), write_call(), Reply("done")])
        e = make(ws, [ex], brain)
        e.start("make hello", "coding", CRIT)
        s = e.run()
        self.assertEqual(s["status"], "passed")
        self.assertEqual(s["round"], 2)

    def test_lock_blocks_concurrent_runs(self):
        ws = tempfile.mkdtemp()
        st = Store(ws)
        st.path("lock").write_text(str(os.getppid()))
        with self.assertRaises(Locked):
            with st.lock():
                pass

    def test_stale_lock_is_taken_over(self):
        ws = tempfile.mkdtemp()
        st = Store(ws)
        st.path("lock").write_text("999999")
        with st.lock():
            pass


class Portability(unittest.TestCase):
    MSGS = [{"role": "user", "text": "hi"},
            {"role": "assistant", "text": "", "calls": [{"id": "c1", "name": "read_file", "args": {"path": "a"}}]},
            {"role": "tool", "results": [{"id": "c1", "name": "read_file", "content": "data"}]}]

    def test_anthropic_wire(self):
        w = AnthropicProvider.to_wire(self.MSGS)
        self.assertEqual(w[1]["content"][0]["type"], "tool_use")
        self.assertEqual(w[2]["content"][0]["type"], "tool_result")
        self.assertEqual(w[2]["content"][0]["tool_use_id"], "c1")

    def test_openai_wire(self):
        w = OpenAICompatProvider.to_wire("sys", self.MSGS)
        self.assertEqual(w[0]["role"], "system")
        self.assertEqual(json.loads(w[2]["tool_calls"][0]["function"]["arguments"]), {"path": "a"})
        self.assertEqual((w[3]["role"], w[3]["tool_call_id"]), ("tool", "c1"))

    def test_command_provider_as_text_role_and_native_agent(self):
        self.assertEqual(CommandProvider("c", "cat").complete("S", "hello").strip(), "S\n\nhello")
        ws = tempfile.mkdtemp()
        cp = CommandProvider("agent", "echo made > out.txt; echo finished", native_agent=True)
        text = CommandProvider("text", "cat")
        self.assertTrue(Resilient([text, cp], sleep=lambda s: None).native_agent)
        self.assertIn("finished", Resilient([cp], sleep=lambda s: None).agent("", "do it", ws))
        self.assertTrue((pathlib.Path(ws) / "out.txt").exists())


if __name__ == "__main__":
    unittest.main()
