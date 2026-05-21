---
name: redesign-pipeline
description: Automated site redesign pipeline — parse → generate → vision QA → fix → screenshot → QA → judge
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
| 4 | **fix** | — | `fix/apply_fixes.py` | Applies color/image corrections from vision QA |
| 5 | **screenshot** | — | `screenshot/redesign.js` | Playwright renders HTML → PNGs |
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
2. **Critical issues** (fake content, broken images, bad links) → must fix, re-run QA
3. **>1 Major issue** (wrong colors, emoji, broken form) → fix, re-run QA
4. Otherwise → **done**, pipeline is complete

Max 3 fix iterations. If score doesn't improve or >= 9.0 — stop.

## Environment Variables

| Variable | Required | Default | Purpose |
|----------|----------|---------|---------|
| `VLLM_KEY` | ✅ | — | RixTrema/DeepSeek API key for HTML generation |
| `VLLM_BASE` | ❌ | `https://rixtrema.net/api/vllm/v1` | vLLM endpoint |
| `VISION_BACKEND` | ❌ | `gateway` | `gateway` / `claude` / `rixtrema` |
| `ANTHROPIC_API_KEY` | for Claude | — | Claude API key |
| `GATEWAY_TOKEN` | for gateway | — | OpenClaw Gateway token |

## Output

Results in `sites/{site_name}/`:
- `final.html` — готовый редизайн
- `qa_report.json` — QA-отчёт (score 0-1)
- `screenshots/` — fullpage + viewport скриншоты

## Key Rules (Zero Rule)

- **НИЧЕГО не придумываем**. Всё с оригинального сайта
- Никакого lorem ipsum
- Никаких эмодзи в HTML/CSS
- Каждое изображение — ровно 1 раз (лого — макс 2)
- Только реальные URL, цвета, тексты с сайта

## File Structure

```
pipeline/
├── run.py                  # Оркестратор (прямой запуск)
├── parse/                  # Шаг 1: парсинг
├── generate/               # Шаг 2: генерация HTML
├── vision/                 # Шаг 3: vision QA
├── fix/                    # Шаг 4: фиксы
├── screenshot/             # Шаг 5: Playwright скриншоты
├── qa/                     # Шаг 6: QA проверки
├── judge/                  # Шаг 7: судья
├── lib/                    # Общие модули
├── agents/prompts/         # Шаблоны для sub-agents
├── config/.env.template    # Переменные окружения
├── Dockerfile              # Docker-образ
└── docker-compose.yml       # Docker Compose
```
