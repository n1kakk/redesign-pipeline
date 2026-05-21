# Agent: Vision QA

## Task
Сравнить оригинальные скриншоты сайта с сгенерированным HTML через vision-модель.

## Prerequisites
- `pipeline/outputs/v2/final.html` существует
- `pipeline/outputs/parsed_site.json` существует

## Steps
1. Сделать скриншот оригинала: `node pipeline/screenshot/original.js`
2. Собрать vision-промпт: `python pipeline/vision/advisor.py`
3. Запустить vision QA:
   - По умолчанию: `python pipeline/vision/evaluate.py` (GPT-4o через Gateway)
   - Или RixTrema: `python pipeline/vision/evaluate.py --backend rixtrema`
4. Применить коррекции: `python pipeline/fix/apply_fixes.py`

## Guidelines
- Сравниваем оригинал (screenshot) и генерацию (final.html)
- Проверяем: правильные ли изображения в секциях, нет ли дубликатов
- Проверяем: правильное ли чередование тёмных/светлых фонов

## Success Criteria
- `pipeline/outputs/v2/vision_corrections.json` существует
- `pipeline/outputs/v2/final.html` обновлён с фиксами

## Output
Ничего.


