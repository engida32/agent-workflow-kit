"""Token and cost accounting, read from state.json and config pricing.

Providers report a token count per call but no price. A config may declare
``"pricing": {"<provider>": {"usd_per_mtok": <number>}}``. Without it a stage
reports tokens and ``cost_usd: null`` rather than a guessed number.
"""

from __future__ import annotations


def record(state: dict, role: str, provider: str, tokens: int) -> None:
    entry = state.setdefault("spend", {}).setdefault(role, {"calls": 0, "tokens": 0, "providers": {}})
    tokens = int(tokens or 0)
    entry["calls"] += 1
    entry["tokens"] += tokens
    entry["providers"][provider] = entry["providers"].get(provider, 0) + tokens


def rate_for(pricing: dict, provider: str):
    spec = pricing.get(provider)
    if isinstance(spec, dict):
        rate = spec.get("usd_per_mtok")
        if isinstance(rate, (int, float)) and not isinstance(rate, bool):
            return float(rate)
    return None


def summarize(state: dict, config: dict | None = None) -> dict:
    spend = state.get("spend") or {}
    pricing = (config or {}).get("pricing") or {}
    stages = {}
    unpriced = set()
    total = 0.0
    complete = True
    for role, entry in sorted(spend.items()):
        providers = dict(entry.get("providers") or {})
        usd = 0.0
        priced_here = True
        for name, tokens in providers.items():
            rate = rate_for(pricing, name)
            if rate is None:
                priced_here = False
                unpriced.add(name)
            else:
                usd += tokens / 1_000_000 * rate
        total += usd
        complete = complete and priced_here
        stages[role] = {
            "calls": entry.get("calls", 0),
            "tokens": entry.get("tokens", 0),
            "providers": providers,
            "cost_usd": round(usd, 6) if priced_here else None,
        }
    return {
        "tokens": state.get("tokens", 0),
        "stages": stages,
        "cost_usd": round(total, 6) if complete else None,
        "unpriced": sorted(unpriced),
    }
