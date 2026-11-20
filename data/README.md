# data/ — исходные документы

Оригиналы (PDF, HTML и т.п.) лежат не плоско, а в двух корзинах:

| Папка | Назначение |
| --- | --- |
| `raw_data/` | Новые файлы, MD ещё нет |
| `have_md/` | Оригинал уже имеет MD в `data_to_md/ready_to_corpus/` |

Поток: кладёте файл в `raw_data/` → после появления `<stem>.md` в `ready_to_corpus` скрипт `monitoring/promote_raw_to_have_md.py` (или постпроцесс) переносит оригинал в `have_md/`.

В корпусе поле `source` указывает на актуальный путь, например:

```json
"source": "data/have_md/1356_about_support_measures.pdf"
```
