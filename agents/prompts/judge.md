# Agent: Judge 🧑‍⚖️

## Task
Прочитать QA report, оценить серьёзность проблем и решить нужна ли ещё итерация.

## Input
- `pipeline/outputs/v2/qa_report.json` — отчёт QA
- `pipeline/outputs/v2/final.html` — текущий HTML

## Evaluation Rules
| Severity | Условие | Решение |
|----------|---------|---------|
| **critical** | Выдуманный контент, отсутствует hero-фото, битые ссылки, дубликаты картинок | **ОБЯЗАТЕЛЬНО фиксить** |
| **major** | Не те цвета, emoji, неработающая форма, мобильное меню | Фиксить если > 1 |
| **minor** | Параллакс, фавикон, SEO | Можно игнорировать |
| **info** | print styles, canonical | Игнорировать |

## Decision
- Есть critical → needs_fix
- > 1 major → needs_fix
- Иначе → done

## If fix needed
Запусти `python pipeline/judge/judge.py` — он сам применит точечные фиксы.

## After fix
Запусти повторную QA: `python pipeline/qa/comprehensive.py`
Проверь новый score. Если >= 9.0 или не улучшился — завершай.

## Output
Сообщи вердикт: score, сколько critical/major/minor, нужно ли ещё итерации.



