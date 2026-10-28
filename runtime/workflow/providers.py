"""Provider-neutral model layer (stdlib only).

Internal message format (what gets checkpointed to disk, so a run can resume on a different model):
  {"role": "user", "text": str}
  {"role": "assistant", "text": str, "calls": [{"id", "name", "args"}]}
  {"role": "tool", "results": [{"id", "name", "content"}]}
Tool spec: {"name", "description", "schema"}  (JSON Schema)
"""
import json
import os
import random
import socket
import subprocess
import time
import urllib.error
import urllib.request


class Transient(Exception):
    """Retryable: rate limit, overload, 5xx, network, timeout."""

    def __init__(self, msg, retry_after=None):
        super().__init__(msg)
        self.retry_after = retry_after


class Fatal(Exception):
    """Not retryable on this provider: auth, bad request, missing command."""


class Disruption(Exception):
    """Every provider is unavailable right now. State is safe on disk; resume later."""


class Reply:
    def __init__(self, text="", calls=None, tokens=0, stop=""):
        self.text, self.calls, self.tokens, self.stop = text, calls or [], tokens, stop


def http_json(url, headers, body, timeout=180):
    req = urllib.request.Request(url, data=json.dumps(body).encode(), method="POST",
                                 headers={"content-type": "application/json", **headers})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        detail = e.read().decode(errors="replace")[:500]
        ra = e.headers.get("retry-after") if e.headers else None
        try:
            ra = float(ra) if ra else None
        except ValueError:
            ra = None
        if e.code in (408, 409, 425, 429) or e.code >= 500:  # 529 = overloaded
            raise Transient(f"HTTP {e.code}: {detail}", ra)
        raise Fatal(f"HTTP {e.code}: {detail}")
    except (urllib.error.URLError, socket.timeout, TimeoutError, ConnectionError, ValueError) as e:
        raise Transient(f"network/decode: {e}")


class Provider:
    name = "provider"
    native_agent = False  # True: the provider is itself an agent that works in the workspace

    def chat(self, system, messages, tools=None, max_tokens=4096):
        raise NotImplementedError

    def complete(self, system, user, max_tokens=4096):
        return self.chat(system, [{"role": "user", "text": user}], None, max_tokens).text


class AnthropicProvider(Provider):
    def __init__(self, name, model, api_key_env="ANTHROPIC_API_KEY", base_url="https://api.anthropic.com", **_):
        self.name, self.model, self.key_env, self.base = name, model, api_key_env, base_url.rstrip("/")

    @staticmethod
    def to_wire(messages):
        out = []
        for m in messages:
            if m["role"] == "user":
                out.append({"role": "user", "content": m["text"]})
            elif m["role"] == "assistant":
                blocks = [{"type": "text", "text": m["text"]}] if m.get("text") else []
                blocks += [{"type": "tool_use", "id": c["id"], "name": c["name"], "input": c["args"]}
                           for c in m.get("calls", [])]
                out.append({"role": "assistant", "content": blocks or [{"type": "text", "text": "(no output)"}]})
            else:
                out.append({"role": "user", "content": [
                    {"type": "tool_result", "tool_use_id": r["id"], "content": r["content"]} for r in m["results"]]})
        return out

    def chat(self, system, messages, tools=None, max_tokens=4096):
        key = os.getenv(self.key_env, "")
        if not key:
            raise Fatal(f"{self.key_env} is not set")
        body = {"model": self.model, "max_tokens": max_tokens, "system": system,
                "messages": self.to_wire(messages)}
        if tools:
            body["tools"] = [{"name": t["name"], "description": t["description"], "input_schema": t["schema"]}
                             for t in tools]
        d = http_json(f"{self.base}/v1/messages", {"x-api-key": key, "anthropic-version": "2023-06-01"}, body)
        text = "".join(b.get("text", "") for b in d.get("content", []) if b.get("type") == "text")
        calls = [{"id": b["id"], "name": b["name"], "args": b.get("input", {})}
                 for b in d.get("content", []) if b.get("type") == "tool_use"]
        u = d.get("usage", {})
        return Reply(text, calls, u.get("input_tokens", 0) + u.get("output_tokens", 0), d.get("stop_reason", ""))


class OpenAICompatProvider(Provider):
    """Any server that speaks /chat/completions with tools: OpenAI, Gemini's compat endpoint,
    OpenRouter, Ollama, vLLM, LM Studio, ..."""

    def __init__(self, name, model, base_url="https://api.openai.com/v1", api_key_env="OPENAI_API_KEY",
                 max_tokens_param="max_tokens", **_):
        self.name, self.model, self.base = name, model, base_url.rstrip("/")
        self.key_env, self.mt_param = api_key_env, max_tokens_param

    @staticmethod
    def to_wire(system, messages):
        out = [{"role": "system", "content": system}] if system else []
        for m in messages:
            if m["role"] == "user":
                out.append({"role": "user", "content": m["text"]})
            elif m["role"] == "assistant":
                msg = {"role": "assistant", "content": m.get("text") or None}
                if m.get("calls"):
                    msg["tool_calls"] = [{"id": c["id"], "type": "function",
                                          "function": {"name": c["name"], "arguments": json.dumps(c["args"])}}
                                         for c in m["calls"]]
                out.append(msg)
            else:
                out += [{"role": "tool", "tool_call_id": r["id"], "content": r["content"]} for r in m["results"]]
        return out

    def chat(self, system, messages, tools=None, max_tokens=4096):
        headers = {}
        if self.key_env:
            key = os.getenv(self.key_env, "")
            if not key:
                raise Fatal(f"{self.key_env} is not set")
            headers["authorization"] = f"Bearer {key}"
        body = {"model": self.model, self.mt_param: max_tokens, "messages": self.to_wire(system, messages)}
        if tools:
            body["tools"] = [{"type": "function", "function": {"name": t["name"], "description": t["description"],
                                                               "parameters": t["schema"]}} for t in tools]
        d = http_json(f"{self.base}/chat/completions", headers, body)
        try:
            msg = d["choices"][0]["message"]
        except (KeyError, IndexError):
            raise Transient(f"malformed response: {str(d)[:200]}")
        calls = []
        for c in msg.get("tool_calls") or []:
            try:
                args = json.loads(c["function"].get("arguments") or "{}")
            except ValueError:
                args = {}
            calls.append({"id": c["id"], "name": c["function"]["name"], "args": args})
        u = d.get("usage", {})
        return Reply(msg.get("content") or "", calls, u.get("prompt_tokens", 0) + u.get("completion_tokens", 0),
                     d["choices"][0].get("finish_reason", ""))


class CommandProvider(Provider):
    """Wrap any CLI that reads a prompt on stdin and prints text (check your CLI's headless flags).
    native_agent=True means the CLI does its own file/tool work inside the workspace."""

    def __init__(self, name, command, native_agent=False, timeout=1800, **_):
        self.name, self.command, self.native_agent, self.timeout = name, command, native_agent, timeout

    def run(self, prompt, cwd=None):
        try:
            p = subprocess.run(self.command, shell=True, input=prompt, capture_output=True, text=True,
                               cwd=cwd, timeout=self.timeout)
        except subprocess.TimeoutExpired:
            raise Transient("command timed out")
        if p.returncode == 127:
            raise Fatal(f"command not found: {self.command}")
        if p.returncode != 0:
            raise Transient(f"exit {p.returncode}: {(p.stderr or p.stdout)[-300:]}")
        return p.stdout

    def chat(self, system, messages, tools=None, max_tokens=4096):
        if tools:
            raise Fatal("command providers cannot do tool calling; use them for text roles or as native_agent")
        parts = [system] if system else []
        for m in messages:
            parts.append(m.get("text", ""))
        return Reply(self.run("\n\n".join(parts)))

    def run_agent(self, system, prompt, cwd):
        return self.run((system + "\n\n" if system else "") + prompt, cwd=cwd)


class Resilient:
    """Retries with backoff+jitter, honors Retry-After, falls back down the chain, and can wait out an outage."""

    def __init__(self, chain, retries=5, base_delay=2.0, max_delay=60.0, outage_wait=0, sleep=time.sleep,
                 log=lambda **k: None):
        self.chain, self.retries, self.base, self.cap = chain, retries, base_delay, max_delay
        self.outage_wait, self.sleep, self.log = outage_wait, sleep, log
        self.last_provider = chain[0].name

    @property
    def native_agent(self):
        return self.chain[0].native_agent

    def _try(self, method, chain, *a, **kw):
        deadline = time.time() + self.outage_wait
        while True:
            fatal = []
            for p in chain:
                for attempt in range(self.retries + 1):
                    try:
                        r = getattr(p, method)(*a, **kw)
                        self.last_provider = p.name
                        return r
                    except Transient as e:
                        self.log(event="transient", provider=p.name, attempt=attempt, error=str(e)[:200])
                        if attempt == self.retries:
                            break
                        delay = e.retry_after or min(self.cap, self.base * 2 ** attempt) * random.uniform(0.5, 1.0)
                        self.sleep(delay)
                    except Fatal as e:
                        self.log(event="fatal", provider=p.name, error=str(e)[:200])
                        fatal.append(f"{p.name}: {e}")
                        break
            if len(fatal) == len(chain):
                raise Fatal("; ".join(fatal))
            if time.time() >= deadline:
                raise Disruption("all providers unavailable: " + ", ".join(p.name for p in chain))
            self.log(event="waiting_for_recovery")
            self.sleep(min(60, max(1, deadline - time.time())))

    def chat(self, system, messages, tools=None, max_tokens=4096):
        return self._try("chat", self.chain, system, messages, tools, max_tokens)

    def complete(self, system, user, max_tokens=4096):
        return self.chat(system, [{"role": "user", "text": user}], None, max_tokens).text

    def agent(self, system, prompt, cwd):
        agents = [p for p in self.chain if p.native_agent]
        return self._try("run_agent", agents, system, prompt, cwd)


def build_provider(name, spec):
    if not isinstance(spec, dict):
        raise ValueError(f"provider {name!r} must be a JSON object with a type")
    t = spec.get("type")
    if t == "anthropic":
        return AnthropicProvider(name, **{k: v for k, v in spec.items() if k != "type"})
    if t == "openai_compat":
        return OpenAICompatProvider(name, **{k: v for k, v in spec.items() if k != "type"})
    if t == "command":
        return CommandProvider(name, **{k: v for k, v in spec.items() if k != "type"})
    raise ValueError(f"unknown provider type for {name}: {t}")
