#!/usr/bin/env python3
"""
Pipeline Orchestrator v3 — single entry point for automated site redesign.

Usage:
  python pipeline/run.py --full https://example.com
  python pipeline/run.py --full --vision-backend claude https://example.com

Pipeline flow by folders:
  01_parse/        — парсинг оригинального сайта
  02_generate/     — сборка промпта + генерация HTML
  03_vision/       — vision QA (сравнение скринов)
  04_fix/          — применение фиксов + авто-фикс
  05_screenshot/   — Playwright скриншоты
  06_qa/           — Quality Assurance (27 проверок)
  07_judge/        — оценка результатов, фикс-луп
"""
import json, os, sys, subprocess, time

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PIPELINE = os.path.join(BASE, "pipeline")
OUT = os.path.join(BASE, "pipeline", "sites")
PIPE_OUT = os.path.join(BASE, "pipeline", "outputs")
os.makedirs(OUT, exist_ok=True)

# Cross-platform curl
CURL = "curl" if sys.platform != "win32" else "curl.exe"

sys.path.insert(0, os.path.join(PIPELINE, "lib"))
from state import set_state


# ── helpers ────────────────────────────────────────────────────────────

def site_name(url: str) -> str:
    from urllib.parse import urlparse
    domain = urlparse(url).netloc.lower()
    parts = domain.split(".")
    if parts[0] == "www" and len(parts) > 2:
        return parts[1]
    return parts[0]

def run(cmd: str, cwd=None, timeout=120) -> bool:
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True,
                            cwd=cwd or BASE, timeout=timeout)
    if result.returncode != 0:
        print(f"  ERROR: {result.stderr.strip()[:300]}")
        return False
    out = result.stdout.strip()
    if out:
        print(f"  {out[:1500]}")
    return True

def step(n: int, name: str):
    print(f"\n{'='*60}")
    print(f"  [{n}/7] {name}")
    print(f"{'='*60}")

# Shorthand path helpers
P = lambda *parts: os.path.join(PIPELINE, *parts)


# ── pipeline steps ─────────────────────────────────────────────────────

def step_parse(so: str, url: str):
    set_state(site=so, step="parse", status="running",
              message="Downloading and parsing site...")
    step(1, "parse — extract content, colors, images, nav")
    raw_path = os.path.join(PIPE_OUT, so, "raw_homepage.html")
    os.makedirs(os.path.join(OUT, so), exist_ok=True)
    subprocess.run(f'{CURL} -sL "{url}" -o "{raw_path}"',
                   shell=True, cwd=BASE, timeout=30)
    run(f'python "{P("parse", "parse_site.py")}"', cwd=BASE)
    parsed = os.path.join(PIPE_OUT, "parsed_site.json")
    if os.path.exists(parsed):
        import shutil
        shutil.copy2(parsed, os.path.join(OUT, so, "parsed_site.json"))


def step_build_prompt(so: str, url: str):
    set_state(site=so, step="generate", status="running",
              message="Building prompt and generating HTML...")
    step(2, "generate — build prompt + generate HTML")
    run(f'python "{P("generate", "build_prompt.py")}" '
        f'--url "{url}" --generate', cwd=BASE, timeout=180)
    import shutil
    v2 = os.path.join(PIPE_OUT, "v2")
    dst = os.path.join(OUT, so)
    for f in ["final.html", "harmony_prompt.txt",
              "01_brief_data.json", "01_site_data.json"]:
        src = os.path.join(v2, f)
        if os.path.exists(src):
            shutil.copy2(src, os.path.join(dst, f))


def step_vision_qa(so: str, url: str = ""):
    set_state(site=so, step="vision_qa", status="running",
              message="Running vision QA...")
    step(3, "vision — compare original vs generated HTML")
    site_url = url or so
    run(f'node "{P("screenshot", "original.js")}" "{site_url}"',
        cwd=BASE, timeout=60)
    run(f'python "{P("vision", "advisor.py")}"', cwd=BASE)
    run(f'python "{P("vision", "evaluate.py")}"', cwd=BASE, timeout=120)
    v2 = os.path.join(PIPE_OUT, "v2")
    dst = os.path.join(OUT, so)
    import shutil
    for f in ["vision_corrections.json", "vision_prompt.json",
              "vision_prompt.txt", "vision_fix_report.json"]:
        src = os.path.join(v2, f)
        if os.path.exists(src):
            shutil.copy2(src, os.path.join(dst, f))


def step_apply_fixes(so: str):
    set_state(site=so, step="apply_fixes", status="running",
              message="Applying vision fixes...")
    step(4, "fix — image placement + color rhythm")
    run(f'python "{P("fix", "apply_fixes.py")}"', cwd=BASE, timeout=30)
    import shutil
    v2 = os.path.join(PIPE_OUT, "v2")
    dst = os.path.join(OUT, so)
    for f in ["final.html", "vision_fix_report.json"]:
        src = os.path.join(v2, f)
        if os.path.exists(src):
            shutil.copy2(src, os.path.join(dst, f))


def step_screenshot(so: str):
    set_state(site=so, step="screenshot", status="running",
              message="Taking screenshots via Playwright...")
    step(5, "screenshot — viewport + fullpage + mobile")
    final_html = os.path.join(OUT, so, "final.html")
    if os.path.exists(final_html):
        run(f'node "{P("screenshot", "redesign.js")}" {so}',
            cwd=BASE, timeout=60)
        import shutil
        src_dir = os.path.join(PIPE_OUT, so, "screenshots")
        dst_dir = os.path.join(OUT, so, "screenshots")
        if os.path.exists(src_dir):
            shutil.copytree(src_dir, dst_dir, dirs_exist_ok=True)
            print(f"  Screenshots copied to {dst_dir}/")
    else:
        print("  final.html not found, skipping screenshot")


def step_qa(so: str):
    set_state(site=so, step="qa", status="running",
              message="Running QA check...")
    step(6, "qa — 25+ criteria (layout, visual, content, code)")
    run(f'python "{P("qa", "quick.py")}"', cwd=BASE)
    run(f'python "{P("qa", "comprehensive.py")}"', cwd=BASE, timeout=60)
    import shutil
    v2 = os.path.join(PIPE_OUT, "v2")
    dst = os.path.join(OUT, so)
    for f in ["qa_report.json", "qa_report_v2.json"]:
        src = os.path.join(v2, f)
        if os.path.exists(src):
            shutil.copy2(src, os.path.join(dst, f))


def step_fix_loop(so: str, max_iter: int = 3):
    set_state(site=so, step="fix_loop", status="running",
              message="Running judge — evaluating QA report...")
    step(7, f"judge — fix loop (max {max_iter} iterations)")
    v2 = os.path.join(PIPE_OUT, "v2")
    dst = os.path.join(OUT, so)

    for i in range(1, max_iter + 1):
        qa_path = os.path.join(v2, "qa_report.json")
        if not os.path.exists(qa_path):
            print("  no QA report, skipping fix loop")
            break

        print(f"  Iteration {i}: running judge...")
        result = subprocess.run(
            f'python "{P("judge", "judge.py")}"',
            shell=True, capture_output=True, text=True,
            cwd=BASE, timeout=60
        )
        print(result.stdout[:2000] if result.stdout else result.stderr[:500])
        needs_fix = result.returncode != 0

        if not needs_fix:
            print("  \U0001f9d1\u200d\u2696\ufe0f Judge says: good enough!")
            break

        if not os.path.exists(os.path.join(v2, "judge_report.json")):
            print("  No judge report — running auto_fix as fallback")
            run(f'python "{P("fix", "auto_fix.py")}"', cwd=BASE, timeout=180)

        run(f'python "{P("fix", "apply_fixes.py")}"', cwd=BASE, timeout=30)
        run(f'node "{P("screenshot", "redesign.js")}" {so}',
            cwd=BASE, timeout=60)
        run(f'python "{P("qa", "quick.py")}"', cwd=BASE)
        run(f'python "{P("qa", "comprehensive.py")}"', cwd=BASE, timeout=60)

        import shutil
        for f in ["final.html", "qa_report.json",
                  f"qa_report_iter{i}.json", "judge_report.json"]:
            src = os.path.join(v2, f.replace(f"iter{i}", "").strip("."))
            if os.path.exists(src):
                shutil.copy2(src, os.path.join(dst, f))

        new_qa = os.path.join(v2, "qa_report.json")
        if os.path.exists(new_qa):
            new_score = json.load(open(new_qa, encoding="utf-8")).get("overall_score", 0)
            print(f"  New score after iteration {i}: {new_score}/10")

    import shutil
    for f in ["final.html", "qa_report.json",
              "fix_prompt.txt", "judge_report.json"]:
        src = os.path.join(v2, f)
        if os.path.exists(src):
            shutil.copy2(src, os.path.join(dst, f))
    run(f'python "{P("qa", "quick.py")}"', cwd=BASE)
    run(f'python "{P("qa", "comprehensive.py")}"', cwd=BASE, timeout=60)
    for f_n in ["final.html", "qa_report.json", f"qa_report_iter{i}.json"]:
        src = os.path.join(v2, f_n.replace(f"iter{i}", "").strip("."))
        if os.path.exists(src):
            shutil.copy2(src, os.path.join(dst, f_n))

    import shutil
    for f in ["final.html", "qa_report.json", "fix_prompt.txt"]:
        src = os.path.join(v2, f)
        if os.path.exists(src):
            shutil.copy2(src, os.path.join(dst, f))


# ── sub-agent instructions ─────────────────────────────────────────────

def print_subagent_instructions(so, url):
    print(f"""
{'='*60}
  SUB-AGENT PIPELINE for {so.upper()}
  URL: {url}
{'='*60}

Run in order:

--- 1: Parse ---
sessions_spawn {{
  task: "$(cat pipeline/agents/prompts/parse.md)" -replace '{{URL}}', '{url}',
  label: "parse-{so}"
}}

--- 2: Generate ---
sessions_spawn {{
  task: "$(cat pipeline/agents/prompts/generate.md)",
  label: "generate-{so}"
}}

--- 3: Vision QA ---
sessions_spawn {{
  task: "$(cat pipeline/agents/prompts/vision-qa.md)",
  label: "vision-{so}"
}}

--- 4: Screenshot ---
sessions_spawn {{
  task: "Take screenshot using node pipeline/screenshot/redesign.js",
  label: "screenshot-{so}"
}}

--- 5: QA ---
sessions_spawn {{
  task: "$(cat pipeline/agents/prompts/qa.md)",
  label: "qa-{so}"
}}

--- Copy results ---
python -c "import shutil,os; shutil.copytree('pipeline/outputs/v2',
  'pipeline/sites/{so}', dirs_exist_ok=True)"
""")


# ── main ───────────────────────────────────────────────────────────────

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Design pipeline orchestrator")
    parser.add_argument("url", nargs="?", help="Site URL to redesign")
    parser.add_argument("--full", action="store_true",
                        help="Full auto pipeline")
    parser.add_argument("--parse", action="store_true",
                        help="Parse only")
    parser.add_argument("--subagents", action="store_true",
                        help="Print sub-agent prompts instead of running")
    parser.add_argument("--model",
                        help="Override VLLM model (default: auto)")
    parser.add_argument("--vision-backend",
                        choices=["gateway", "rixtrema", "claude"],
                        help="Vision QA backend")
    args = parser.parse_args()

    url = args.url
    if not url:
        parser.print_help()
        return 1

    so = site_name(url)

    if args.subagents:
        print_subagent_instructions(so, url)
        return 0

    if args.model:
        os.environ["VLLM_MODEL"] = args.model
    if args.vision_backend:
        os.environ["VISION_BACKEND"] = args.vision_backend

    model = os.environ.get("VLLM_MODEL", "auto")
    vision = os.environ.get("VISION_BACKEND", "gateway")
    full_auto = args.full or not args.parse

    print(f"\n{'='*60}")
    print(f"  PIPELINE v3 — {so.upper()}")
    print(f"  URL:          {url}")
    print(f"  Model:        {model}")
    print(f"  Vision QA:    {vision}")
    print(f"  Output:       {os.path.join(OUT, so)}/")
    print(f"{'='*60}")

    t_start = time.time()

    if full_auto or not args.parse:
        step_parse(so, url)
        step_build_prompt(so, url)
        step_vision_qa(so, url)
        step_apply_fixes(so)
        step_screenshot(so)
        step_qa(so)
        step_fix_loop(so)

        elapsed = time.time() - t_start
        mins, secs = int(elapsed // 60), int(elapsed % 60)
        set_state(site=so, step="done", status="done",
                  message=f"Completed in {mins}m {secs}s",
                  model=model, vision_backend=vision)

        print(f"\n{'='*60}")
        print(f"  DONE — {so.upper()} in {mins}m {secs}s")
        print(f"  Artifacts: {os.path.join(OUT, so)}/")
        print(f"{'='*60}")

        report_path = os.path.join(OUT, so, "final_report.json")
        report = {
            "site": so, "url": url,
            "duration_seconds": elapsed,
            "output_dir": os.path.join(OUT, so),
            "status": "complete"
        }
        qa_path = os.path.join(OUT, so, "qa_report.json")
        if os.path.exists(qa_path):
            report["qa"] = json.load(open(qa_path, encoding="utf-8"))
        with open(report_path, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        print(f"  Report: {report_path}")

    elif args.parse:
        step_parse(so, url)
        print(f"\n  PARSED — {so}")
        print(f"  Parsed data: {os.path.join(OUT, so, 'parsed_site.json')}")

    return 0


if __name__ == "__main__":
    sys.exit(main())



