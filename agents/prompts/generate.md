# Agent: Generate Design

## Task
Создать дизайн-промпт из распарсенных данных и сгенерировать HTML.

## Prerequisites
- `pipeline/outputs/parsed_site.json` существует (результат агента parse)

## Steps
1. Запустить билдер промпта с генерацией:
   `python pipeline/generate/build_prompt.py --generate`
2. Результаты в `pipeline/outputs/v2/final.html`
3. Если используется `--model`, установить `$env:VLLM_MODEL` перед запуском

## Constraints
- ZERO RULE: ничего не придумываем, всё с оригинального сайта
- No emoji, no lorem ipsum, все изображения 1 раз
- См. pipeline/outputs/v2/constraints.json

## Success Criteria
- `pipeline/outputs/v2/final.html` существует
- Размер > 5000 байт
- Содержит <html> и <style>

## Output
Тишина. Просто сохранить HTML и завершиться.



