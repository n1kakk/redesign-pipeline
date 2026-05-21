#!/usr/bin/env python3
"""
vLLM client for the redesign pipeline.
Uses OpenAI-compatible API — default: https://rixtrema.net/api/vllm/v1

Config via environment variables (override defaults):
  VLLM_BASE   — API endpoint URL
  VLLM_KEY    — API key
  VLLM_MODEL  — model name (if not set, queries /v1/models)

Usage:
    from vllm_client import query, resolve_model
    html = query(prompt_text)
"""
import os, sys, json
from openai import OpenAI
from typing import Optional

BASE = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))

# ── config (from env, fallback to defaults) ────────────────────────────
VLLM_BASE = os.environ.get(
    "VLLM_BASE",
    "https://rixtrema.net/api/vllm/v1"
)
VLLM_KEY = os.environ.get("VLLM_KEY", "")

# Maximum tokens for generation (adjust per model)
MAX_TOKENS = 8192

# ── client ──────────────────────────────────────────────────────────────
_client = OpenAI(base_url=VLLM_BASE, api_key=VLLM_KEY)


def resolve_model() -> str:
    """Get the model name from env var or by querying /v1/models."""
    if m := os.environ.get("VLLM_MODEL"):
        return m
    models = _client.models.list()
    if not models.data:
        raise RuntimeError("No models returned from vLLM endpoint")
    return models.data[0].id


def query(
    prompt: str,
    model: Optional[str] = None,
    temperature: float = 0.1,
    max_tokens: int = MAX_TOKENS,
    system_msg: Optional[str] = None,
) -> str:
    """Send a prompt to vLLM and return the generated text."""
    model = model or resolve_model()
    messages = []
    if system_msg:
        messages.append({"role": "system", "content": system_msg})
    messages.append({"role": "user", "content": prompt})

    response = _client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens,
        extra_body={"repetition_penalty": 1.1},
    )
    msg = response.choices[0].message
    content = msg.content or msg.reasoning or ""
    # Strip markdown fences if model wraps output
    if content.startswith("```html"):
        content = content[7:]
    elif content.startswith("```"):
        content = content[3:]
    if content.endswith("```"):
        content = content[:-3]
    return content.strip()


def generate_html(
    prompt_text: str,
    prompt_source: str = "",
    model: Optional[str] = None,
    out_path: Optional[str] = None,
) -> str:
    """
    Generate HTML from a design prompt.
    Extracts HTML from the response (strips markdown fences if present).
    """
    html = query(prompt_text, model=model, temperature=0.1)

    if out_path:
        os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(html)
        print(f"[vllm] HTML saved: {out_path} ({len(html)} chars)")

    return html


# ── quick test ──────────────────────────────────────────────────────────
if __name__ == "__main__":
    model = resolve_model()
    print(f"vLLM endpoint: {VLLM_BASE}")
    print(f"vLLM model:    {model}")
    print(f"vLLM key set:  {'YES' if VLLM_KEY else 'NO'}")
    test = query("Say hello in 5 words or less.")
    print(f"Test response: {test}")

