# Agent: Parse Site

## Task
Скачать и распарсить сайт, извлечь всю структуру.

## Input
URL: {URL}

## Steps
1. Скачать HTML: `curl.exe -sL "{URL}" -o pipeline/outputs/raw_homepage.html`
2. Запустить парсер: `python pipeline/parse/parse_site.py`
3. Результат будет в `pipeline/outputs/parsed_site.json`

## Success Criteria
- `pipeline/outputs/parsed_site.json` существует
- В файле есть: title, text_sections, images, colors_found, links
- Размер > 1000 байт

## Output
Ничего не выводить в чат. Просто выполнить шаги и завершиться.



