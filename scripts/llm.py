#!/usr/bin/env python3
"""scripts/llm.py

LLM 调用中间层（artbot 同步调用）。

支持两种后端：

1) moonshot（默认）：脚本直连 Moonshot API。
2) openclaw：通过 `openclaw agent` 让某个 OpenClaw agent 作为“中枢模型调用器”。
   - 这样可以把“用哪个模型”收敛到 agent 配置上（例如该 agent 用 Copilot/Kimi/Claude）。

配置：
- ARTBOT_LLM_BACKEND=moonshot|openclaw   (默认 moonshot)
- ARTBOT_OPENCLAW_AGENT_ID=<agent_id>   (openclaw 后端下必填/建议；默认 main)
- ARTBOT_OPENCLAW_TIMEOUT=60            (秒；默认 90)

注意：openclaw 后端是“让 agent 回答一次”，因此 model/temperature/max_tokens 参数
无法逐一映射到所有 provider；目前会尽量保持接口兼容，但 openclaw 可能忽略这些参数。
"""

import json
import os
import subprocess
import urllib.request
from typing import Any


def _backend() -> str:
    return (os.environ.get("ARTBOT_LLM_BACKEND") or "moonshot").strip().lower()


# -----------------------------
# Moonshot direct backend
# -----------------------------

def _load_moonshot_key() -> str:
    """Load API key from OpenClaw agent auth or env."""
    paths = [
        os.path.expanduser("~/.openclaw/agents/coding/agent/auth.json"),
        os.path.expanduser("~/.openclaw/agents/main/agent/auth.json"),
    ]
    for p in paths:
        try:
            with open(p) as f:
                d = json.load(f)
            key = (d.get("moonshot", {}) or {}).get("key", "")
            if key:
                return key
        except Exception:
            continue
    return os.environ.get("MOONSHOT_API_KEY", "")


def _moonshot_chat(prompt: str, model: str, temperature: float, max_tokens: int) -> str:
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


# -----------------------------
# OpenClaw agent backend
# -----------------------------

def _openclaw_agent_id() -> str:
    return (os.environ.get("ARTBOT_OPENCLAW_AGENT_ID") or "main").strip()


def _openclaw_timeout() -> int:
    try:
        return int(os.environ.get("ARTBOT_OPENCLAW_TIMEOUT") or "90")
    except Exception:
        return 90


def _extract_openclaw_text(payload: dict[str, Any]) -> str:
    # Current CLI returns: { payloads: [{text, mediaUrl}, ...], meta: {...}}
    pls = payload.get("payloads") or []
    if not pls:
        return ""
    # Prefer last non-empty text
    for p in reversed(pls):
        t = (p.get("text") or "").strip()
        if t:
            return t
    return (pls[-1].get("text") or "").strip()


def _openclaw_chat(prompt: str, timeout_s: int | None = None) -> str:
    agent_id = _openclaw_agent_id()
    timeout_s = timeout_s or _openclaw_timeout()

    # 强约束输出格式，尽量避免 agent 自说自话。
    wrapped = (
        "你是一个‘LLM 后端’，只负责按要求生成文本。\n"
        "必须严格遵守：仅输出最终结果正文，不要解释、不要寒暄、不要自述过程、不要加前后缀。\n\n"
        "用户需求如下（请直接完成）：\n"
        f"{prompt.strip()}"
    )

    cmd = [
        "openclaw",
        "agent",
        "--agent",
        agent_id,
        "--message",
        wrapped,
        "--json",
        "--timeout",
        str(timeout_s),
    ]

    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"openclaw agent failed: rc={r.returncode} stderr={r.stderr.strip()}")

    try:
        data = json.loads(r.stdout)
    except Exception as e:
        raise RuntimeError(f"openclaw agent returned non-json: {e}; stdout={r.stdout[:500]}")

    # CLI payload shape: {runId,status,summary,result:{payloads:[...]}}
    result = data.get("result") or {}
    text = _extract_openclaw_text(result)
    return (text or "").strip()


# -----------------------------
# Public API
# -----------------------------

def chat(prompt: str, model: str = "moonshot-v1-8k", temperature: float = 0.8,
         max_tokens: int = 1000) -> str:
    """Chat completion.

    - moonshot backend: honors model/temperature/max_tokens.
    - openclaw backend: uses configured agent; may ignore model/temperature/max_tokens.
    """
    be = _backend()
    if be == "openclaw":
        return _openclaw_chat(prompt)

    # default: moonshot direct
    return _moonshot_chat(prompt, model=model, temperature=temperature, max_tokens=max_tokens)
