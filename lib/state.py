#!/usr/bin/env python3
"""
Pipeline state tracker — writes/reads pipeline_state.json so nexus can show agent progress.

Usage:
    from pipeline.state import set_state, AgentState
    set_state(site="oxfordharriman", step="generate", status="running",
              message="Generating HTML via RixTrema...")
"""
import json, os, time

STATE_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "pipeline", "outputs", "v2", "pipeline_state.json"
)

STEPS = [
    "parse",
    "generate",
    "vision_qa",
    "apply_fixes",
    "screenshot",
    "qa",
    "fix_loop",
    "done"
]

def set_state(site="", step="", status="idle", message="", progress=0,
              completed_sites=None, model="", vision_backend="",
              error=""):
    """Write current pipeline state for nexus to read."""
    state = {
        "status": status,           # idle | running | error | done
        "current_site": site,
        "current_step": step,
        "current_step_index": STEPS.index(step) if step in STEPS else -1,
        "total_steps": len(STEPS),
        "message": message,
        "progress": progress,        # 0-100
        "started_at": None,
        "completed_sites": completed_sites or [],
        "model": model,
        "vision_backend": vision_backend,
        "error": error,
        "updated_at": time.time(),
    }

    # Preserve started_at from previous state
    if os.path.exists(STATE_PATH):
        try:
            prev = json.load(open(STATE_PATH, encoding="utf-8"))
            state["started_at"] = prev.get("started_at", state["started_at"])
            if not state["completed_sites"]:
                state["completed_sites"] = prev.get("completed_sites", [])
        except:
            pass

    if status == "running" and not state["started_at"]:
        state["started_at"] = time.time()

    os.makedirs(os.path.dirname(STATE_PATH), exist_ok=True)
    with open(STATE_PATH, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2, ensure_ascii=False)


def get_state():
    """Read current pipeline state."""
    if os.path.exists(STATE_PATH):
        try:
            return json.load(open(STATE_PATH, encoding="utf-8"))
        except:
            pass
    return {
        "status": "idle",
        "current_site": "",
        "current_step": "",
        "current_step_index": -1,
        "total_steps": 7,
        "message": "No pipeline running",
        "progress": 0,
        "started_at": None,
        "completed_sites": [],
        "model": "",
        "vision_backend": "",
        "error": "",
        "updated_at": time.time(),
    }


def reset():
    """Reset pipeline state to idle."""
    if os.path.exists(STATE_PATH):
        os.remove(STATE_PATH)


if __name__ == "__main__":
    import sys
    if "--reset" in sys.argv:
        reset()
        print("Pipeline state reset")
    else:
        print(json.dumps(get_state(), indent=2))

