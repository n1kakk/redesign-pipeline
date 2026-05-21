# Agent: QA Check

## Task
Проверить сгенерированный HTML по критериям качества.

## Prerequisites
- `pipeline/outputs/v2/final.html` существует

## Steps
1. Быстрая проверка: `python pipeline/qa/quick.py`
2. Полная проверка: `python pipeline/qa/comprehensive.py`
3. Результаты в `pipeline/outputs/v2/qa_report.json`

## What We Check
- Layout: section_width_consistency, section_rhythm, layout_balance
- Visual: no_emoji, color_spec, hero_quality, real_images
- Interaction: animations, hover_no_jank, mobile_nav, desktop_nav
- Content: no_repeating_images, no_placeholder, links_correct
- Code: responsive, dead_code, services_section

## Threshold
- Score >= 9.0/10 → PASS
- Score < 9.0 → нужна итерация фикса

## Output
Ничего. Просто выполнить проверки.



