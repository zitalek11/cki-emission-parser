# Парсер эмиссионных документов ЦКИ

Извлечение параметров выпуска ценных бумаг из эмиссионной документации
для справочника ЦКИ. Источник истины — цитата в первичном документе.

**Нет доказательства → нет значения.**

Примеры в `data/examples` и Excel-разборы — эталонный набор, не спецификация
допустимых входов. Новый эмитент, новый тип документа, новая формулировка
номинала не должны требовать отдельного правила.

## Что уже есть (этапы 5–9)

- загрузка каталога НРД (`config/schema/nrd_catalog.xlsx`, ~2 000 полей);
- набор извлечения MVP (`config/schema/extract_set.yaml`, десятки полей);
- разбор PDF и DOCX с `source_id`, страницей, разделом, ячейкой таблицы, bbox;
- OCR-gate: страницы без текстового слоя помечаются, разбор не падает;
- классификация типа документа по формулировкам, не по имени эмитента;
- поиск кандидатов по синонимам поля и предпочтительному типу документа;
- извлечение LLM только из найденных фрагментов; `confirmed` ставит код после проверки цитаты;
- нормализация и валидация в коде: валюта, даты-правила, ИНН не из URL, CFI и краткое имя не выводятся, план ≠ факт;
- повторная проверка цитаты; сверка документов комплекта (`conflict` сохраняет обе цитаты);
- неизвестные параметры — `unmapped_fact`, без записи в «похожее» поле;
- отчёты: JSON (поля и очередь ревью, без фрагментов), Excel без ломания типов, HTML-ревью на русском;
- оценка на эталоне: `accepted` / `must-be-empty` / `known-bad`; метрика `unsupported_value_rate`, не доля заполненных полей;
- эталон комплектов (`config/eval/gold.yaml`) с цитатами из PDF/DOCX; класс инструмента по заголовку, не по отрицанию «не являются структурными».

## Запуск

```bash
cd cki-emission-parser
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

python -m cki_emission_parser --schema-stats
python -m cki_emission_parser path/to/pack --out reports/parse.json
python -m cki_emission_parser path/to/pack --dry-retrieve
python -m cki_emission_parser path/to/pack --extract --instrument bond_exchange
python -m cki_emission_parser path/to/pack --extract --out reports/extract.json
python -m cki_emission_parser path/to/pack --extract --out reports/extract.xlsx
python -m cki_emission_parser path/to/pack --extract --out reports/review.html
python -m cki_emission_parser --evaluate config/eval/gold.example.yaml --report reports/extract.json
python -m cki_emission_parser path/to/pack --evaluate config/eval/gold.yaml
python -m cki_emission_parser --llm-ping
python -m cki_emission_parser --serve
pytest
```

Эталон комплектов — `config/eval/gold.yaml`: цитаты из PDF/DOCX, не из Excel.
Поля с `requires_llm: true` не считаются промахом, пока модель не вызывалась.

JSON извлечения содержит поля, цитаты и `review_queue`, без фрагментов документа.
Полный retrieval — у `--dry-retrieve` или `--extract --with-retrieval`.
В Excel колонка «Значение (текст)» всегда текст: ИНН, CFI, номера регистрации
и даты-правила не превращаются в числа и даты Excel. Числовая колонка
только для integer/money. HTML-ревью на русском; латиница — id полей, CFI, статусы.

Внешние источники по умолчанию выключены. Для `--extract` в каталоге проекта
нужен файл `.env`:

```
CKI_LLM_API_KEY=...
CKI_LLM_BASE_URL=https://api-new.ai.moex.com/v1
CKI_LLM_MODEL=flagship
```

В `model` нужен **ID группы** шлюза: `flagship` (предпочтительно), иначе
`strong`, `qwen35-397b`, `Qwen3-Next`, `kimi`, `glm`, `balanced`, `fast`.
Имена вроде `gpt-oss` или `openai/gpt-4o-mini` шлюз не знает и отвечает 404.
URL — без хвоста `/chat/completions`. Проверка: `--llm-ping`. Без ключа
поля остаются `not_found`.

## Эталонные документы

Не коммитим PDF/DOCX комплектов. Импорт:

```bash
python scripts/import_benchmark.py "/путь/к/Артефакты для справочника выпусков.zip"
```

## Принципы

1. Схему не копировать в промпт целиком.
2. CFI, краткое имя, «для квалинвесторов = нет» — только из текста или
   из явного правила в коде со статусом `derived`.
3. Ошибку чинить в слое (разбор / поиск / извлечение / нормализация /
   валидация / схема), а не набором if-эмитент.
