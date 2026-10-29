"""On-disk state. Everything needed to resume lives in <workspace>/.wf/ (atomic writes, append-only journal)."""
import contextlib
import json
import os
import pathlib
import time


class Locked(Exception):
    pass


class StateError(ValueError):
    pass


def _alive(pid):
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return True
    return True


class Store:
    def __init__(self, workspace):
        self.ws = pathlib.Path(workspace).resolve()
        self.dir = self.ws / ".wf"
        self.dir.mkdir(parents=True, exist_ok=True)

    def path(self, name):
        return self.dir / name

    def write(self, name, data, text=False):
        p = self.path(name)
        tmp = p.with_name(p.name + ".tmp")
        with open(tmp, "w") as f:
            f.write(data if text else json.dumps(data, indent=1, default=str))
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, p)  # atomic: a crash leaves either the old or the new file, never half of one

    def read(self, name, default=None, text=False, strict=False):
        p = self.path(name)
        if not p.exists():
            return default
        raw = p.read_text()
        if text:
            return raw
        try:
            return json.loads(raw)
        except ValueError as e:
            if strict:
                raise StateError(f"{name} is not valid JSON: {e}") from e
            return default

    def append(self, name, line):
        with open(self.path(name), "a") as f:
            f.write(line)
            f.flush()
            os.fsync(f.fileno())

    def journal(self, **kw):
        self.append("journal.jsonl", json.dumps({"ts": round(time.time(), 1), **kw}, default=str) + "\n")

    def delete(self, name):
        with contextlib.suppress(FileNotFoundError):
            self.path(name).unlink()

    @contextlib.contextmanager
    def lock(self):
        p = self.path("lock")
        for _ in range(2):
            try:
                fd = os.open(p, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                os.write(fd, str(os.getpid()).encode())
                os.close(fd)
                break
            except FileExistsError:
                try:
                    pid = int(p.read_text() or 0)
                except (ValueError, OSError):
                    pid = 0
                if pid and _alive(pid) and pid != os.getpid():
                    raise Locked(f"another run (pid {pid}) is using this workspace")
                with contextlib.suppress(FileNotFoundError):
                    p.unlink()  # stale lock from a crashed run
        else:
            raise Locked("could not acquire workspace lock")
        try:
            yield
        finally:
            with contextlib.suppress(FileNotFoundError):
                p.unlink()
