# ADR: источник Markdown для стипендийного корпуса РУДН

- **Статус:** принято
- **Дата:** 2026-10-29
- **Контекст:** TSK-PRE-EXP-01 / пайплайн `docs/rudn_stipendii_10_pipeline.xlsx` (этап A и далее)

## Решение

**Рабочий корпус Markdown для дальнейших этапов (spans / K1 / чанки / Qdrant):**

`llama_parse/llama_parse_md_clean/`

Это MD после LlamaParse + `llama_parse/postprocess_md.py` (снят шум СЭД/ЭП: barcode, e1cib, блоки подписи, `signature:` / `logo:`).

**Не использовать как основной источник:**

- `docs/docling_md/` — архив / сравнение; у Docling часто ломается шапка приказа (`""`, image-placeholder).
- `llama_parse/llama_parse_md/` — сырой вывод LlamaParse **до** чистки; в индекс не брать.

PDF-источник без изменений: `docs/docling_pdf/` (22 документа).

## Почему

Сравнение 22 парных файлов (clean LP vs Docling):

- после постпроцесса у LP шум СЭД/ЭП ≈ 0; у Docling служебные артефакты в шапках остаются чаще;
- у Docling в ~13/22 файлах в шапке пустой номер приказа; у clean LP шапка с номером обычно на месте;
- смысловое пересечение высокое (средний Jaccard ≈ 0.94); на длинных положениях тексты почти совпадают.

Docling остаётся запасным контуром и материалом для QA/сравнения, не «текущим» MD для индекса.

## Последствия

1. Clean MD — вход для корпуса `rudn_corpus/rudn_doc.json` (формат как multidoc2dial_doc: `doc_data[domain][doc_id]`).
2. Снимок K1: `snapshot_k1/stipendii_lp_v1/` — адаптером `rudn_corpus/build_k1_snapshot.py` из `rudn_doc.json` (не напрямую из папки md).
3. Повторная конвертация PDF → MD: LlamaParse → `postprocess_md.py` → `llama_parse_md_clean/`.
4. Опись файлов: `llama_parse/manifest.jsonl` (`build_manifest.py`).

## Ссылки

- Скрипт чистки: `llama_parse/postprocess_md.py`
- Манифест: `llama_parse/manifest.jsonl`
- Корпус: `rudn_corpus/rudn_doc.json`
- Адаптер K1: `rudn_corpus/build_k1_snapshot.py` → `snapshot_k1/stipendii_lp_v1/`
- Сырой LP: `llama_parse/llama_parse_md/`
- Docling MD (не основной): `docs/docling_md/`
- Трекер: `docs/rudn_stipendii_10_pipeline.xlsx`
