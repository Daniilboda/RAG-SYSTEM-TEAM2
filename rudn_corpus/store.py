# -*- coding: utf-8 -*-
"""File-based RUDN corpus: docs/<domain>/<doc_id>.json + catalog.jsonl."""
from __future__ import annotations

import json
import re
import unicodedata
from datetime import datetime, timezone
from pathlib import Path

CORPUS_DIR = Path(__file__).resolve().parent
DOCS_DIR = CORPUS_DIR / "docs"
CATALOG_PATH = CORPUS_DIR / "catalog.jsonl"

# Meta first so source is visible without scrolling past doc_text/spans.
DOC_KEY_ORDER = (
    "title",
    "doc_id",
    "domain",
    "doc_type",
    "number",
    "date",
    "source",
    "status",
    "effective_from",
    "relations",
    "content_hash",
    "updated_at",
    "doc_text",
    "spans",
    "tables",
)

_UNSAFE = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


def order_doc(doc: dict) -> dict:
    out: dict = {}
    for key in DOC_KEY_ORDER:
        if key in doc:
            out[key] = doc[key]
    for key, val in doc.items():
        if key not in out:
            out[key] = val
    return out


def nfc(s: str) -> str:
    return unicodedata.normalize("NFC", s)


def safe_filename(doc_id: str) -> str:
    """Windows-safe file stem; keep Unicode letters."""
    name = nfc(doc_id).strip().rstrip(".")
    name = _UNSAFE.sub("_", name)
    return name or "doc"


def doc_path(domain: str, doc_id: str) -> Path:
    return DOCS_DIR / nfc(domain) / f"{safe_filename(doc_id)}.json"


def catalog_entry(doc: dict, path: Path | None = None) -> dict:
    domain = nfc(doc.get("domain") or "unknown")
    doc_id = nfc(doc.get("doc_id") or "")
    rel = path or doc_path(domain, doc_id)
    try:
        rel_s = str(rel.relative_to(CORPUS_DIR)).replace("\\", "/")
    except ValueError:
        rel_s = str(rel).replace("\\", "/")
    return {
        "doc_id": doc_id,
        "domain": domain,
        "title": doc.get("title") or doc_id,
        "content_hash": doc.get("content_hash"),
        "path": rel_s,
        "doc_type": doc.get("doc_type"),
        "status": doc.get("status"),
        "updated_at": doc.get("updated_at")
        or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }


def write_doc(doc: dict, *, refresh_catalog: bool = True) -> Path:
    domain = nfc(doc["domain"])
    doc_id = nfc(doc["doc_id"])
    path = doc_path(domain, doc_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    doc = dict(doc)
    doc["doc_id"] = doc_id
    doc["domain"] = domain
    doc["updated_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    doc = order_doc(doc)
    path.write_text(
        json.dumps(doc, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    if refresh_catalog:
        rebuild_catalog()
    return path


def read_doc(domain: str, doc_id: str) -> dict:
    path = doc_path(domain, doc_id)
    return json.loads(path.read_text(encoding="utf-8"))


def iter_docs(domain: str | None = None) -> list[dict]:
    if not DOCS_DIR.is_dir():
        return []
    out: list[dict] = []
    domains = [DOCS_DIR / nfc(domain)] if domain else sorted(DOCS_DIR.iterdir())
    for ddir in domains:
        if not ddir.is_dir():
            continue
        for fp in sorted(ddir.glob("*.json")):
            out.append(json.loads(fp.read_text(encoding="utf-8")))
    return out


def load_domain_map(domain: str) -> dict[str, dict]:
    """doc_id -> doc, for scripts that used corpus['doc_data'][domain]."""
    return {nfc(d["doc_id"]): d for d in iter_docs(domain)}


def rebuild_catalog() -> Path:
    rows = [catalog_entry(doc) for doc in iter_docs()]
    rows.sort(key=lambda r: (r["domain"], r["doc_id"]))
    CATALOG_PATH.write_text(
        "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows),
        encoding="utf-8",
    )
    return CATALOG_PATH


def migrate_from_monolith(monolith: Path) -> tuple[int, Path]:
    """Split rudn_doc.json into docs/ + catalog.jsonl."""
    corpus = json.loads(monolith.read_text(encoding="utf-8"))
    n = 0
    for domain, docs in corpus.get("doc_data", {}).items():
        for doc_id, doc in docs.items():
            doc = dict(doc)
            doc.setdefault("doc_id", doc_id)
            doc.setdefault("domain", domain)
            write_doc(doc, refresh_catalog=False)
            n += 1
    rebuild_catalog()
    return n, CATALOG_PATH
