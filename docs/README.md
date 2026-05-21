# Pipeline Plan — Automated Site Redesign

## Два режима

### Режим 1: Прямой (subprocess) — Python запускает скрипты сам
```bash
python pipeline/run.py --full https://example.com
```
Всё последовательно в одном процессе. Проще, быстрее для одного сайта.

### Режим 2: Sub-agent — каждый шаг как OpenClaw агент
```bash
python pipeline/run.py --subagents https://example.com
```
Печатает промпты для `sessions_spawn`. Каждый шаг — отдельный sub-agent.

```
sessions_spawn { task: "cat pipeline/agents/agent-parse.md", label: "parse-site" }
    ↓ ждём
sessions_spawn { task: "cat pipeline/agents/agent-generate.md", label: "generate-site" }
    ↓ ждём
sessions_spawn { task: "cat pipeline/agents/agent-vision-qa.md", label: "vision-site" }
    ↓ ждём
...
```

**Когда использовать sub-agent режим:**
- Хочешь запустить 3 сайта параллельно
- Хочешь видеть прогресс по каждому шагу отдельно
- Хочешь разные модели для разных шагов
- Хочешь восстановиться после падения одного шага

## Запуск одной командой

```bash
# Прямой режим
python pipeline/run.py --full https://example.com

# Sub-agent режим
python pipeline/run.py --subagents https://example.com

# Только парсинг
python pipeline/run.py --parse https://example.com

# Выбор модели генерации
python pipeline/run.py --model deepseek-chat https://example.com
python pipeline/run.py --model gpt-4o-mini https://example.com

# Выбор бэкенда для vision QA
python pipeline/run.py --vision-backend rixtrema https://example.com
python pipeline/run.py --vision-backend gateway https://example.com
python pipeline/run.py --vision-backend claude https://example.com

# Старый флаг (для совместимости)
python pipeline/run_v2.py https://example.com
```

Результаты: `pipeline/sites/{domain}/`

---

## Архитектура

```mermaid
parse_site.py ──→ parsed_site.json ──→ build_prompt.py ──→ RixTrema ──→ HTML
                                                                          ↓
GPT-4o vision ◄── original screenshots                   final.html ←───┘
    ↓                                                            ↑
vision_advisor.py → vision_corrections.json → apply_vision_fixes.py
    ↓
screenshot.js → fullpage.png, viewport.png
    ↓
_qa_check.py → qa_report.json
    ↓
[loop while score < 9.0] auto_fix.py → re-screenshot → re-qa
```

### Модели

**Настройка через флаги `run.py` или переменные окружения.**

| Флаг / Env | Что меняет | По умолчанию |
|-----------|-----------|-------------|
| `--model` / `VLLM_MODEL` | Модель для генерации HTML | auto (первая из /v1/models) |
| `VLLM_BASE` | API endpoint | `https://rixtrema.net/api/vllm/v1` |
| `VLLM_KEY` | API ключ | хардкод (RixTrema) |
| `--vision-backend` / `VISION_BACKEND` | Бэкенд vision QA | `gateway` |
| `GATEWAY_URL` | Gateway URL (для vision) | `http://127.0.0.1:18789` |
| `GATEWAY_TOKEN` | Gateway токен | хардкод |
| `VISION_MODEL` | Модель vision (RixTrema) | `gpt-4o` |

**Примеры переключения:**

| Хочу | Команда |
|------|---------|
| DeepSeek для генерации | `--model deepseek-chat` |
| GPT-4o mini для генерации | `--model gpt-4o-mini` + `VLLM_BASE=https://api.openai.com/v1` + `VLLM_KEY=sk-...` |
| Vision через RixTrema | `--vision-backend rixtrema` |
| Всё через DeepSeek | `$env:VLLM_BASE='https://api.deepseek.com'; $env:VLLM_KEY='sk-...'` + `--vision-backend rixtrema` |

---

## Этапы (7 шагов)

| # | Этап | Инструмент | ~Время |
|---|------|-----------|--------|
| 1 | **Парсинг** | `parse_site.py` + `curl` | 2-3 мин |
| 2 | **Бриф + генерация** | `build_prompt.py` → `vllm_client.py` (RixTrema) | 3-7 мин |
| 3 | **Vision QA** | `vision_advisor.py` → GPT-4o | 1-2 мин |
| 4 | **Применить фиксы** | `apply_vision_fixes.py` | ~1 мин |
| 5 | **Скриншот** | `screenshot.js` (Playwright) | ~1 мин |
| 6 | **QA** | `_qa_check.py` + `qa_comprehensive.py` | ~1 мин |
| 7 | **Фикс-луп** | `auto_fix.py` (до score ≥ 9.0) | 3-5 мин/итерация |

**Один сайт:** ~15-30 мин · **10 сайтов:** ~3-5 часов

---

## Ключевые файлы

### `pipeline/` — ядро пайплайна

| Файл | Назначение |
|------|-----------|
| `run.py` | 🟢 **Оркестратор** — единственная точка входа |
| `parse_site.py` | 🟢 HTMLParser — извлекает текст, ссылки, изображения, цвета, мета-теги |
| `build_prompt.py` | 🟢 Универсальный билдер — анализ цветов, фильтр трекеров, дизайн-бриф |
| `vllm_client.py` | 🟢 Клиент RixTrema API (OpenAI-совместимый) |
| `vision_advisor.py` | 🟢 Формирует промпт для GPT-4o vision |
| `apply_vision_fixes.py` | 🟢 Применяет коррекции (перемещение изображений, цветовой ритм) |
| `screenshot.js` | 🟢 Playwright — viewport + fullpage скриншоты |
| `_qa_check.py` | 🟢 Быстрый QA (эмодзи, дубликаты, секции, ссылки) |
| `qa_comprehensive.py` | 🟢 Детальный QA (25+ критериев по категориям) |
| `auto_fix.py` | 🟢 Авто-фикс по QA-отчёту |
| `image_mapper.py` | 🟢 Маппинг изображений между оригиналом и генерацией |
| `parse_brand.py` | 🟢 Отдельный инструмент для глубокого анализа бренда |

### `pipeline/agents/` — агенты и шаблоны для sub-agent режима

| Файл | Назначение |
|------|-----------|
| `01_parse.py` | 🐍 Python-агент: парсинг сайта |
| `02_generate.py` | 🐍 Python-агент: генерация HTML |
| `03_vision_qa.py` | 🐍 Python-агент: vision QA |
| `07_judge/judge.py` | 🧑‍⚖️ **Судья** — читает QA, решает фикс-итерацию |
| `agent-parse.md` | 📝 Промпт-шаблон для OpenClaw sub-agent (parse) |
| `agent-generate.md` | 📝 Промпт-шаблон для OpenClaw sub-agent (generate) |
| `agent-vision-qa.md` | 📝 Промпт-шаблон для OpenClaw sub-agent (vision) |
| `agent-qa.md` | 📝 Промпт-шаблон для OpenClaw sub-agent (QA) |
| `agent-judge.md` | 📝 Промпт-шаблон для OpenClaw sub-agent (judge) |

Использование: `python pipeline/run.py --subagents https://...` — печатает готовые промпты.

### `pipeline/legacy/` — одноразовые скрипты для конкретных сайтов

~120 файлов, использовались при разработке для конкретных сайтов (DeRose, GMS, Russcap, Transcend и др.). Сохранены на случай, если понадобится подсмотреть решение. Не относятся к основному пайплайну.

### `pipeline/sites/` — сгенерированные сайты

Каждый сайт в своей папке:

```
sites/
├── oxfordharriman/
│   ├── final.html              # Финальный HTML
│   ├── parsed_site.json        # Результат парсинга
│   ├── qa_report.json          # QA-отчёт
│   ├── final_report.json       # Сводный отчёт
│   ├── vision_corrections.json # Коррекции от vision-агента
│   ├── raw_homepage.html       # Исходный HTML
│   ├── screenshots/            # Скриншоты
│   │   ├── fullpage.png
│   │   └── viewport.png
│   └── ... (fix_prompt.txt, vision_fix_report.json, и т.д.)
├── derose/
├── gms/
├── russcap/
└── ...
```

### `pipeline/outputs/` — временные файлы пайплайна

**НЕ класть сюда сайты.** Это working directory:
- `outputs/v2/` — constraints.json, промпты, промежуточные HTML, QA-отчёты (перезаписываются)
- `outputs/original_ref/` — скриншоты оригиналов для vision-QA

### `pipeline/sites/` — список всех нагенерированных сайтов

```
sites/
├── derose/          
├── gms/             
├── russcap/         
├── transcend/       
├── iter_001-006/    # Обучающие итерации
├── akrecapital/     
├── aksia/           
├── alerus/          
├── cac/             
├── deepseek/        
├── finspire/        
├── gygi/            
└── derose-redesign/ # отдельный проект DeRose (4 версии)
```

Новые сайты автоматически сохраняются в `pipeline/sites/{domain}/`.

---

## Constraints (из 5+ итераций) — `pipeline/outputs/v2/constraints.json`

### 🚫 НИЧЕГО НЕ ПРИДУМЫВАЕМ (zero_rule)

Это **абсолютный приоритет** над любыми дизайн-пожеланиями. Модели ЗАПРЕЩЕНО:
- Генерировать свои URL изображений
- Выдумывать цвета, которых нет в парсинге
- Писать свой контент/тексты
- Заменять отсутствующие элементы

Всё — ТОЛЬКО с оригинального сайта, из `parsed_site.json`. Если чего-то нет в парсинге — этого нет в HTML.

### Остальные критические правила:

1. **NO emoji** в HTML/CSS — ни юникод-символов, ни HTML-entities эмодзи
2. **Единая ширина секций** — 1280px (`--content-max`)
3. **Mobile nav: absolute** — не fixed (backdrop-filter ломает fixed контекст)
4. **transition: конкретные свойства** — не `all` (вызывает jank)
5. **Hover без дёрганья** — `border: transparent` в базисе, меняется только `border-color`
6. **Каждое изображение — ровно 1 раз** (кроме лого: макс 2)
7. **Никакого lorem ipsum** — только реальный контент с сайта
8. **Аккордеон: close-others** — при открытии одного, остальные закрываются
9. **Mobile: scroll lock** при открытом меню
10. **2-колоночный grid** для услуг, не 3-4
11. **Desktop подменю: CSS-only** (hover, без JS)
12. **Все URL изображений — абсолютные** (`https://...`)
13. **Никаких спецсимволов вне ASCII** — дефисы вместо em dash, (R) вместо ®

Полный список: `pipeline/outputs/v2/constraints.json` (16 основных + 7 checks harmony audit)

---

## Виджеты

Удалены. Если понадобятся для демо — смотреть `pipeline/outputs/v2/final.html` (уже встроены в последнюю генерацию Oxford Harriman).

---

## Nexus — UI дашборд

Отдельный Next.js проект в `nexus/`. Пока не подключён к пайплайну.

---

## Оценка на 10 сайтов

| Сценарий | На сайт | Всего |
|----------|---------|-------|
| Оптимистичный | ~15 мин | ~2.5 ч |
| Средний | ~25 мин | ~4 ч |
| Пессимистичный | ~45 мин | ~7.5 ч |

**Токены (среднее, 3 итерации):**
- Вход: ~100-150K · Выход: ~40-60K
- На 10 сайтов: ~1-1.5M входных / ~0.4-0.6M выходных

---

## Как добавить новый сайт

```bash
# 1. Полный прогон
python pipeline/run.py --full https://newsite.com

# 2. Посмотреть результат
open pipeline/sites/newsite/final.html

# 3. Проверить QA
cat pipeline/sites/newsite/qa_report.json | python -m json.tool
```

---

## История рефакторинга

- **2026-05-20**: v3 — единый `run.py` оркестратор, ~120 legacy-скриптов вынесены в `legacy/`, `PLAN.md` переписан
- **2026-05-13**: v2 — добавлен vision QA (GPT-4o), constraints.json, harmony audit
- **2026-05-11**: v1 — базовый пайплайн (парсинг → бриф → генерация → фиксы → скриншот → QA)


