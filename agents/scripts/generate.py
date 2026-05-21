#!/usr/bin/env python3
"""Agent: Generate HTML. Usage: python pipeline/agents/generate.py <url>"""
import json, os, sys, subprocess, time

BASE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PIPE = os.path.join(BASE, "pipeline")
SITES = os.path.join(PIPE, "sites")

def set_state(step="", msg="", progress=0):
    sp = os.path.join(PIPE, "outputs", "v2", "pipeline_state.json")
    steps = ["parse","generate","vision_qa","apply_fixes","screenshot","qa","fix_loop","done"]
    s = {"status": "running", "current_site": "", "current_step": step,
         "current_step_index": steps.index(step) if step in steps else -1,
         "total_steps": 7, "message": msg, "progress": progress,
         "updated_at": time.time(), "started_at": None,
         "completed_sites": [], "model": os.environ.get("VLLM_MODEL", "RixTrema"),
         "vision_backend": os.environ.get("VISION_BACKEND", "gateway"), "error": ""}
    if os.path.exists(sp):
        try:
            prev = json.load(open(sp, encoding="utf-8"))
            s["started_at"] = prev.get("started_at")
            s["completed_sites"] = prev.get("completed_sites", [])
        except: pass
    if not s["started_at"]: s["started_at"] = time.time()
    json.dump(s, open(sp, "w", encoding="utf-8"), indent=2, ensure_ascii=False)

def run(cmd, timeout=300):
    r = subprocess.run(cmd, shell=True, capture_output=True, text=True, cwd=BASE, timeout=timeout)
    if r.returncode != 0: print("ERROR:", r.stderr.strip()[:300]); return False
    if r.stdout.strip(): print(r.stdout.strip()[:1500])
    return True

def main():
    url = sys.argv[1] if len(sys.argv) > 1 else ""
    if not url: print("Usage: python pipeline/agents/02_generate.py <url>"); return 1
    from urllib.parse import urlparse
    domain = urlparse(url).netloc.lower().split(".")[0]
    set_state("generate", "Building prompt and generating HTML for " + domain + "...", 15)
    site_dir = os.path.join(SITES, domain)
    os.makedirs(site_dir, exist_ok=True)
    if not run('python pipeline/generate/build_prompt.py --generate', timeout=300): return 1
    v2 = os.path.join(PIPE, "outputs", "v2")
    import shutil
    for f in ["final.html", "harmony_prompt.txt"]:
        src = os.path.join(v2, f)
        if os.path.exists(src):
            shutil.copy2(src, os.path.join(site_dir, f))
            sz = os.path.getsize(src)
            print("Copied", f, "(" + str(sz) + " bytes)")
    set_state("generate", "HTML generated for " + domain, 25)
    return 0

if __name__ == "__main__":
    sys.exit(main())


