#!/usr/bin/env python3
"""
轻量 LLM 调用模块 — 用于 artbot 后端同步调用 AI
"""
import json
import os
import urllib.request

# Load API key from OpenClaw agent auth
def _load_moonshot_key() -> str:
    paths = [
        os.path.expanduser("~/.openclaw/agents/coding/agent/auth.json"),
        os.path.expanduser("~/.openclaw/agents/main/agent/auth.json"),
    ]
    for p in paths:
        try:
            with open(p) as f:
                d = json.load(f)
            key = d.get("moonshot", {}).get("key", "")
            if key:
                return key
        except Exception:
            continue
    return os.environ.get("MOONSHOT_API_KEY", "")


def chat(prompt: str, model: str = "moonshot-v1-8k", temperature: float = 0.8,
         max_tokens: int = 1000) -> str:
    """Simple synchronous chat completion via Moonshot API."""
    api_key = _load_moonshot_key()
    if not api_key:
        raise RuntimeError("No Moonshot API key found")

    body = json.dumps({
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": temperature,
        "max_tokens": max_tokens,
    }).encode()

    req = urllib.request.Request(
        "https://api.moonshot.cn/v1/chat/completions",
        data=body,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
    )

    with urllib.request.urlopen(req, timeout=30) as resp:
        result = json.loads(resp.read())
    
    return result["choices"][0]["message"]["content"].strip()
