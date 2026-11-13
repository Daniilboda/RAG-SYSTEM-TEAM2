# -*- coding: utf-8 -*-
"""Build K1 snapshot from rudn_corpus/rudn_doc.json (domain=stipendii).

Output: snapshot_k1/stipendii_lp_v1/
  pages/<uuid>.txt
  structure/<uuid>.json   — sections from spans (id_sec groups)
  manifest.jsonl
  snapshot_info.json
  reports/{sections,crawl_stats,boilerplate_report,duplicates,page_stats}

URL scheme: rudn-stipendii://v1/<quoted corpus doc_id>
K1 doc_id = uuid5(NAMESPACE_URL, url) — stable across rebuilds.
"""
from __future__ import annotations

import hashlib
import json
import shutil
import sys
from pathlib import Path
from urllib.parse import quote
from uuid import NAMESPACE_URL, uuid5

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "multidoc2dial" / "packages"))

from rag_common.text import normalized_hash  # noqa: E402

CORPUS_PATH = Path(__file__).parent / "rudn_doc.json"
DOMAIN = "stipendii"
SNAPSHOT_ID = "stipendii_lp_v1"
OUT = ROOT / "snapshot_k1" / SNAPSHOT_ID
ADAPTER_VERSION = "1"
# Fixed clock so rebuild same day is byte-stable for passport/manifest timestamps.
FETCHED_AT = "2026-10-30T00:00:00Z"
URL_PREFIX = "rudn-stipendii://v1"


def k1_url(source_doc_id: str) -> str:
    return f"{URL_PREFIX}/{quote(source_doc_id, safe='')}"


def k1_doc_id(source_doc_id: str) -> str:
    return str(uuid5(NAMESPACE_URL, k1_url(source_doc_id)))


def file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def sections_from_spans(doc_text: str, spans: dict) -> list[dict]:
    """Same idea as mdd structure.py: one section per id_sec."""
    if not spans:
        return [
            {
                "title_path": ["document"],
                "char_start": 0,
                "char_end": len(doc_text),
            }
        ]

    grouped: dict[str, list[dict]] = {}
    for span in spans.values():
        grouped.setdefault(span["id_sec"], []).append(span)

    sections: list[dict] = []
    for sec_spans in grouped.values():
        start = sec_spans[0]["start_sec"]
        end = sec_spans[0]["end_sec"]
        if any(s["start_sec"] != start or s["end_sec"] != end for s in sec_spans):
            raise ValueError(f"section {sec_spans[0]['id_sec']} has mixed bounds")
        if not 0 <= start <= end <= len(doc_text):
            raise ValueError(f"section {sec_spans[0]['id_sec']} out of range")

        fragment = doc_text[start:end]
        chosen = next(
            (s for s in sec_spans if s.get("title") and s["title"] in fragment),
            None,
        )
        if chosen is None:
            chosen = next((s for s in sec_spans if s.get("title")), sec_spans[0])

        title_path = [p["text"] for p in chosen.get("parent_titles") or []]
        if chosen.get("title"):
            title_path.append(chosen["title"])
        if not title_path:
            title_path = [chosen.get("id_sec") or "section"]

        sections.append(
            {"title_path": title_path, "char_start": start, "char_end": end}
        )

    sections.sort(key=lambda x: (x["char_start"], x["char_end"], x["title_path"]))
    return sections


def load_docs() -> list[dict]:
    corpus = json.loads(CORPUS_PATH.read_text(encoding="utf-8"))
    domain_docs = corpus["doc_data"][DOMAIN]
    docs = []
    for source_doc_id, doc in domain_docs.items():
        text = doc["doc_text"]
        if not text.endswith("\n"):
            text += "\n"
        docs.append(
            {
                "source_doc_id": source_doc_id,
                "title": doc.get("title") or source_doc_id,
                "doc_text": text,
                "spans": doc.get("spans") or {},
                "source_file": doc.get("source_file"),
                "content_hash_corpus": doc.get("content_hash"),
            }
        )
    return docs


def main() -> None:
    docs = load_docs()
    if OUT.exists():
        shutil.rmtree(OUT)
    pages_dir = OUT / "pages"
    structure_dir = OUT / "structure"
    reports_dir = OUT / "reports"
    pages_dir.mkdir(parents=True)
    structure_dir.mkdir(parents=True)
    reports_dir.mkdir(parents=True)

    rows: list[dict] = []
    page_stats: list[str] = []

    for doc in docs:
        source_id = doc["source_doc_id"]
        did = k1_doc_id(source_id)
        text = doc["doc_text"]
        (pages_dir / f"{did}.txt").write_bytes(text.encode("utf-8"))

        sections = sections_from_spans(text, doc["spans"])
        (structure_dir / f"{did}.json").write_bytes(
            (json.dumps(sections, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
        )

        row = {
            "schema_version": "k1.v1",
            "doc_id": did,
            "source": "rudn_corpus",
            "url": k1_url(source_id),
            "aliases": [],
            "source_doc_id": source_id,
            "title": doc["title"],
            "lang": "ru",
            "content_type": "text/plain",
            "path": f"pages/{did}.txt",
            "content_hash": normalized_hash(text),
            "section": DOMAIN,
            "fetched_at": FETCHED_AT,
            "last_modified": None,
            "corpus_source_file": doc.get("source_file"),
        }
        rows.append(row)
        page_stats.append(
            json.dumps(
                {
                    "doc_id": did,
                    "depth": 0,
                    "removed_blocks": 0,
                    "audience": None,
                },
                ensure_ascii=False,
            )
        )

    rows.sort(key=lambda r: r["doc_id"])
    (OUT / "manifest.jsonl").write_bytes(
        "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows).encode("utf-8")
    )

    info = {
        "schema_version": "k1.v1",
        "adapter_version": ADAPTER_VERSION,
        "snapshot_id": SNAPSHOT_ID,
        "source_corpus": str(CORPUS_PATH.relative_to(ROOT)).replace("\\", "/"),
        "source_corpus_sha256": file_sha256(CORPUS_PATH),
        "domain": DOMAIN,
        "document_count": len(rows),
        "created_at": FETCHED_AT,
    }
    (OUT / "snapshot_info.json").write_bytes(
        (json.dumps(info, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    )

    sections_report = {
        "sections": [
            {
                "section": DOMAIN,
                "document_count": len(rows),
                "description": "Стипендии и меры поддержки обучающихся РУДН",
            }
        ]
    }
    (reports_dir / "sections.json").write_bytes(
        (json.dumps(sections_report, ensure_ascii=False, indent=2) + "\n").encode(
            "utf-8"
        )
    )
    (reports_dir / "crawl_stats.json").write_bytes(
        (
            json.dumps(
                {
                    "found": 0,
                    "downloaded": 0,
                    "errors": 0,
                    "redirects": 0,
                    "duplicates": 0,
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n"
        ).encode("utf-8")
    )
    (reports_dir / "boilerplate_report.json").write_bytes(
        (json.dumps({"blocks": []}, ensure_ascii=False, indent=2) + "\n").encode(
            "utf-8"
        )
    )
    (reports_dir / "duplicates.json").write_bytes(
        (json.dumps({"groups": []}, ensure_ascii=False, indent=2) + "\n").encode(
            "utf-8"
        )
    )
    page_stats.sort()
    (reports_dir / "page_stats.jsonl").write_bytes(
        "".join(line + "\n" for line in page_stats).encode("utf-8")
    )

    # quick validation
    bad = 0
    for row in rows:
        txt = (OUT / row["path"]).read_text(encoding="utf-8")
        if normalized_hash(txt) != row["content_hash"]:
            bad += 1
        st = json.loads((structure_dir / f"{row['doc_id']}.json").read_text(encoding="utf-8"))
        for sec in st:
            if not 0 <= sec["char_start"] <= sec["char_end"] <= len(txt):
                bad += 1

    print(f"wrote {OUT}")
    print(f"documents={len(rows)} bad_checks={bad}")
    print(f"sample url={rows[0]['url']}")
    print(f"sample doc_id={rows[0]['doc_id']}")


if __name__ == "__main__":
    main()
