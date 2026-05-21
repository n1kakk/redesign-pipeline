---
name: redesign-pipeline
description: Automated site redesign pipeline тАФ parse тЖТ generate тЖТ vision QA тЖТ fix тЖТ screenshot тЖТ QA тЖТ judge
---

# Redesign Pipeline Orchestrator

Automated 7-step pipeline for redesigning any website. 
Generates a modern HTML/CSS version while preserving all original content, images, colors, and links.

## Quick Start

```bash
cd /path/to/redesign-pipeline

# Single-command run (Python)
python run.py --full --vision-backend claude https://example.com

# Single-command run (Docker)
docker compose run --rm redesign --full https://example.com
```

Or spawn sub-agents for each step (see below).

## Pipeline Steps

| # | Step | Agent Prompt | Script | What Happens |
|---|------|-------------|--------|-------------|
| 1 | **parse** | `agents/prompts/parse.md` | `parse/parse_site.py` | Downloads site HTML, extracts content, colors, images, nav |
| 2 | **generate** | `agents/prompts/generate.md` | `generate/build_prompt.py` | Builds design prompt, generates HTML via RixTrema/DeepSeek |
| 3 | **vision** | `agents/prompts/vision-qa.md` | `vision/evaluate.py` | Compares original vs redesign screenshots via vision model |
| 4 | **fix** | тАФ | `fix/apply_fixes.py` | Applies color/image corrections from vision QA |
| 5 | **screenshot** | тАФ | `screenshot/redesign.js` | Playwright renders HTML тЖТ PNGs |
| 6 | **qa** | `agents/prompts/qa.md` | `qa/quick.py` + `qa/comprehensive.py` | 27 automated checks (content, colors, links, layout) |
| 7 | **judge** | `agents/prompts/judge.md` | `judge/judge.py` | Evaluates QA report, triggers fix loop if score < threshold |

## Orchestrating with Sub-Agents

Spawn sub-agents sequentially. Wait for each to finish before starting the next.

### Step 1: Parse
```json
{
  "task": "Read agents/prompts/parse.md and execute each step. URL: https://example.com",
  "label": "parse-example"
}
```

### Step 2: Generate
```json
{
  "task": "Read agents/prompts/generate.md and execute each step.",
  "label": "generate-example"
}
```

### Step 3: Vision QA
```json
{
  "task": "Read agents/prompts/vision-qa.md and execute each step.",
  "label": "vision-example"
}
```

### Step 4: Screenshot
```json
{
  "task": "Take screenshots: node screenshot/redesign.js example",
  "label": "screenshot-example"
}
```

### Step 5: QA
```json
{
  "task": "Read agents/prompts/qa.md and execute each step.",
  "label": "qa-example"
}
```

### Step 6: Judge & Fix Loop
```json
{
  "task": "Read agents/prompts/judge.md and execute. If fixes applied, re-run QA and check score.",
  "label": "judge-example"
}
```

## Fix Loop Logic

After initial QA, the judge decides:

1. Read `outputs/v2/qa_report.json`
2. **Critical issues** (fake content, broken images, bad links) тЖТ must fix, re-run QA
3. **>1 Major issue** (wrong colors, emoji, broken form) тЖТ fix, re-run QA
4. Otherwise тЖТ **done**, pipeline is complete

Max 3 fix iterations. If score doesn't improve or >= 9.0 тАФ stop.

## Environment Variables

| Variable | Required | Default | Purpose |
|----------|----------|---------|---------|
| `VLLM_KEY` | тЬЕ | тАФ | RixTrema/DeepSeek API key for HTML generation |
| `VLLM_BASE` | тЭМ | `https://rixtrema.net/api/vllm/v1` | vLLM endpoint |
| `VISION_BACKEND` | тЭМ | `gateway` | `gateway` / `claude` / `rixtrema` |
| `ANTHROPIC_API_KEY` | for Claude | тАФ | Claude API key |
| `GATEWAY_TOKEN` | for gateway | тАФ | OpenClaw Gateway token |

## Output

Results in `sites/{site_name}/`:
- `final.html` тАФ ╨│╨╛╤В╨╛╨▓╤Л╨╣ ╤А╨╡╨┤╨╕╨╖╨░╨╣╨╜
- `qa_report.json` тАФ QA-╨╛╤В╤З╤С╤В (score 0-1)
- `screenshots/` тАФ fullpage + viewport ╤Б╨║╤А╨╕╨╜╤И╨╛╤В╤Л

## Key Rules (Zero Rule)

- **╨Э╨Ш╨з╨Х╨У╨Ю ╨╜╨╡ ╨┐╤А╨╕╨┤╤Г╨╝╤Л╨▓╨░╨╡╨╝**. ╨Т╤Б╤С ╤Б ╨╛╤А╨╕╨│╨╕╨╜╨░╨╗╤М╨╜╨╛╨│╨╛ ╤Б╨░╨╣╤В╨░
- ╨Э╨╕╨║╨░╨║╨╛╨│╨╛ lorem ipsum
- ╨Э╨╕╨║╨░╨║╨╕╤Е ╤Н╨╝╨╛╨┤╨╖╨╕ ╨▓ HTML/CSS
- ╨Ъ╨░╨╢╨┤╨╛╨╡ ╨╕╨╖╨╛╨▒╤А╨░╨╢╨╡╨╜╨╕╨╡ тАФ ╤А╨╛╨▓╨╜╨╛ 1 ╤А╨░╨╖ (╨╗╨╛╨│╨╛ тАФ ╨╝╨░╨║╤Б 2)
- ╨в╨╛╨╗╤М╨║╨╛ ╤А╨╡╨░╨╗╤М╨╜╤Л╨╡ URL, ╤Ж╨▓╨╡╤В╨░, ╤В╨╡╨║╤Б╤В╤Л ╤Б ╤Б╨░╨╣╤В╨░

## File Structure

```
pipeline/
тФЬтФАтФА run.py                  # ╨Ю╤А╨║╨╡╤Б╤В╤А╨░╤В╨╛╤А (╨┐╤А╤П╨╝╨╛╨╣ ╨╖╨░╨┐╤Г╤Б╨║)
тФЬтФАтФА parse/                  # ╨и╨░╨│ 1: ╨┐╨░╤А╤Б╨╕╨╜╨│
тФЬтФАтФА generate/               # ╨и╨░╨│ 2: ╨│╨╡╨╜╨╡╤А╨░╤Ж╨╕╤П HTML
тФЬтФАтФА vision/                 # ╨и╨░╨│ 3: vision QA
тФЬтФАтФА fix/                    # ╨и╨░╨│ 4: ╤Д╨╕╨║╤Б╤Л
тФЬтФАтФА screenshot/             # ╨и╨░╨│ 5: Playwright ╤Б╨║╤А╨╕╨╜╤И╨╛╤В╤Л
тФЬтФАтФА qa/                     # ╨и╨░╨│ 6: QA ╨┐╤А╨╛╨▓╨╡╤А╨║╨╕
тФЬтФАтФА judge/                  # ╨и╨░╨│ 7: ╤Б╤Г╨┤╤М╤П
тФЬтФАтФА lib/                    # ╨Ю╨▒╤Й╨╕╨╡ ╨╝╨╛╨┤╤Г╨╗╨╕
тФЬтФАтФА agents/prompts/         # ╨и╨░╨▒╨╗╨╛╨╜╤Л ╨┤╨╗╤П sub-agents
тФЬтФАтФА config/.env.template    # ╨Я╨╡╤А╨╡╨╝╨╡╨╜╨╜╤Л╨╡ ╨╛╨║╤А╤Г╨╢╨╡╨╜╨╕╤П
тФЬтФАтФА Dockerfile              # Docker-╨╛╨▒╤А╨░╨╖
тФФтФАтФА docker-compose.yml       # Docker Compose
```

