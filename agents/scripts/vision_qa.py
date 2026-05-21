import json, time
PIPE = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "pipeline")
def set_state(step="", msg="", progress=0):
    sp = os.path.join(PIPE, "outputs", "v2", "pipeline_state.json")
    steps = ["parse","generate","vision_qa","apply_fixes","screenshot","qa","fix_loop","done"]
    s = {"status":"running","current_site":"","current_step":step,"current_step_index":steps.index(step)if step in steps else -1,"total_steps":7,"message":msg,"progress":progress,"updated_at":time.time(),"started_at":None,"completed_sites":[],"model":os.environ.get("VLLM_MODEL","RixTrema"),"vision_backend":os.environ.get("VISION_BACKEND","gateway"),"error":""}
    if os.path.exists(sp):
        try:
            prev=json.load(open(sp,encoding="utf-8"))
            s["started_at"]=prev.get("started_at")
            s["completed_sites"]=prev.get("completed_sites",[])
        except: pass
    if not s["started_at"]: s["started_at"]=time.time()
    json.dump(s,open(sp,"w",encoding="utf-8"),indent=2,ensure_ascii=False)#!/usr/bin/env python3
"""
Agent: Vision QA — сравнить оригинальные скриншоты сгенерированным HTML через GPT-4o.

Запуск:  python pipeline/agents/03_vision_qa.py <domain>
Выход:   pipeline/outputs/v2/vision_corrections.json
"""
import os, sys, subprocess

BASE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PIPE = os.path.join(BASE, "pipeline")

def run(cmd, timeout=120):
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True, cwd=BASE, timeout=timeout)
    if result.returncode != 0:
        print(f"ERROR: {result.stderr.strip()[:300]}")
        return False
    if result.stdout.strip():
        print(result.stdout.strip()[:1500])
    return True

def main():
    domain = sys.argv[1] if len(sys.argv) > 1 else ""
    if not domain:
        print("Usage: python pipeline/agents/vision_qa.py <domain>")
        return 1

    # 1. Take original screenshots
    print("Taking original site screenshots...")
    run('node pipeline/screenshot/original.js', timeout=60)

    # 2. Build vision prompt
    print("Building vision prompt...")
    run('python pipeline/vision/advisor.py', timeout=30)

    # 3. Run vision QA
    print("Running vision QA via GPT-4o...")
    vision_backend = os.environ.get("VISION_BACKEND", "gateway")
    if vision_backend == "rixtrema":
        run('python pipeline/vision/evaluate.py --backend rixtrema', timeout=180)
    else:
        run('python pipeline/vision/evaluate.py', timeout=180)

    # Show results
    corr_path = os.path.join(PIPE, "outputs", "v2", "vision_corrections.json")
    if os.path.exists(corr_path):
        import json
        corr = json.load(open(corr_path, encoding='utf-8'))
        assessment = corr.get('overall_assessment', {})
        print(f"Score: {assessment.get('score', '?')}/10")
        print(f"Image fixes: {len(corr.get('image_corrections', []))}")
        print(f"Color fixes: {len(corr.get('color_rhythm_fixes', []))}")

    return 0

if __name__ == "__main__":
    sys.exit(main())


