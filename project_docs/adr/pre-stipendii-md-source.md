# ADR: источник Markdown для стипендийного корпуса РУДН

- **Статус:** принято
- **Дата:** 2026-10-29 (пути обновлены 2026-11-13: этап A → `data_to_md/`)
- **Контекст:** TSK-PRE-EXP-01 / пайплайн `project_docs/rudn_stipendii_10_pipeline.xlsx` (этап A и далее)

## Решение

**MD после нормализации (постпроцесс LlamaParse):**

`data_to_md/llama_parse/llama_parse_md_clean/`

Это MD после LlamaParse + `data_to_md/llama_parse/postprocess_md.py` (снят шум СЭД/ЭП: barcode, e1cib, блоки подписи, `signature:` / `logo:`).

**Шлюз в корпус (после всех проверок):** `data_to_md/ready_to_corpus/` — сюда попадают только MD, готовые к этапу B. Корпус / spans / K1 / чанки / Qdrant дальше идут отсюда (через `rudn_corpus`).

**Не использовать как основной источник:**

- `data_to_md/docling/docling_md/` — архив / сравнение; у Docling часто ломается шапка приказа (`""`, image-placeholder).
- `data_to_md/llama_parse/llama_parse_md/` — сырой вывод LlamaParse **до** чистки; в индекс не брать.

PDF-источник сейчас: `data_to_md/llama_parse/llama_parse_pdf/` (22 документа). В перспективе сырые входы — в `data/`, а `data_to_md/` только нормализует в clean MD.

## Почему

Сравнение 22 парных файлов (clean LP vs Docling):

- после постпроцесса у LP шум СЭД/ЭП ≈ 0; у Docling служебные артефакты в шапках остаются чаще;
- у Docling в ~13/22 файлах в шапке пустой номер приказа; у clean LP шапка с номером обычно на месте;
- смысловое пересечение высокое (средний Jaccard ≈ 0.94); на длинных положениях тексты почти совпадают.

Docling остаётся запасным контуром и материалом для QA/сравнения, не «текущим» MD для индекса.

## Последствия

1. Clean MD — вход для корпуса `rudn_corpus/`: `docs/<domain>/<doc_id>.json` + `catalog.jsonl` (текст, meta, spans/tables). Оригиналы PDF: `data/raw_data/` → после MD в `ready_to_corpus` — `data/have_md/` (`monitoring/promote_raw_to_have_md.py`).
2. Снимок K1: `snapshot_k1/stipendii_lp_v1/` — `snapshot_k1/build_snapshot.py` из файлового корпуса (не напрямую из папки md).
3. Повторная конвертация PDF → MD: LlamaParse → `postprocess_md.py` → `llama_parse_md_clean/`.
4. Опись файлов: `data_to_md/llama_parse/manifest.jsonl` (`build_manifest.py`).

## Ссылки

- Скрипт чистки: `data_to_md/llama_parse/postprocess_md.py`
- Манифест: `data_to_md/llama_parse/manifest.jsonl`
- Шлюз в корпус: `data_to_md/ready_to_corpus/`
- Корпус: `rudn_corpus/docs/` + `rudn_corpus/catalog.jsonl`
- Сборка K1: `snapshot_k1/build_snapshot.py` → `snapshot_k1/stipendii_lp_v1/`
- Сырой LP: `data_to_md/llama_parse/llama_parse_md/`
- Docling MD (не основной): `data_to_md/docling/docling_md/`
- Трекер: `project_docs/rudn_stipendii_10_pipeline.xlsx`
