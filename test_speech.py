"""
test_speech.py — Build the speech prompt for a single scenario and query the LLM.

Usage (simplified)
------------------
Just edit the variables in the CONFIG section below and run:

    python test_speech.py

Requirements
------------
- Python 3.9+
- `pip install openai>=1.0.0`
- OPENAI_API_KEY in environment (unless DRY_RUN=True)
"""
from __future__ import annotations
import json
from pathlib import Path

from llm import chat as llm_chat

# ============================================================
# CONFIGURATION — edit these variables as you like
# ============================================================
PROMPT_FILE = "./speech_prompt.py"      # Path to speech_prompt.py
SCENARIO_FILE = "./scenario.json"       # Path to scenario.json
SCENARIO_ID = "S6"  # Scenario id to run
ROLE = "werewolf"                       # "werewolf" or "villager"

# LLM settings
MODEL = "gpt-4o"
TEMPERATURE = 0.5
MAX_TOKENS = None
DRY_RUN = False                         # True: only print prompt, don't call API

# Prompt overrides (Japanese-only; fixed output length)
OVERRIDES = {
    "risk_tolerance": "medium",       # "low" | "medium" | "high"
    "aggression": "medium",           # "low" | "medium" | "high"
    "persona_tone": "assertive",     # calm | assertive | apologetic | analytical
    "include_examples": True,
}
# ============================================================

import importlib.util
import sys
from typing import Any, Dict

def load_module_from_path(path: str):
    spec = importlib.util.spec_from_file_location("speech_prompt_mod", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot import module from {path}")
    mod = importlib.util.module_from_spec(spec)
    sys.modules["speech_prompt_mod"] = mod
    spec.loader.exec_module(mod)  # type: ignore
    return mod

def load_scenario(scenario_path: str, scenario_id: str) -> Dict[str, Any]:
    data = json.loads(Path(scenario_path).read_text(encoding="utf-8"))
    if "groups" in data:
        for g in data["groups"]:
            for s in g.get("scenarios", []):
                if s.get("id") == scenario_id:
                    return s
    if "scenarios" in data:
        for s in data["scenarios"]:
            if s.get("id") == scenario_id:
                return s
    raise KeyError(f"Scenario id not found: {scenario_id}")

def main():
    mod = load_module_from_path(PROMPT_FILE)
    if not hasattr(mod, "build_speech_prompt"):
        raise AttributeError("speech_prompt.py must export build_speech_prompt()")

    scenario = load_scenario(SCENARIO_FILE, SCENARIO_ID)
    prompt = mod.build_speech_prompt(role=ROLE, scenario=scenario, overrides=OVERRIDES)

    sep = "=" * 40
    print(sep)
    print(f"[PROMPT — role={ROLE}, scenario={SCENARIO_ID}]")
    print(sep)
    print(prompt)
    print(sep)

    if DRY_RUN:
        print("[DRY-RUN] Skipping OpenAI call.")
        return

    text = llm_chat(
        prompt,
        model=MODEL,
        temperature=TEMPERATURE,
        max_tokens=MAX_TOKENS,
    )

    print("[LLM OUTPUT]")
    print(sep)
    print(text.strip())
    print(sep)

if __name__ == "__main__":
    main()
