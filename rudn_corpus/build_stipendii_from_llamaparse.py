# -*- coding: utf-8 -*-
"""Upsert domain=stipendii into file-based rudn_corpus from ready_to_corpus MD.

Prefers data_to_md/ready_to_corpus/<stem>.md (postprocess + table merge).
Falls back to manifest md_path if a file is missing there.

Corpus layout:
  rudn_corpus/docs/<domain>/<doc_id>.json
  rudn_corpus/catalog.jsonl

On text change spans/tables are cleared — run fill_spans.py after.
Other domains are preserved (untouched files).
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
import unicodedata
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from store import load_domain_map, rebuild_catalog, write_doc  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
LP_MANIFEST = ROOT / "data_to_md" / "llama_parse" / "manifest.jsonl"
READY_DIR = ROOT / "data_to_md" / "ready_to_corpus"
DATA_DIR = ROOT / "data"
RAW_DIR = DATA_DIR / "raw_data"
HAVE_DIR = DATA_DIR / "have_md"
DOMAIN = "stipendii"


def content_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def resolve_md_path(pdf_name: str, manifest_md: str) -> Path:
    ready = READY_DIR / f"{Path(pdf_name).stem}.md"
    if ready.is_file():
        return ready
    # NFC-safe lookup in ready_to_corpus
    stem = nfc(Path(pdf_name).stem)
    for p in READY_DIR.glob("*.md"):
        if nfc(p.stem) == stem:
            return p
    return ROOT / manifest_md


def resolve_source(pdf_name: str, prev: dict) -> str | None:
    """Путь к оригиналу: сначала have_md, затем raw_data (одинаковый basename)."""
    for folder, base in (("have_md", HAVE_DIR), ("raw_data", RAW_DIR)):
        candidate = base / pdf_name
        if candidate.is_file():
            return f"data/{folder}/{pdf_name}".replace("\\", "/")
    # NFC-safe lookup (Windows / Unicode stems)
    stem = nfc(Path(pdf_name).stem)
    for folder, base in (("have_md", HAVE_DIR), ("raw_data", RAW_DIR)):
        if not base.is_dir():
            continue
        for p in base.iterdir():
            if p.is_file() and nfc(p.stem) == stem:
                return f"data/{folder}/{p.name}".replace("\\", "/")
    prev_src = prev.get("source")
    return prev_src if isinstance(prev_src, str) and prev_src.strip() else None


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


def main() -> None:
    rows = [
        json.loads(line)
        for line in LP_MANIFEST.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    domain_docs = load_domain_map(DOMAIN)
    written = 0

    for row in rows:
        pdf_name = row["document_old"]
        md_path = resolve_md_path(pdf_name, row["md_path"])
        text = md_path.read_text(encoding="utf-8")
        if not text.endswith("\n"):
            text += "\n"

        doc_id = nfc(Path(pdf_name).stem)
        title = row.get("title") or doc_id
        new_hash = content_hash(text)

        prev = domain_docs.get(doc_id, {})
        text_changed = prev.get("content_hash") != new_hash or prev.get("doc_text") != text
        if text_changed:
            spans: dict = {}
            tables: list = []
        else:
            spans = prev.get("spans") if isinstance(prev.get("spans"), dict) else {}
            tables = prev.get("tables") if isinstance(prev.get("tables"), list) else []
        relations = (
            prev.get("relations") if isinstance(prev.get("relations"), list) else []
        )
        status = prev.get("status") or "unknown"
        effective_from = prev.get("effective_from")
        number = prev.get("number") or guess_number(text, pdf_name)
        date = prev.get("date") or guess_date(text, pdf_name)
        doc_type = prev.get("doc_type") or guess_doc_type(title, pdf_name)
        source = resolve_source(pdf_name, prev)

        doc = {
            "title": title,
            "doc_id": doc_id,
            "domain": DOMAIN,
            "doc_type": doc_type,
            "number": number,
            "date": date,
            "source": source,
            "status": status,
            "effective_from": effective_from,
            "relations": relations,
            "content_hash": new_hash,
            "doc_text": text,
            "spans": spans,
            "tables": tables,
        }
        write_doc(doc, refresh_catalog=False)
        domain_docs[doc_id] = doc
        written += 1
        rel = str(md_path.relative_to(ROOT)).replace("\\", "/")
        print(f"{doc_id[:50]:50} <- {rel} changed={text_changed}")

    rebuild_catalog()
    print(f"wrote docs under rudn_corpus/docs/{DOMAIN}/")
    print(f"domain={DOMAIN} documents={written} catalog=rudn_corpus/catalog.jsonl")
    print(f"domains on disk: {sorted({d['domain'] for d in domain_docs.values()})}")


if __name__ == "__main__":
    main()
