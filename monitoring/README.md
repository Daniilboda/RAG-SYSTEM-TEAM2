# monitoring — контроль потока оригиналов

Следит за связкой:

- `data/raw_data/` — новые исходники (PDF и т.п.), ещё без MD
- `data_to_md/ready_to_corpus/` — готовый MD после постпроцесса
- `data/have_md/` — оригиналы, для которых MD уже есть

## Скрипт

```bash
py -3.14 -X utf8 monitoring/promote_raw_to_have_md.py
py -3.14 -X utf8 monitoring/promote_raw_to_have_md.py --dry-run
```

Переносит файл из `raw_data` в `have_md`, если рядом (по stem) появился `.md` в `ready_to_corpus`.

Тот же шаг вызывается из `data_to_md/llama_parse/postprocess_md.py`, когда `--outdir` указывает на `ready_to_corpus`.
