# -*- coding: utf-8 -*-
"""Join Markdown paragraphs split by PDF page / line wraps (LlamaParse MD).

Structural heuristics only (no LLM). Typical case:

    * … программам бакалавриата, программам

    специалитета), имеющим оценки …

→ one list line. Same for numbered clauses and plain prose when the first
block looks incomplete and the next is a continuation (not a new heading /
list / clause / table).
"""
from __future__ import annotations

import re

HTML_TABLE_RE = re.compile(r"(?is)<table\b.*?</table>")
# start of a new structural block — never glue onto previous
STRUCT_START_RE = re.compile(
    r"^(?:"
    r"#{1,6}\s"  # ATX heading
    r"|[*\-•]\s"  # bullet
    r"|\d+(?:\.\d+)*\.\s"  # 1. / 1.1.
    r"|\|.+\|"  # GFM table row
    r"|</?table\b"
    r"|</?tr\b"
    r"|</?t[hd]\b"
    r")",
    re.I,
)
# page junk between wrap halves (rare after SED strip)
PAGE_JUNK_RE = re.compile(
    r"(?i)^(?:стр\.?\s*\d+|-\s*\d+\s*-|\d+\s*/\s*\d+|№\s*\d+[\-\u2013]?[а-яa-z]?)\s*$"
)
TERMINAL_END = tuple(".!?;:…")
SOFT_HYPHEN_END = ("-", "\u00ad", "\u2010", "\u2011")


def _last_content_line(block: str) -> str:
    for ln in reversed(block.splitlines()):
        if ln.strip():
            return ln.rstrip()
    return ""


def _first_content_line(block: str) -> str:
    for ln in block.splitlines():
        if ln.strip():
            return ln.strip()
    return ""


def _is_incomplete(line: str) -> bool:
    """True if line looks cut mid-phrase (judge by ending, not by bullet/heading start)."""
    s = line.rstrip()
    if not s:
        return False
    if s.endswith(TERMINAL_END):
        return False
    # mid-phrase / open constructs — strong signals
    if s.endswith((",", "(", "[", "{", "«", "/", "\\") + SOFT_HYPHEN_END):
        return True
    # ends with letter/digit/closing quote without sentence end
    ch = s[-1]
    if ch.isalnum() or ch in "»\")]}":
        return True
    return False


def _is_continuation(line: str) -> bool:
    s = line.strip()
    if not s or STRUCT_START_RE.match(s):
        return False
    if PAGE_JUNK_RE.match(s):
        return False
    # closing / mid-word leftovers after page break
    if s[0].islower():
        return True
    if s[0] in "),.;:]»\"'":
        return True
    # Capitalized continuation of a legal phrase is common after page break
    # when previous ended with comma / open paren / hyphen — allow those via caller
    return False


def _should_join(left: str, right: str) -> bool:
    a = _last_content_line(left)
    b = _first_content_line(right)
    if not a or not b:
        return False
    if not _is_incomplete(a):
        return False
    if STRUCT_START_RE.match(b):
        return False
    if PAGE_JUNK_RE.match(b):
        return False
    # Strong incomplete end → accept almost any non-structure continuation
    if a.endswith((",", "(", "[", "{", "«") + SOFT_HYPHEN_END):
        return not STRUCT_START_RE.match(b)
    # Weaker incomplete (ends with alnum): require clear continuation cue
    return _is_continuation(b)


def _glue(left: str, right: str) -> str:
    a = left.rstrip()
    b = right.lstrip()
    # soft hyphen at end of last line → join without hyphen/space
    lines = a.splitlines()
    last = lines[-1].rstrip()
    rest_left = "\n".join(lines[:-1])
    first_b, _, rest_b = b.partition("\n")
    first_b = first_b.strip()
    if last.endswith(SOFT_HYPHEN_END) and first_b[:1].isalnum():
        merged_line = last[:-1] + first_b
    else:
        # no space before ),.;:]
        if first_b[:1] in "),.;:]»\"'":
            merged_line = last + first_b
        else:
            merged_line = last + " " + first_b
    parts = []
    if rest_left:
        parts.append(rest_left)
    parts.append(merged_line)
    if rest_b.strip():
        parts.append(rest_b.lstrip("\n"))
    return "\n".join(parts)


def _join_paragraphs(text: str) -> tuple[str, int]:
    """Join adjacent non-empty blocks separated by blank lines when wrap-like."""
    # Keep blank-line separators; work on paragraph list
    parts = re.split(r"\n{2,}", text)
    if len(parts) < 2:
        return text, 0
    out: list[str] = []
    joins = 0
    i = 0
    while i < len(parts):
        cur = parts[i]
        while i + 1 < len(parts) and _should_join(cur, parts[i + 1]):
            cur = _glue(cur, parts[i + 1])
            joins += 1
            i += 1
        out.append(cur)
        i += 1
    return "\n\n".join(out), joins


def merge_broken_wraps(md: str) -> str:
    """Return MD with page/line wraps rejoined; tables left untouched."""
    if not md:
        return md
    pieces: list[str] = []
    pos = 0
    total_joins = 0
    for m in HTML_TABLE_RE.finditer(md):
        before = md[pos : m.start()]
        fixed, n = _join_paragraphs(before)
        total_joins += n
        pieces.append(fixed)
        pieces.append(m.group(0))
        pos = m.end()
    tail = md[pos:]
    fixed, n = _join_paragraphs(tail)
    total_joins += n
    pieces.append(fixed)
    out = "".join(pieces)
    out = re.sub(r"\n{3,}", "\n\n", out)
    if not out.endswith("\n"):
        out += "\n"
    # total_joins available for callers via count_broken_wrap_joins
    merge_broken_wraps.last_joins = total_joins  # type: ignore[attr-defined]
    return out


merge_broken_wraps.last_joins = 0  # type: ignore[attr-defined]


def count_broken_wrap_joins(md: str) -> int:
    """How many wrap joins *would* be applied (runs merge on a copy)."""
    merge_broken_wraps(md)
    return int(getattr(merge_broken_wraps, "last_joins", 0))
