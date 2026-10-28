"""Regression tests for workspace scanning, verification, and CLI error handling."""
import contextlib
import io
import json
import pathlib
import sys
import tempfile
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from workflow.cli import main, task_skills_dir  # noqa: E402
from workflow.engine import Engine  # noqa: E402
from workflow.providers import Fatal, Provider, Reply  # noqa: E402
from workflow.state import Store  # noqa: E402
from workflow.tools import Tools  # noqa: E402

SKILLS = pathlib.Path(__file__).resolve().parents[2] / "skill" / "task-skills"


class Script(Provider):
    def __init__(self, name, reply):
        self.name, self.reply = name, reply

    @property
    def last_provider(self):
        return self.name

    def chat(self, system, messages, tools=None, max_tokens=4096):
        return self.reply


def state(ws, task="do the thing"):
    Store(ws).write("state.json", {"task": task, "tokens": 0, "providers_used": {},
                                   "limits": {"max_tokens": 100000, "max_seconds": 7200, "verifier_votes": 1}})


class WorkspaceScan(unittest.TestCase):
    def test_list_files_skips_vcs_virtualenv_and_cache_dirs(self):
        with tempfile.TemporaryDirectory() as d:
            ws = pathlib.Path(d)
            (ws / "src").mkdir()
            (ws / "src" / "app.py").write_text("print('hi')")
            for rel in (".git/objects/ab/cdef", "node_modules/pkg/index.js", ".venv/lib/x.py",
                        "__pycache__/app.pyc", ".pytest_cache/v/cache"):
                p = ws / rel
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_text("noise")
            out = Tools(Store(ws), SKILLS, "deny", 120).call("list_files", {})
            self.assertIn("src/app.py", out)
            for noise in (".git", "node_modules", ".venv", "__pycache__", ".pytest_cache"):
                self.assertNotIn(noise, out)

    def test_snapshot_ignores_noise_and_caps_per_file(self):
        with tempfile.TemporaryDirectory() as d:
            ws = pathlib.Path(d)
            (ws / "hello.txt").write_text("deliverable")
            (ws / ".git" / "objects").mkdir(parents=True)
            (ws / ".git" / "objects" / "blob").write_text("git-noise")
            (ws / "big.txt").write_text("A" * 20000)
            snap = Engine(ws, {}, {}, SKILLS).snapshot()
            self.assertIn("hello.txt", snap)
            self.assertIn("deliverable", snap)
            self.assertNotIn("git-noise", snap)
            self.assertNotIn("A" * 6001, snap)


class Verification(unittest.TestCase):
    def test_verifier_dict_results_are_normalized(self):
        with tempfile.TemporaryDirectory() as d:
            ws = pathlib.Path(d)
            state(ws)
            reply = Reply('{"results":[{"id":"r1","passed":true,"reason":"found"}]}', tokens=5)
            eng = Engine(ws, {}, {"verifier": Script("v", reply)}, SKILLS)
            out = eng.verify([{"id": "r1", "text": "x", "kind": "rubric", "must": True}])
            self.assertTrue(out[0]["passed"])
            self.assertEqual(out[0]["reason"], "found")

    def test_verifier_list_results_still_work(self):
        with tempfile.TemporaryDirectory() as d:
            ws = pathlib.Path(d)
            state(ws)
            reply = Reply('[{"id":"r1","passed":true,"reason":"ok"}]', tokens=5)
            eng = Engine(ws, {}, {"verifier": Script("v", reply)}, SKILLS)
            out = eng.verify([{"id": "r1", "text": "x", "kind": "rubric", "must": True}])
            self.assertTrue(out[0]["passed"])

    def test_exec_criterion_matching_deny_list_fails_loudly(self):
        with tempfile.TemporaryDirectory() as d:
            ws = pathlib.Path(d)
            state(ws)
            eng = Engine(ws, {}, {}, SKILLS)
            with self.assertRaises(Fatal) as ctx:
                eng.verify([{"id": "c1", "text": "x", "kind": "exec", "must": True,
                             "command": "mkfs.ext4 -V"}])
            self.assertIn("deny list", str(ctx.exception))


class Cli(unittest.TestCase):
    def test_status_tolerates_partial_state(self):
        with tempfile.TemporaryDirectory() as d:
            ws = pathlib.Path(d)
            Store(ws).write("state.json", {"status": "paused"})
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                rc = main(["status", str(ws)])
            self.assertEqual(rc, 0)
            out = json.loads(buf.getvalue())
            self.assertEqual(out["status"], "paused")
            self.assertIsNone(out["round"])

    def test_version_exits_zero(self):
        with contextlib.redirect_stdout(io.StringIO()):
            with self.assertRaises(SystemExit) as ctx:
                main(["--version"])
        self.assertEqual(ctx.exception.code, 0)

    def test_unknown_role_provider_is_a_clean_error(self):
        with tempfile.TemporaryDirectory() as d:
            ws = pathlib.Path(d)
            cfg = ws / "cfg.json"
            cfg.write_text(json.dumps({"providers": {"ok": {"type": "command", "command": "cat"}},
                                       "roles": {"router": ["ghost"]}}))
            err = io.StringIO()
            with contextlib.redirect_stderr(err):
                rc = main(["run", "task", "-w", str(ws), "--config", str(cfg)])
            self.assertEqual(rc, 2)
            self.assertIn("unknown provider 'ghost'", err.getvalue())

    def test_empty_providers_is_a_clean_error(self):
        with tempfile.TemporaryDirectory() as d:
            ws = pathlib.Path(d)
            cfg = ws / "cfg.json"
            cfg.write_text(json.dumps({"providers": {}}))
            err = io.StringIO()
            with contextlib.redirect_stderr(err):
                rc = main(["run", "task", "-w", str(ws), "--config", str(cfg)])
            self.assertEqual(rc, 2)
            self.assertIn("no providers configured", err.getvalue())
            self.assertNotIn("Traceback", err.getvalue())

    def test_null_provider_spec_is_a_clean_error(self):
        with tempfile.TemporaryDirectory() as d:
            ws = pathlib.Path(d)
            cfg = ws / "cfg.json"
            cfg.write_text(json.dumps({"providers": {"x": None}}))
            err = io.StringIO()
            with contextlib.redirect_stderr(err):
                rc = main(["run", "task", "-w", str(ws), "--config", str(cfg)])
            self.assertEqual(rc, 2)
            self.assertIn("must be a JSON object", err.getvalue())
            self.assertNotIn("Traceback", err.getvalue())

    def test_status_rejects_non_object_state(self):
        with tempfile.TemporaryDirectory() as d:
            ws = pathlib.Path(d)
            Store(ws).write("state.json", [1])
            err = io.StringIO()
            with contextlib.redirect_stderr(err):
                rc = main(["status", str(ws)])
            self.assertEqual(rc, 2)
            self.assertIn("not a JSON object", err.getvalue())
            self.assertNotIn("Traceback", err.getvalue())

    def test_task_skills_resolve_from_source_checkout(self):
        self.assertEqual(task_skills_dir(), SKILLS)
        self.assertTrue((task_skills_dir() / "coding.md").is_file())


if __name__ == "__main__":
    unittest.main()
