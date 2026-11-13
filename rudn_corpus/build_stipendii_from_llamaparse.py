# -*- coding: utf-8 -*-
"""Upsert domain=stipendii into rudn_doc.json from llama_parse clean MD.

Corpus shape (like multidoc2dial_doc.json / rudn_doc_sketch.json):
  { "doc_data": { "<domain>": { "<doc_id>": { title, doc_text, spans, ... } } } }

Spans/tables start empty — fill later; doc_text is the clean markdown.
Other domains in rudn_doc.json are preserved.
"""
from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LP_MANIFEST = ROOT / "llama_parse" / "manifest.jsonl"
CORPUS_PATH = Path(__file__).parent / "rudn_doc.json"
DOMAIN = "stipendii"


def nfc(s: str) -> str:
    return unicodedata.normalize("NFC", s)


def guess_doc_type(title: str, filename: str) -> str:
    t = (title + " " + filename).lower()
    if "регламент" in t:
        return "регламент"
    if "график" in t:
        return "график"
    if "положение" in t or "polozhenie" in t:
        return "положение"
    if "приказ" in t or re.search(r"\bno\d|№\s*\d", t, re.I):
        return "приказ"
    return "документ"


def guess_number(text: str, filename: str) -> str | None:
    m = re.search(r"№\s*([\d\-–]+(?:\-[рp])?)", text[:800], re.I)
    if m:
        return m.group(1).replace("–", "-")
    m = re.search(r"No(\d+[^\s_]*)", filename, re.I)
    if m:
        return m.group(1)
    return None


def guess_date(text: str, filename: str) -> str | None:
    m = re.search(
        r"(\d{1,2})[.\-](\d{1,2})[.\-](\d{4})",
        text[:900],
    )
    if m:
        d, mo, y = m.groups()
        return f"{y}-{int(mo):02d}-{int(d):02d}"
    m = re.search(r"ot_(\d{2})\.(\d{2})\.(\d{4})", filename)
    if m:
        d, mo, y = m.groups()
        return f"{y}-{mo}-{d}"
    m = re.search(r"_(\d{2})_(\d{2})_(\d{4})_", filename)
    if m:
        d, mo, y = m.groups()
        return f"{y}-{mo}-{d}"
    return None


def load_corpus() -> dict:
    if CORPUS_PATH.exists():
        return json.loads(CORPUS_PATH.read_text(encoding="utf-8"))
    return {"doc_data": {}}


def main() -> None:
    rows = [
        json.loads(line)
        for line in LP_MANIFEST.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    corpus = load_corpus()
    doc_data = corpus.setdefault("doc_data", {})
    domain_docs = doc_data.setdefault(DOMAIN, {})

    for row in rows:
        md_path = ROOT / row["md_path"]
        text = md_path.read_text(encoding="utf-8")
        if not text.endswith("\n"):
            text += "\n"

        pdf_name = row["document_old"]
        doc_id = nfc(Path(pdf_name).stem)
        title = row.get("title") or doc_id

        # preserve manually enriched fields if doc already exists
        prev = domain_docs.get(doc_id, {})
        spans = prev.get("spans") if isinstance(prev.get("spans"), dict) else {}
        tables = prev.get("tables") if isinstance(prev.get("tables"), list) else []
        relations = prev.get("relations") if isinstance(prev.get("relations"), list) else []
        status = prev.get("status") or "unknown"
        effective_from = prev.get("effective_from")
        number = prev.get("number") or guess_number(text, pdf_name)
        date = prev.get("date") or guess_date(text, pdf_name)
        doc_type = prev.get("doc_type") or guess_doc_type(title, pdf_name)

        domain_docs[doc_id] = {
            "title": title,
            "doc_id": doc_id,
            "domain": DOMAIN,
            "doc_type": doc_type,
            "number": number,
            "date": date,
            "source_file": pdf_name,
            "source_md": row["md_path"],
            "status": status,
            "effective_from": effective_from,
            "relations": relations,
            "content_hash": row.get("content_hash"),
            "doc_text": text,
            "spans": spans,
            "tables": tables,
        }

    # stable key order within domain: by manifest order
    ordered = {}
    for row in rows:
        doc_id = nfc(Path(row["document_old"]).stem)
        ordered[doc_id] = domain_docs[doc_id]
    # keep any extra stipendii docs not in this manifest rebuild
    for doc_id, doc in domain_docs.items():
        if doc_id not in ordered:
            ordered[doc_id] = doc
    doc_data[DOMAIN] = ordered

    CORPUS_PATH.write_text(
        json.dumps(corpus, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    n = len(ordered)
    print(f"wrote {CORPUS_PATH}")
    print(f"domain={DOMAIN} documents={n}")
    print(f"domains in corpus: {sorted(doc_data)}")


if __name__ == "__main__":
    main()
