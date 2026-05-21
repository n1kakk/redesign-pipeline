#!/usr/bin/env python3
"""Agent: Parse site, sets pipeline state. Usage: python pipeline/agents/parse.py <url>"""
import json, os, sys, subprocess, time

BASE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PIPE = os.path.join(BASE, "pipeline")
SITES = os.path.join(PIPE, "sites")

def set_state(step="", msg="", progress=0):
    sp = os.path.join(PIPE, "outputs", "v2", "pipeline_state.json")
    s = {"status": "running", "current_site": "", "current_step": step,
         "current_step_index": ["parse","generate","vision_qa","apply_fixes",
                                "screenshot","qa","fix_loop","done"].index(step) if step in [
            "parse","generate","vision_qa","apply_fixes","screenshot","qa","fix_loop","done"] else -1,
         "total_steps": 7, "message": msg, "progress": progress,
         "updated_at": time.time(), "started_at": None,
         "completed_sites": [], "model": "", "vision_backend": "", "error": ""}
    if os.path.exists(sp):
        try:
            prev = json.load(open(sp, encoding="utf-8"))
            s["started_at"] = prev.get("started_at")
            s["completed_sites"] = prev.get("completed_sites", [])
        except: pass
    if not s["started_at"]: s["started_at"] = time.time()
    json.dump(s, open(sp, "w", encoding="utf-8"), indent=2, ensure_ascii=False)

def run(cmd, timeout=120):
    r = subprocess.run(cmd, shell=True, capture_output=True, text=True, cwd=BASE, timeout=timeout)
    if r.returncode != 0: print("ERROR:", r.stderr.strip()[:300]); return False
    if r.stdout.strip(): print(r.stdout.strip()[:1000])
    return True

def main():
    url = sys.argv[1] if len(sys.argv) > 1 else ""
    if not url: print("Usage: python pipeline/agents/01_parse.py <url>"); return 1
    from urllib.parse import urlparse
    domain = urlparse(url).netloc.lower().split(".")[0]
    set_state("parse", "Downloading and parsing " + domain + "...", 5)
    site_dir = os.path.join(SITES, domain)
    os.makedirs(site_dir, exist_ok=True)
    raw_path = os.path.join(PIPE, "outputs", "raw_homepage.html")
    subprocess.run('curl.exe -sL "' + url + '" -o "' + raw_path + '"', shell=True, cwd=BASE, timeout=30)
    if not run("python pipeline/parse/parse_site.py", timeout=60): return 1
    parsed_path = os.path.join(PIPE, "outputs", "parsed_site.json")
    if os.path.exists(parsed_path):
        import shutil
        shutil.copy2(parsed_path, os.path.join(site_dir, "parsed_site.json"))
        sz = os.path.getsize(parsed_path)
        print("Parsed:", sz, "bytes ->", site_dir)
    set_state("parse", "Parse complete for " + domain, 10)
    return 0

if __name__ == "__main__":
    sys.exit(main())



