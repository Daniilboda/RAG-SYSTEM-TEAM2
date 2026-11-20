# -*- coding: utf-8 -*-
"""Regenerate preview_chunks_1356.html from chunking/chunks.jsonl + K1 page.

Document with HTML tables (1356_about_support_measures). Click a chunk →
highlight char_start..char_end; tables render as HTML (not escaped tags).
Lives in project_docs/previews/.
"""
from __future__ import annotations

import html
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SOURCE_DOC_ID = "1356_about_support_measures"
CHUNKS_PATH = ROOT / "chunking" / "chunks.jsonl"
SNAPSHOT = ROOT / "snapshot_k1" / "stipendii_lp_v1"
OUT = Path(__file__).resolve().parent / "preview_chunks_1356.html"
HTML_TABLE_RE = re.compile(r"(?is)<table\b.*?</table>")
HTML_TR_RE = re.compile(r"(?is)<tr\b[^>]*>.*?</tr>")
HTML_TABLE_OPEN_RE = re.compile(r"(?is)<table\b[^>]*>")

# Distinct-ish palette for chunk_index cycling
PALETTE = [
    "#1d4ed8",
    "#c2410c",
    "#15803d",
    "#7c3aed",
    "#be123c",
    "#0e7490",
    "#a16207",
    "#4f46e5",
    "#db2777",
    "#059669",
    "#0284c7",
    "#ea580c",
]


def esc(s: str) -> str:
    return html.escape(s, quote=True)


def trunc(s: str, n: int = 80) -> str:
    s = re.sub(r"\s+", " ", s).strip()
    return s if len(s) <= n else s[: n - 1] + "…"


def load_chunks() -> list[dict]:
    rows = [
        json.loads(line)
        for line in CHUNKS_PATH.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    cs = [r for r in rows if r.get("source_doc_id") == SOURCE_DOC_ID]
    cs.sort(key=lambda r: (int(r["chunk_index"]), int(r["char_start"])))
    if not cs:
        raise SystemExit(f"no chunks for {SOURCE_DOC_ID}")
    return cs


def load_page(doc_id: str) -> str:
    path = SNAPSHOT / "pages" / f"{doc_id}.txt"
    return path.read_text(encoding="utf-8")


def color_for(idx: int) -> str:
    return PALETTE[idx % len(PALETTE)]


def _covering(chunks: list[dict], a: int, b: int) -> list[dict]:
    """Chunks that fully contain [a, b)."""
    return [
        c
        for c in chunks
        if int(c["char_start"]) <= a and int(c["char_end"]) >= b
    ]


def _overlapping(chunks: list[dict], a: int, b: int) -> list[dict]:
    """Chunks that intersect [a, b) — needed for tables split across chunks."""
    return [
        c
        for c in chunks
        if not (int(c["char_end"]) <= a or int(c["char_start"]) >= b)
    ]


def _wrap_seg(inner: str, covering: list[dict]) -> str:
    if not covering:
        return f'<span class="plain">{inner}</span>'
    classes = " ".join(f"c{int(c['chunk_index'])}" for c in covering)
    primary = min(covering, key=lambda c: int(c["chunk_index"]))
    color = color_for(int(primary["chunk_index"]))
    ids = ",".join(str(int(c["chunk_index"])) for c in covering)
    return (
        f'<span class="seg {classes}" data-chunks="{esc(ids)}" '
        f'style="--c:{color}">{inner}</span>'
    )


def _annotate_tr(tr_html: str, covering: list[dict]) -> str:
    """Вешает seg-классы на <tr>, чтобы подсвечивать только строки чанка."""
    if not covering:
        return tr_html
    classes = " ".join(f"c{int(c['chunk_index'])}" for c in covering)
    primary = min(covering, key=lambda c: int(c["chunk_index"]))
    color = color_for(int(primary["chunk_index"]))
    ids = ",".join(str(int(c["chunk_index"])) for c in covering)
    return HTML_TR_RE.sub(
        lambda m: re.sub(
            r"(?i)<tr\b",
            f'<tr class="seg {classes}" data-chunks="{esc(ids)}" style="--c:{color}"',
            m.group(0),
            count=1,
        ),
        tr_html,
        count=1,
    )


def _render_plain_range(text: str, chunks: list[dict], start: int, end: int) -> str:
    """Highlight non-table slice [start, end)."""
    if start >= end:
        return ""
    breaks = {start, end}
    for c in chunks:
        a, b = int(c["char_start"]), int(c["char_end"])
        if b <= start or a >= end:
            continue
        breaks.add(max(start, a))
        breaks.add(min(end, b))
    points = sorted(breaks)
    parts: list[str] = []
    for i in range(len(points) - 1):
        a, b = points[i], points[i + 1]
        if a >= b:
            continue
        covering = _covering(chunks, a, b)
        piece = esc(text[a:b]).replace("\n", "<br>\n")
        parts.append(_wrap_seg(piece, covering))
    return "".join(parts)


def _row_chunks(chunks: list[dict], a: int, b: int) -> list[dict]:
    """Чанки для строки: полное покрытие, иначе пересечение (rare mid-row split)."""
    full = _covering(chunks, a, b)
    if full:
        return full
    return _overlapping(chunks, a, b)


def _render_table(text: str, chunks: list[dict], start: int, end: int) -> str:
    """Рендерит <table> с подсветкой по <tr> в границах чанка."""
    table = text[start:end]
    open_m = HTML_TABLE_OPEN_RE.match(table)
    open_tag = open_m.group(0) if open_m else "<table>"
    cursor = open_m.end() if open_m else 0
    parts: list[str] = [open_tag]
    for tr in HTML_TR_RE.finditer(table):
        if tr.start() > cursor:
            parts.append(table[cursor : tr.start()])
        abs_a = start + tr.start()
        abs_b = start + tr.end()
        parts.append(_annotate_tr(tr.group(0), _row_chunks(chunks, abs_a, abs_b)))
        cursor = tr.end()
    if cursor < len(table):
        parts.append(table[cursor:])
    return f'<div class="table-block">{"".join(parts)}</div>'


def render_doc(text: str, chunks: list[dict]) -> str:
    """Partition by chunk bounds; HTML <table> — подсветка по строкам чанка."""
    parts: list[str] = []
    pos = 0
    for m in HTML_TABLE_RE.finditer(text):
        parts.append(_render_plain_range(text, chunks, pos, m.start()))
        parts.append(_render_table(text, chunks, m.start(), m.end()))
        pos = m.end()
    parts.append(_render_plain_range(text, chunks, pos, len(text)))
    return "".join(parts)


def main() -> None:
    chunks = load_chunks()
    doc_id = chunks[0]["doc_id"]
    text = load_page(doc_id)
    for c in chunks:
        a, b = int(c["char_start"]), int(c["char_end"])
        if text[a:b] != c["text"]:
            raise SystemExit(f"slice mismatch chunk_index={c['chunk_index']}")

    legend = "".join(
        f'<i><span class="dot" style="background:{color_for(i)}"></span>#{i}</i>'
        for i in range(min(8, len(chunks)))
    )

    show_keys = [
        "chunk_id",
        "chunk_index",
        "doc_id",
        "source_doc_id",
        "title",
        "section",
        "headings",
        "breadcrumbs",
        "char_start",
        "char_end",
        "token_count",
        "n_chunks",
        "chunker",
        "embedding_model",
        "snapshot_id",
        "content_hash",
        "doc_content_hash",
        "embed_text",
        "text",
    ]

    cards: list[str] = []
    meta_js: dict[str, dict] = {}
    for c in chunks:
        idx = int(c["chunk_index"])
        color = color_for(idx)
        headings = c.get("headings") or []
        head = " › ".join(str(h) for h in headings) if headings else "(no heading)"
        preview = trunc(c.get("text") or "", 90)
        meta_js[str(idx)] = {
            "chunk_id": c.get("chunk_id"),
            "chunk_index": idx,
            "char_start": int(c["char_start"]),
            "char_end": int(c["char_end"]),
            "token_count": c.get("token_count"),
            "headings": headings,
            "embed_text": c.get("embed_text") or "",
            "text": c.get("text") or "",
        }
        fields_html: list[str] = []
        for key in show_keys:
            if key not in c:
                continue
            val = c[key]
            if isinstance(val, (list, dict)):
                shown = json.dumps(val, ensure_ascii=False)
            else:
                shown = str(val)
            # keep long fields readable but not endless in the card
            if key in ("text", "embed_text") and len(shown) > 500:
                shown_view = shown[:500] + "…"
            else:
                shown_view = shown
            clickable = ' clickable" data-field="' + esc(key) + '"' if key == "embed_text" else '"'
            hint = (
                ' <span class="field-hint">← клик: полный текст для вектора</span>'
                if key == "embed_text"
                else ""
            )
            fields_html.append(
                f'<div class="jfield{clickable}>'
                f'<span class="jk">"{esc(key)}"</span> : '
                f'<span class="jv">{esc(shown_view)}</span>{hint}</div>'
            )
        cards.append(
            f'<button type="button" class="chunk-card" id="chunk-{idx}" '
            f'data-idx="{idx}" style="--c:{color}">'
            f'<div class="chunk-head">'
            f'<span class="chip">#{idx}</span>'
            f'<span class="meta">{int(c["char_start"])}–{int(c["char_end"])} · '
            f'{esc(str(c.get("token_count", "?")))} tok</span>'
            f"</div>"
            f'<div class="heads">{esc(head)}</div>'
            f'<div class="preview">{esc(preview)}</div>'
            f'<div class="fields">{"".join(fields_html)}</div>'
            f"</button>"
        )

    doc_html = render_doc(text, chunks)
    chunks_json = json.dumps(meta_js, ensure_ascii=False)
    n_tables = len(HTML_TABLE_RE.findall(text))

    page = f"""<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>Chunks ↔ документ — {esc(SOURCE_DOC_ID)}</title>
<style>
  :root {{
    --bg: #0b1220; --panel: #0f172a; --text: #e5e7eb; --muted: #94a3b8;
    --line: #1f2937; --docbg: #f8fafc;
  }}
  * {{ box-sizing: border-box; }}
  body {{
    margin: 0; font: 14px/1.5 "Segoe UI", system-ui, sans-serif; color: var(--text);
    background: radial-gradient(1000px 500px at 0% 0%, #1e3a5f55, transparent),
                radial-gradient(800px 400px at 100% 0%, #134e4a44, transparent), var(--bg);
  }}
  .wrap {{ max-width: 1400px; margin: 0 auto; padding: 18px 14px 48px; }}
  h1 {{ font-size: 1.2rem; margin: 0 0 4px; }}
  .sub {{ color: var(--muted); margin: 0 0 14px; font-size: 0.92rem; }}
  .toolbar {{ display: flex; flex-wrap: wrap; gap: 8px; align-items: center; margin-bottom: 12px; }}
  .toolbar button {{
    background: #1e293b; color: var(--text); border: 1px solid var(--line);
    border-radius: 8px; padding: 6px 10px; cursor: pointer; font-size: 0.85rem;
  }}
  .legend {{ display: flex; flex-wrap: wrap; gap: 6px; }}
  .legend i {{
    display: inline-flex; align-items: center; gap: 5px; font-style: normal;
    font-size: 0.75rem; border: 1px solid var(--line); border-radius: 999px;
    padding: 2px 8px; background: #0b1324;
  }}
  .dot {{ width: 9px; height: 9px; border-radius: 2px; display: inline-block; }}
  .split {{
    display: grid; grid-template-columns: minmax(320px, 40%) 1fr; gap: 12px; align-items: stretch;
  }}
  @media (max-width: 700px) {{ .split {{ grid-template-columns: 1fr; }} }}
  .panel {{
    background: var(--panel); border: 1px solid var(--line); border-radius: 14px;
    overflow: hidden; display: flex; flex-direction: column;
    min-height: 70vh; max-height: calc(100vh - 120px);
  }}
  .panel-h {{
    padding: 10px 14px; border-bottom: 1px solid var(--line);
    font-size: 0.78rem; text-transform: uppercase; letter-spacing: .06em;
    color: var(--muted); background: #0b1324;
  }}
  .panel-b {{ overflow: auto; padding: 10px 12px 20px; flex: 1; }}
  .chunk-card {{
    display: block; width: 100%; text-align: left;
    background: #0b1324; color: inherit; border: 1px solid var(--line);
    border-left: 3px solid var(--c); border-radius: 8px;
    padding: 10px 12px; margin: 8px 0; cursor: pointer; font: inherit;
  }}
  .chunk-card:hover {{ border-color: color-mix(in srgb, var(--c) 60%, #64748b); }}
  .chunk-card.active {{
    background: color-mix(in srgb, var(--c) 18%, #0b1324);
    box-shadow: 0 0 0 1px var(--c);
  }}
  .chunk-head {{ display: flex; gap: 8px; align-items: center; flex-wrap: wrap; }}
  .chip {{
    font-size: 11px; background: var(--c); color: #fff;
    border-radius: 999px; padding: 1px 8px; font-weight: 700;
  }}
  .meta {{ color: #94a3b8; font-size: 11px; font-family: ui-monospace, Consolas, monospace; }}
  .heads {{ color: #cbd5e1; font-size: 12px; margin: 4px 0; }}
  .preview {{ color: #94a3b8; font-size: 11px; }}
  .fields {{
    display: none; margin-top: 8px; padding-left: 8px;
    border-left: 1px dashed #334155;
    font-family: ui-monospace, Consolas, monospace; font-size: 11px;
  }}
  .chunk-card.active .fields {{ display: block; }}
  .jfield {{ padding: 2px 0; word-break: break-word; }}
  .jfield.clickable {{
    cursor: pointer; border-radius: 4px; padding: 4px 6px; margin: 2px -6px;
    border: 1px solid transparent;
  }}
  .jfield.clickable:hover {{ background: #1e293b; border-color: #64748b; }}
  .jfield.clickable.active-field {{
    background: color-mix(in srgb, var(--c) 28%, #1e293b);
    border-color: var(--c);
  }}
  .jk {{ color: #7dd3fc; }}
  .jv {{ color: #fde68a; white-space: pre-wrap; }}
  .field-hint {{ color: #86efac; font-size: 10px; margin-left: 6px; }}
  .muted {{ color: #64748b; }}
  .right-col {{
    display: grid; grid-template-rows: 1fr 1fr; gap: 12px; min-height: 70vh;
    max-height: calc(100vh - 120px);
  }}
  .right-col .panel {{ min-height: 0; max-height: none; height: 100%; }}
  .doc {{
    background: var(--docbg); color: #0f172a;
    border-radius: 10px; padding: 14px 16px 28px; font-size: 0.95rem;
  }}
  .doc .plain {{ color: #334155; }}
  .doc table {{
    border-collapse: collapse; width: 100%; margin: 10px 0;
    font-size: 0.82rem; background: #fff;
  }}
  .doc th, .doc td {{
    border: 1px solid #cbd5e1; padding: 5px 8px; vertical-align: top;
  }}
  .doc th {{ background: #e2e8f0; font-weight: 600; }}
  .table-block {{
    display: block; margin: 10px 0; padding: 6px; border-radius: 8px;
    position: relative;
    border: 1px solid #cbd5e1;
    background: #fff;
  }}
  .table-block::before {{
    content: "TABLE";
    position: absolute; top: -8px; left: 10px;
    font-size: 9px; font-weight: 700; letter-spacing: .06em;
    background: #64748b; color: #fff;
    border-radius: 999px; padding: 1px 7px;
  }}
  .seg {{
    background: color-mix(in srgb, var(--c) 10%, white);
    border-bottom: 1px solid color-mix(in srgb, var(--c) 35%, white);
    border-radius: 2px;
  }}
  tr.seg {{
    background: color-mix(in srgb, var(--c) 8%, white);
  }}
  .doc[data-active] .seg {{ opacity: 0.35; }}
  .doc[data-active] tr.seg {{ opacity: 0.28; }}
  .doc[data-active] .seg.on {{
    opacity: 1;
    background: color-mix(in srgb, var(--hl, var(--c)) 42%, white);
    box-shadow: 0 0 0 2px var(--hl, var(--c));
  }}
  .doc[data-active] tr.seg.on {{
    opacity: 1;
    outline: 2px solid var(--hl, var(--c));
    outline-offset: -2px;
    background: color-mix(in srgb, var(--hl, var(--c)) 30%, white);
  }}
  .doc[data-active] tr.seg.on th,
  .doc[data-active] tr.seg.on td {{
    background: color-mix(in srgb, var(--hl, var(--c)) 28%, white);
  }}
  .embed-box {{
    background: #0b1324; border: 1px solid var(--line); border-radius: 10px;
    padding: 12px 14px; font-family: ui-monospace, Consolas, monospace;
    font-size: 12px; white-space: pre-wrap; word-break: break-word;
    color: #e2e8f0; min-height: 100%;
  }}
  .embed-box.empty {{ color: #64748b; font-family: inherit; }}
  .embed-box.active {{
    border-color: #86efac;
    box-shadow: 0 0 0 1px #86efac55;
  }}
  #modeHint {{ color: #fde68a; font-size: 0.85rem; min-height: 1.2em; }}
</style>
</head>
<body>
<div class="wrap">
  <h1>Chunks ↔ документ (с таблицами)</h1>
  <p class="sub"><code>{esc(SOURCE_DOC_ID)}</code> · {len(chunks)} chunks · {n_tables} HTML tables ·
  клик по чанку → подсветка <code>text</code> (в таблицах — только свои <code>&lt;tr&gt;</code>);
  клик по <code>embed_text</code> → текст для векторов</p>

  <div class="toolbar">
    <button type="button" id="btnClear">Сбросить подсветку</button>
    <span id="modeHint"></span>
    <div class="legend">{legend}</div>
  </div>

  <div class="split">
    <section class="panel">
      <div class="panel-h">Chunks (кликабельные)</div>
      <div class="panel-b" id="chunkPanel">{"".join(cards)}</div>
    </section>
    <div class="right-col">
      <section class="panel">
        <div class="panel-h">Документ (K1 page) · подсветка text</div>
        <div class="panel-b"><div class="doc" id="doc">{doc_html}</div></div>
      </section>
      <section class="panel">
        <div class="panel-h">embed_text → векторы (то, что эмбеддится)</div>
        <div class="panel-b">
          <pre class="embed-box empty" id="embedView">Кликни поле "embed_text" в карточке чанка — здесь появится полный текст для эмбеддинга.</pre>
        </div>
      </section>
    </div>
  </div>
</div>
<script>
const CHUNKS = {chunks_json};
const COLORS = {json.dumps(PALETTE)};

function clearActive() {{
  document.querySelectorAll('.chunk-card.active').forEach(el => el.classList.remove('active'));
  document.querySelectorAll('.jfield.active-field').forEach(el => el.classList.remove('active-field'));
  const doc = document.getElementById('doc');
  doc.removeAttribute('data-active');
  document.querySelectorAll('.seg.on').forEach(el => {{
    el.classList.remove('on');
    el.style.removeProperty('--hl');
  }});
  resetEmbedPanel();
  document.getElementById('modeHint').textContent = '';
}}

function resetEmbedPanel() {{
  const emb = document.getElementById('embedView');
  emb.textContent = 'Кликни поле "embed_text" в карточке чанка — здесь появится полный текст для эмбеддинга.';
  emb.classList.add('empty');
  emb.classList.remove('active');
  document.querySelectorAll('.jfield.active-field').forEach(el => el.classList.remove('active-field'));
}}

function highlightChunk(idx, opts) {{
  opts = opts || {{}};
  document.querySelectorAll('.chunk-card.active').forEach(el => el.classList.remove('active'));
  if (!opts.keepEmbed) resetEmbedPanel();
  const doc = document.getElementById('doc');
  doc.removeAttribute('data-active');
  document.querySelectorAll('.seg.on').forEach(el => {{
    el.classList.remove('on');
    el.style.removeProperty('--hl');
  }});

  const card = document.getElementById('chunk-' + idx);
  const meta = CHUNKS[String(idx)];
  if (card) {{
    card.classList.add('active');
    card.scrollIntoView({{ behavior: 'smooth', block: 'nearest' }});
  }}
  if (!meta) return;
  doc.setAttribute('data-active', String(idx));
  const hl = COLORS[idx % COLORS.length];
  let first = null;
  document.querySelectorAll('.seg.c' + idx).forEach(el => {{
    el.classList.add('on');
    el.style.setProperty('--hl', hl);
    if (!first) first = el;
  }});
  document.getElementById('modeHint').textContent =
    'chunk #' + idx + ' · text ' + meta.char_start + '–' + meta.char_end +
    ' · ' + (meta.token_count ?? '?') + ' tok';
  if (first && !opts.skipScrollDoc) first.scrollIntoView({{ behavior: 'smooth', block: 'center' }});
}}

function showEmbedText(idx, fieldEl) {{
  highlightChunk(idx, {{ keepEmbed: true, skipScrollDoc: true }});
  document.querySelectorAll('.jfield.active-field').forEach(el => el.classList.remove('active-field'));
  if (fieldEl) fieldEl.classList.add('active-field');
  const meta = CHUNKS[String(idx)];
  const emb = document.getElementById('embedView');
  emb.textContent = (meta && meta.embed_text) ? meta.embed_text : '(пусто)';
  emb.classList.remove('empty');
  emb.classList.add('active');
  document.getElementById('modeHint').textContent =
    'chunk #' + idx + ' · показан embed_text (' + emb.textContent.length + ' символов) → векторы';
  emb.scrollIntoView({{ behavior: 'smooth', block: 'nearest' }});
}}

document.getElementById('chunkPanel').addEventListener('click', (e) => {{
  const field = e.target.closest('.jfield.clickable');
  const card = e.target.closest('.chunk-card');
  if (!card) return;
  const idx = Number(card.dataset.idx);
  if (field && field.dataset.field === 'embed_text') {{
    e.preventDefault();
    e.stopPropagation();
    showEmbedText(idx, field);
    return;
  }}
  highlightChunk(idx);
}});

document.getElementById('doc').addEventListener('click', (e) => {{
  const seg = e.target.closest('.seg');
  if (!seg || !seg.dataset.chunks) return;
  const ids = seg.dataset.chunks.split(',').map(Number);
  let best = ids[0];
  let bestLen = 1e18;
  for (const id of ids) {{
    const m = CHUNKS[String(id)];
    if (!m) continue;
    const len = m.char_end - m.char_start;
    if (len < bestLen) {{ bestLen = len; best = id; }}
  }}
  highlightChunk(best);
}});

document.getElementById('btnClear').addEventListener('click', clearActive);
</script>
</body>
</html>
"""
    OUT.write_text(page, encoding="utf-8")
    print(f"wrote {OUT} chunks={len(chunks)} page_chars={len(text)} tables={n_tables}")


if __name__ == "__main__":
    main()
