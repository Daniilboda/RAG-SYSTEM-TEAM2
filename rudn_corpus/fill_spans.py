# -*- coding: utf-8 -*-
"""Fill spans (+ tables) in file-based rudn_corpus from doc_text markdown.

Span shape matches multidoc2dial/docs/rudn_doc_sketch.json:
  id_sp, tag, start_sp, end_sp, text_sp, title, parent_titles,
  id_sec, start_sec, end_sec, text_sec

Strategy:
  1) ATX headings (#..######) → section tree; heading line = hN span
  2) Numbered clauses inside a section → clause spans
  3) Bullet lines under a clause → list_item spans
  4) If <2 headings — treat whole doc as one section and clause-split
  5) HTML / GFM tables → tables[] with char offsets
"""
from __future__ import annotations

import sys
from pathlib import Path

import re

sys.path.insert(0, str(Path(__file__).resolve().parent))
from store import iter_docs, rebuild_catalog, write_doc  # noqa: E402

DOMAIN = "stipendii"

HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$", re.M)
# indent = spaces/tabs only (not \s — otherwise blank lines get swallowed into the match)
CLAUSE_RE = re.compile(
    r"(?m)^(?P<indent>[ \t]*)(?P<num>\d+(?:\.\d+){0,4})\.\s+\S"
)
LIST_RE = re.compile(r"(?m)^(?P<indent>[ \t]*)([*\-•]|\d+[\)])\s+\S")
HTML_TABLE_RE = re.compile(r"(?is)<table\b.*?</table>")
GFM_TABLE_START_RE = re.compile(r"(?m)^\|.+\|\s*$")
MD_BOLD_RE = re.compile(r"\*\*(.+?)\*\*")


def strip_md_title(raw: str) -> str:
    t = raw.strip()
    t = MD_BOLD_RE.sub(r"\1", t)
    t = re.sub(r"^#+\s*", "", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t[:160]


def _line_end(text: str, pos: int) -> int:
    nl = text.find("\n", pos)
    return len(text) if nl < 0 else nl + 1


def find_headings(text: str) -> list[dict]:
    heads: list[dict] = []
    for m in HEADING_RE.finditer(text):
        level = len(m.group(1))
        title = strip_md_title(m.group(2))
        start = m.start()
        end = _line_end(text, m.end())
        heads.append(
            {
                "level": level,
                "title": title or f"h{level}",
                "start": start,
                "head_end": end,
            }
        )
    # body_end = next heading of same or higher level (full section)
    # content_end = next heading of any level (direct content only — avoids dup clauses)
    for i, h in enumerate(heads):
        body_end = len(text)
        content_end = len(text)
        for j in range(i + 1, len(heads)):
            if j == i + 1:
                content_end = heads[j]["start"]
            if heads[j]["level"] <= h["level"]:
                body_end = heads[j]["start"]
                break
        if i + 1 < len(heads):
            content_end = heads[i + 1]["start"]
        else:
            content_end = len(text)
        # section may end before next sibling of parent — content never past body_end
        h["body_end"] = body_end
        h["content_end"] = min(content_end, body_end)
        h["sec_id"] = f"h{h['level']}-{i + 1}"
    return heads


def find_clauses_in_range(text: str, start: int, end: int) -> list[tuple[int, int, str]]:
    """Return (clause_start, clause_end, num) for top-ish numbered lines in [start,end)."""
    chunk = text[start:end]
    hits: list[tuple[int, int, str, int]] = []  # abs_start, abs_line_end, num, indent
    for m in CLAUSE_RE.finditer(chunk):
        abs_s = start + m.start()
        abs_line_end = _line_end(text, abs_s)
        indent = len(m.group("indent").replace("\t", "    "))
        hits.append((abs_s, abs_line_end, m.group("num"), indent))

    if not hits:
        return []

    # keep shallowest indent level among hits (top clauses in this section)
    min_indent = min(h[3] for h in hits)
    top = [h for h in hits if h[3] == min_indent]
    # extend each clause to next top clause / section end
    out: list[tuple[int, int, str]] = []
    for i, (s, _le, num, _ind) in enumerate(top):
        c_end = top[i + 1][0] if i + 1 < len(top) else end
        out.append((s, c_end, num))
    return out


def find_list_items_in_range(text: str, start: int, end: int) -> list[tuple[int, int]]:
    chunk = text[start:end]
    starts: list[int] = []
    for m in LIST_RE.finditer(chunk):
        # skip numbered clauses already covered by CLAUSE_RE style "1. "
        line = chunk[m.start() : chunk.find("\n", m.start())]
        if re.match(r"\s*\d+\.\s+\S", line):
            continue
        starts.append(start + m.start())
    if not starts:
        return []
    out: list[tuple[int, int]] = []
    for i, s in enumerate(starts):
        e = starts[i + 1] if i + 1 < len(starts) else end
        # trim trailing blank lines inside item end — keep exact slice to next item
        out.append((s, e))
    return out


def parent_chain(stack: list[dict], level: int) -> list[dict]:
    """Parents are open headings with level < current."""
    parents = [h for h in stack if h["level"] < level]
    return [
        {"id_sp": p["id_sp"], "text": p["title"], "level": f"h{p['level']}"}
        for p in parents
    ]


def make_span(
    id_sp: str,
    tag: str,
    text: str,
    start: int,
    end: int,
    title: str,
    parent_titles: list[dict],
    id_sec: str,
    sec_start: int,
    sec_end: int,
) -> dict:
    assert 0 <= start <= end <= len(text), (id_sp, start, end, len(text))
    text_sp = text[start:end]
    text_sec = text[sec_start:sec_end]
    return {
        "id_sp": id_sp,
        "tag": tag,
        "start_sp": start,
        "end_sp": end,
        "text_sp": text_sp,
        "title": title,
        "parent_titles": parent_titles,
        "id_sec": id_sec,
        "start_sec": sec_start,
        "end_sec": sec_end,
        "text_sec": text_sec,
    }


def build_spans(text: str) -> dict[str, dict]:
    if not text.endswith("\n"):
        text = text + "\n"

    heads = find_headings(text)
    spans: dict[str, dict] = {}
    next_id = 1
    open_stack: list[dict] = []  # headings with id_sp assigned

    def alloc() -> str:
        nonlocal next_id
        sid = str(next_id)
        next_id += 1
        return sid

    # preamble before first heading
    if heads and heads[0]["start"] > 0:
        pre_end = heads[0]["start"]
        pre = text[:pre_end].strip()
        if pre:
            sid = alloc()
            spans[sid] = make_span(
                sid,
                "preamble",
                text,
                0,
                pre_end,
                "preamble",
                [],
                "preamble",
                0,
                pre_end,
            )

    if len(heads) >= 2:
        for h in heads:
            # close deeper/equal levels
            while open_stack and open_stack[-1]["level"] >= h["level"]:
                open_stack.pop()
            parents = parent_chain(open_stack, h["level"])
            sec_s, sec_e = h["start"], h["body_end"]
            sid = alloc()
            h["id_sp"] = sid
            spans[sid] = make_span(
                sid,
                f"h{h['level']}",
                text,
                h["start"],
                h["head_end"],
                h["title"],
                parents,
                h["sec_id"],
                sec_s,
                sec_e,
            )
            open_stack.append(h)

            body_s, body_e = h["head_end"], h["content_end"]
            clauses = find_clauses_in_range(text, body_s, body_e)
            if clauses:
                for c_s, c_e, num in clauses:
                    line_e = _line_end(text, c_s)
                    first = text[c_s:line_e].strip()
                    if not first:
                        continue
                    c_title = strip_md_title(first)[:120] or num
                    cid = alloc()
                    c_parents = parents + [
                        {
                            "id_sp": sid,
                            "text": h["title"],
                            "level": f"h{h['level']}",
                        }
                    ]
                    spans[cid] = make_span(
                        cid,
                        "clause",
                        text,
                        c_s,
                        line_e,
                        c_title,
                        c_parents,
                        h["sec_id"],
                        sec_s,
                        sec_e,
                    )
                    # list items inside clause body (after first line)
                    items = find_list_items_in_range(
                        text, _line_end(text, c_s), c_e
                    )
                    for i_s, _i_e in items:
                        line_e = _line_end(text, i_s)
                        if not text[i_s:line_e].strip():
                            continue
                        iid = alloc()
                        spans[iid] = make_span(
                            iid,
                            "list_item",
                            text,
                            i_s,
                            line_e,
                            c_title,
                            c_parents
                            + [
                                {
                                    "id_sp": cid,
                                    "text": c_title,
                                    "level": "clause",
                                }
                            ],
                            h["sec_id"],
                            sec_s,
                            sec_e,
                        )
            else:
                # no clauses — one body span if non-empty
                body = text[body_s:body_e].strip()
                if body:
                    bid = alloc()
                    spans[bid] = make_span(
                        bid,
                        "body",
                        text,
                        body_s,
                        body_e,
                        h["title"],
                        parents
                        + [
                            {
                                "id_sp": sid,
                                "text": h["title"],
                                "level": f"h{h['level']}",
                            }
                        ],
                        h["sec_id"],
                        sec_s,
                        sec_e,
                    )
    else:
        # few/no headings — whole doc as one section, clause-split
        sec_s, sec_e = 0, len(text)
        sec_id = "doc"
        if heads:
            h = heads[0]
            sid = alloc()
            spans[sid] = make_span(
                sid,
                f"h{h['level']}",
                text,
                h["start"],
                h["head_end"],
                h["title"],
                [],
                sec_id,
                sec_s,
                sec_e,
            )
            clause_start = h["head_end"]
            head_parent = [
                {"id_sp": sid, "text": h["title"], "level": f"h{h['level']}"}
            ]
        else:
            clause_start = 0
            head_parent = []

        clauses = find_clauses_in_range(text, clause_start, sec_e)
        if not clauses and not heads:
            # single document span
            sid = alloc()
            title = strip_md_title(text[:200].split("\n")[0]) or "document"
            spans[sid] = make_span(
                sid, "document", text, 0, len(text), title, [], sec_id, 0, len(text)
            )
        else:
            for c_s, c_e, num in clauses:
                first = text[c_s : _line_end(text, c_s)].strip()
                c_title = strip_md_title(first)[:120] or num
                cid = alloc()
                spans[cid] = make_span(
                    cid,
                    "clause",
                    text,
                    c_s,
                    _line_end(text, c_s),
                    c_title,
                    head_parent,
                    sec_id,
                    sec_s,
                    sec_e,
                )
                items = find_list_items_in_range(text, _line_end(text, c_s), c_e)
                for i_s, i_e in items:
                    line_e = _line_end(text, i_s)
                    iid = alloc()
                    spans[iid] = make_span(
                        iid,
                        "list_item",
                        text,
                        i_s,
                        line_e,
                        c_title,
                        head_parent
                        + [{"id_sp": cid, "text": c_title, "level": "clause"}],
                        sec_id,
                        sec_s,
                        sec_e,
                    )
            # trailing / body without clauses
            if not clauses and heads:
                body_s = heads[0]["head_end"]
                if text[body_s:sec_e].strip():
                    bid = alloc()
                    spans[bid] = make_span(
                        bid,
                        "body",
                        text,
                        body_s,
                        sec_e,
                        heads[0]["title"],
                        head_parent,
                        sec_id,
                        sec_s,
                        sec_e,
                    )

    # validate slices
    for sp in spans.values():
        if text[sp["start_sp"] : sp["end_sp"]] != sp["text_sp"]:
            raise AssertionError(f"text_sp mismatch id={sp['id_sp']}")
        if text[sp["start_sec"] : sp["end_sec"]] != sp["text_sec"]:
            raise AssertionError(f"text_sec mismatch id={sp['id_sp']}")

    return spans


def find_tables(text: str) -> list[dict]:
    tables: list[dict] = []
    for m in HTML_TABLE_RE.finditer(text):
        tables.append(
            {
                "start": m.start(),
                "end": m.end(),
                "format": "html",
                "text": m.group(0),
            }
        )

    # GFM pipe tables: header + separator + rows
    lines = text.splitlines(keepends=True)
    offsets: list[int] = []
    pos = 0
    for ln in lines:
        offsets.append(pos)
        pos += len(ln)

    i = 0
    while i < len(lines) - 1:
        if not GFM_TABLE_START_RE.match(lines[i]):
            i += 1
            continue
        # separator row: |---|---|
        if not re.match(r"^\|?\s*:?-+:?\s*(\|\s*:?-+:?\s*)+\|?\s*$", lines[i + 1]):
            i += 1
            continue
        j = i + 2
        while j < len(lines) and GFM_TABLE_START_RE.match(lines[j]):
            j += 1
        start = offsets[i]
        end = offsets[j - 1] + len(lines[j - 1]) if j - 1 < len(offsets) else len(text)
        # skip if overlaps an HTML table already recorded
        overlap = any(t["start"] <= start < t["end"] for t in tables)
        if not overlap:
            tables.append(
                {
                    "start": start,
                    "end": end,
                    "format": "gfm",
                    "text": text[start:end],
                }
            )
        i = j

    tables.sort(key=lambda t: t["start"])
    for idx, t in enumerate(tables, 1):
        t["id"] = str(idx)
    return tables


def main() -> None:
    docs = iter_docs(DOMAIN)
    total_spans = 0
    total_tables = 0
    for doc in docs:
        doc_id = doc["doc_id"]
        text = doc["doc_text"]
        if not text.endswith("\n"):
            text += "\n"
            doc["doc_text"] = text
        spans = build_spans(text)
        tables = find_tables(text)
        doc["spans"] = spans
        doc["tables"] = tables
        write_doc(doc, refresh_catalog=False)
        total_spans += len(spans)
        total_tables += len(tables)
        print(f"{doc_id[:55]:55} spans={len(spans):4} tables={len(tables):2}")

    rebuild_catalog()
    print("wrote rudn_corpus/docs/ + catalog.jsonl")
    print(f"docs={len(docs)} spans_total={total_spans} tables_total={total_tables}")


if __name__ == "__main__":
    main()
