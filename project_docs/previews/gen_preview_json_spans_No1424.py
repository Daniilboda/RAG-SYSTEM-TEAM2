# -*- coding: utf-8 -*-
"""Regenerate preview_json_spans_No1424.html from rudn_corpus JSON.

Lives in project_docs/previews/ (not in ready_to_corpus / corpus).
"""
from __future__ import annotations

import html
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DOC_ID = "No1424-r_ot_12.08.2026_Ob_ustanovlenii_normativo"
JSON_PATH = ROOT / "rudn_corpus" / "docs" / "stipendii" / f"{DOC_ID}.json"
OUT = Path(__file__).resolve().parent / "preview_json_spans_No1424.html"

TAG_COLORS = {
    "h1": "#1d4ed8",
    "h2": "#1d4ed8",
    "h3": "#c2410c",
    "h4": "#15803d",
    "h5": "#15803d",
    "h6": "#15803d",
    "body": "#7c3aed",
    "clause": "#be123c",
    "list_item": "#0e7490",
}


def esc(s: str) -> str:
    return html.escape(s, quote=True)


def trunc(s: str, n: int = 70) -> str:
    s = re.sub(r"\s+", " ", s).strip()
    return s if len(s) <= n else s[: n - 1] + "…"


def render_doc(text: str, spans: dict) -> str:
    items = sorted(spans.items(), key=lambda kv: int(kv[0]))
    parts: list[str] = []
    pos = 0
    for sid, sp in items:
        a, b = sp["start_sp"], sp["end_sp"]
        if a < pos:
            continue
        if a > pos:
            parts.append(f'<span class="plain">{esc(text[pos:a])}</span>')
        color = TAG_COLORS.get(sp.get("tag", ""), "#64748b")
        chunk = text[a:b]
        parts.append(
            f'<mark class="sp" id="doc-sp-{esc(sid)}" data-sp="{esc(sid)}" '
            f'data-sec="{esc(sp.get("id_sec", ""))}" style="--c:{color}">'
            f'<span class="lbl">#{esc(sid)} {esc(sp.get("tag", ""))}</span>'
            f"{esc(chunk)}</mark>"
        )
        pos = b
    if pos < len(text):
        parts.append(f'<span class="plain">{esc(text[pos:])}</span>')
    return "".join(parts).replace("\n", "<br>\n")


def field_line(sid: str, key: str, val: str, color: str) -> str:
    preview = trunc(val, 90) if key.startswith("text_") else val
    return (
        f'<div class="jfield" data-field="{esc(key)}" data-sp="{esc(sid)}" '
        f'style="--c:{color}">'
        f'<span class="jk">"{esc(key)}"</span> : '
        f'<span class="jv">"{esc(preview)}"</span></div>'
    )


def main() -> None:
    doc = json.loads(JSON_PATH.read_text(encoding="utf-8"))
    spans = doc.get("spans") or {}
    text = doc.get("doc_text") or ""
    meta_keys = [
        "doc_id",
        "domain",
        "doc_type",
        "number",
        "date",
        "source",
        "status",
        "content_hash",
    ]

    legend = "".join(
        f'<i><span class="dot" style="background:{c}"></span>{esc(t)}</i>'
        for t, c in [
            ("h2", TAG_COLORS["h2"]),
            ("h3", TAG_COLORS["h3"]),
            ("h4", TAG_COLORS["h4"]),
            ("body", TAG_COLORS["body"]),
            ("clause", TAG_COLORS["clause"]),
            ("list_item", TAG_COLORS["list_item"]),
        ]
    )

    meta_html = []
    for k in meta_keys:
        if k in doc:
            meta_html.append(
                f'<div class="jline muted"><span class="jk">"{esc(k)}"</span> : '
                f'<span class="jv">"{esc(str(doc[k]))}"</span></div>'
            )

    span_blocks = []
    for sid in sorted(spans.keys(), key=lambda x: int(x)):
        sp = spans[sid]
        color = TAG_COLORS.get(sp.get("tag", ""), "#64748b")
        fields = []
        for key in (
            "id_sp",
            "tag",
            "start_sp",
            "end_sp",
            "title",
            "id_sec",
            "start_sec",
            "end_sec",
            "text_sp",
            "text_sec",
        ):
            if key not in sp:
                continue
            val = sp[key]
            if key == "text_sec":
                val = "(см. подсветку секции в документе)"
            elif key in ("start_sp", "end_sp", "start_sec", "end_sec"):
                val = str(val)
            else:
                val = str(val)
            fields.append(field_line(sid, key, val, color))
        preview = trunc(sp.get("text_sp", ""), 72)
        span_blocks.append(
            f'<button type="button" class="span-block" id="json-sp-{esc(sid)}" '
            f'data-sp="{esc(sid)}" style="--c:{color}">'
            f'<div class="span-head">'
            f'<span class="jk">"{esc(sid)}"</span> <span class="brace">: {{</span> '
            f'<span class="chip">{esc(sp.get("tag", ""))}</span> '
            f'<span class="chip" style="background:#334155">{esc(sp.get("id_sec", ""))}</span>'
            f"</div>"
            f'<div class="span-preview">{esc(preview)}</div>'
            f'<div class="span-fields">{"".join(fields)}'
            f'<div class="brace-end">}}</div></div></button>'
        )

    doc_html = render_doc(text, spans)
    spans_js = json.dumps(
        {
            sid: {
                "id_sp": sp.get("id_sp"),
                "tag": sp.get("tag"),
                "id_sec": sp.get("id_sec"),
                "start_sp": sp.get("start_sp"),
                "end_sp": sp.get("end_sp"),
                "start_sec": sp.get("start_sec"),
                "end_sec": sp.get("end_sec"),
            }
            for sid, sp in spans.items()
        },
        ensure_ascii=False,
    )

    page = f"""<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>JSON ↔ документ — {esc(DOC_ID)}</title>
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
  .toolbar button:hover {{ border-color: #64748b; }}
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
  .json-root {{ font-family: ui-monospace, Consolas, monospace; font-size: 12px; }}
  .jline {{ padding: 2px 6px; border-radius: 4px; }}
  .jk {{ color: #7dd3fc; }}
  .jv {{ color: #fde68a; word-break: break-all; }}
  .muted .jv {{ color: #64748b; }}
  .span-block {{
    display: block; width: 100%; text-align: left;
    background: #0b1324; color: inherit; border: 1px solid var(--line);
    border-left: 3px solid var(--c); border-radius: 8px;
    padding: 8px 10px; margin: 8px 0; cursor: pointer;
    font: inherit; font-family: ui-monospace, Consolas, monospace; font-size: 12px;
  }}
  .span-block:hover {{ border-color: color-mix(in srgb, var(--c) 60%, #64748b); }}
  .span-block.active {{
    background: color-mix(in srgb, var(--c) 18%, #0b1324);
    box-shadow: 0 0 0 1px var(--c);
  }}
  .span-head {{ display: flex; gap: 8px; align-items: center; flex-wrap: wrap; }}
  .chip {{
    font-size: 10px; background: var(--c); color: #fff;
    border-radius: 999px; padding: 1px 7px; font-weight: 700;
  }}
  .span-preview {{ color: #94a3b8; margin: 4px 0 6px; font-size: 11px; }}
  .span-fields {{ display: none; padding-left: 8px; border-left: 1px dashed #334155; }}
  .span-block.active .span-fields {{ display: block; }}
  .jfield {{ padding: 2px 4px; border-radius: 4px; cursor: pointer; }}
  .jfield:hover {{ background: #1e293b; }}
  .jfield.active-field {{ background: color-mix(in srgb, var(--c) 30%, #1e293b); }}
  .brace, .brace-end {{ color: #e2e8f0; }}
  .brace-end {{ margin-top: 4px; }}
  .doc {{
    background: var(--docbg); color: #0f172a;
    border-radius: 10px; padding: 14px 16px 28px; font-size: 0.95rem;
  }}
  .doc .plain {{ color: #334155; }}
  mark.sp {{
    display: inline; background: color-mix(in srgb, var(--c) 14%, white);
    border-bottom: 2px solid var(--c); border-radius: 3px; padding: 0 1px; cursor: pointer;
    transition: background .15s, box-shadow .15s;
    box-decoration-break: clone; -webkit-box-decoration-break: clone;
  }}
  mark.sp .lbl {{
    display: inline-block; font-size: 0.62rem; font-weight: 700;
    color: #fff; background: var(--c); border-radius: 999px;
    padding: 0 5px; margin-right: 4px; vertical-align: middle;
  }}
  mark.sp.active {{
    background: color-mix(in srgb, var(--c) 45%, white);
    box-shadow: 0 0 0 2px var(--c);
  }}
  mark.sp.sec-glow {{
    background: color-mix(in srgb, var(--c) 28%, white);
    outline: 1px dashed color-mix(in srgb, var(--c) 70%, #94a3b8);
  }}
  #modeHint {{ color: #fde68a; font-size: 0.85rem; min-height: 1.2em; }}
</style>
</head>
<body>
<div class="wrap">
  <h1>JSON ↔ документ · клик по полю подсвечивает текст</h1>
  <p class="sub"><code>{esc(DOC_ID)}</code> · {len(spans)} spans ·
  клик по блоку span в JSON → подсветка <code>text_sp</code>; клик по
  <code>start_sec</code>/<code>end_sec</code>/<code>text_sec</code>/<code>id_sec</code> → вся секция</p>

  <div class="toolbar">
    <button type="button" id="btnClear">Сбросить подсветку</button>
    <span id="modeHint"></span>
    <div class="legend">{legend}</div>
  </div>

  <div class="split">
    <section class="panel">
      <div class="panel-h">JSON (кликабельные spans)</div>
      <div class="panel-b json-root" id="jsonPanel">
        <div class="brace">{{</div>
        {"".join(meta_html)}
        <div class="section-label">"spans" : {{</div>
        {"".join(span_blocks)}
        <div class="brace-end">}}</div>
        <div class="jline muted"><span class="jk">"tables"</span> : <span class="jv">[]</span></div>
        <div class="brace-end">}}</div>
      </div>
    </section>
    <section class="panel">
      <div class="panel-h">Документ (preview) · подсветка из JSON</div>
      <div class="panel-b"><div class="doc" id="doc">{doc_html}</div></div>
    </section>
  </div>
</div>
<script>
const SPANS = {spans_js};

function clearActive() {{
  document.querySelectorAll('.span-block.active').forEach(el => el.classList.remove('active'));
  document.querySelectorAll('.jfield.active-field').forEach(el => el.classList.remove('active-field'));
  document.querySelectorAll('mark.sp.active, mark.sp.sec-glow').forEach(el => {{
    el.classList.remove('active');
    el.classList.remove('sec-glow');
  }});
  document.getElementById('modeHint').textContent = '';
}}

function highlightSpan(id, mode, fieldEl) {{
  clearActive();
  const block = document.getElementById('json-sp-' + id);
  const mark = document.getElementById('doc-sp-' + id);
  if (block) {{
    block.classList.add('active');
    block.scrollIntoView({{ behavior: 'smooth', block: 'nearest' }});
  }}
  if (fieldEl) fieldEl.classList.add('active-field');
  if (!mark) return;
  const sec = mark.dataset.sec;
  if (mode === 'section') {{
    document.querySelectorAll('mark.sp[data-sec="' + sec + '"]').forEach(el => {{
      el.classList.add('sec-glow');
    }});
    mark.classList.add('active');
    document.getElementById('modeHint').textContent =
      'Секция id_sec=' + sec + ' · активный span #' + id;
  }} else {{
    mark.classList.add('active');
    document.getElementById('modeHint').textContent =
      'text_sp span #' + id + ' (' + ((SPANS[id] && SPANS[id].tag) || '') + ')';
  }}
  mark.scrollIntoView({{ behavior: 'smooth', block: 'center' }});
}}

document.getElementById('jsonPanel').addEventListener('click', (e) => {{
  const field = e.target.closest('.jfield');
  const block = e.target.closest('.span-block');
  if (!block) return;
  const id = block.dataset.sp;
  if (field) {{
    e.stopPropagation();
    const fk = field.dataset.field;
    const sectionFields = new Set(['id_sec', 'start_sec', 'end_sec', 'text_sec']);
    highlightSpan(id, sectionFields.has(fk) ? 'section' : 'span', field);
    return;
  }}
  highlightSpan(id, 'span');
}});

document.getElementById('doc').addEventListener('click', (e) => {{
  const mark = e.target.closest('mark.sp');
  if (!mark) return;
  highlightSpan(mark.dataset.sp, 'span');
}});

document.getElementById('btnClear').addEventListener('click', clearActive);
</script>
</body>
</html>
"""
    OUT.write_text(page, encoding="utf-8")
    print(f"wrote {OUT} spans={len(spans)} chars={len(text)}")


if __name__ == "__main__":
    main()
