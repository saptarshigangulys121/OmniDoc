"""A dependency-free smart snippet tagging and highlighting app.

Run with ``python main.py`` and open http://localhost:8000.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from html import escape
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse


DATA_FILE = Path(__file__).with_name("snippets.json")
HOST = "127.0.0.1"
PORT = 8000

LANGUAGE_BY_EXTENSION = {
    ".py": "Python",
    ".js": "JavaScript",
    ".jsx": "JavaScript",
    ".ts": "TypeScript",
    ".tsx": "TypeScript",
    ".java": "Java",
    ".c": "C",
    ".h": "C",
    ".cpp": "C++",
    ".cs": "C#",
    ".go": "Go",
    ".rs": "Rust",
    ".rb": "Ruby",
    ".php": "PHP",
    ".swift": "Swift",
    ".kt": "Kotlin",
    ".sh": "Shell",
    ".sql": "SQL",
    ".html": "HTML",
    ".htm": "HTML",
    ".css": "CSS",
    ".json": "JSON",
    ".yaml": "YAML",
    ".yml": "YAML",
    ".md": "Markdown",
}

LANGUAGE_TAGS = {name: f"language:{name.lower().replace('#', 'sharp').replace('+', 'p').replace(' ', '-') }"
                 for name in set(LANGUAGE_BY_EXTENSION.values())}


def load_snippets() -> list[dict]:
    if not DATA_FILE.exists():
        return []
    try:
        value = json.loads(DATA_FILE.read_text(encoding="utf-8"))
        return value if isinstance(value, list) else []
    except (OSError, json.JSONDecodeError):
        return []


def save_snippets(snippets: list[dict]) -> None:
    DATA_FILE.write_text(json.dumps(snippets, indent=2), encoding="utf-8")


def detect_language(filename: str, code: str) -> str:
    """Infer a language from a filename first, then a few safe code signatures."""
    suffix = Path(filename.strip()).suffix.lower()
    if suffix in LANGUAGE_BY_EXTENSION:
        return LANGUAGE_BY_EXTENSION[suffix]

    checks = (
        (r"^\s*<!doctype html|<\/?[a-z][^>]*>", "HTML"),
        (r"^\s*[{\[]|\b(true|false|null)\b", "JSON"),
        (r"\b(import React|console\.log|const |let |=>)", "JavaScript"),
        (r"\b(def |import |from |if __name__ ==)", "Python"),
        (r"\b(SELECT|INSERT INTO|UPDATE)\b", "SQL"),
        (r"^\s*#!/.*\b(bash|sh)\b", "Shell"),
    )
    for pattern, language in checks:
        if re.search(pattern, code, re.IGNORECASE | re.MULTILINE):
            return language
    return "Plain Text"


def comment_kind(line: str, language: str) -> str | None:
    """Return TODO/NOTE only when the marker occurs in a comment-like region."""
    if language in {"HTML", "XML"}:
        comment = r"(?:<!--|//|#|/\*|\*)"
    elif language in {"SQL", "Python", "Ruby", "Shell", "YAML", "Markdown"}:
        comment = r"(?:#|--|//|/\*)"
    else:
        comment = r"(?://|#|/\*|\*)"
    match = re.search(rf"{comment}[^\r\n]*?\b(TODO|NOTE)\b", line, re.IGNORECASE)
    return match.group(1).upper() if match else None


def annotate_code(code: str, language: str) -> list[dict[str, str | int]]:
    return [
        {"number": number, "text": line, "marker": comment_kind(line, language) or ""}
        for number, line in enumerate(code.splitlines() or [""], 1)
    ]


def create_snippet(title: str, filename: str, code: str) -> dict:
    language = detect_language(filename, code)
    return {
        "id": datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S%f"),
        "title": title.strip() or "Untitled snippet",
        "filename": filename.strip(),
        "code": code,
        "language": language,
        "tags": [LANGUAGE_TAGS.get(language, "language:plain-text")],
        "lines": annotate_code(code, language),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }


PAGE = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Snippet Shelf</title>
  <style>
    :root { --bg:#f5f7fb; --ink:#172033; --muted:#667085; --card:#fff; --line:#e5e7eb; }
    * { box-sizing:border-box; }
    body { margin:0; color:var(--ink); background:var(--bg); font:15px/1.5 system-ui,sans-serif; }
    header { padding:38px max(22px, calc((100% - 1100px)/2)); background:#172554; color:#fff; }
    header h1 { margin:0 0 5px; font-size:30px; } header p { margin:0; color:#c7d2fe; }
    main { max-width:1100px; margin:28px auto; padding:0 22px; display:grid; gap:24px; grid-template-columns:350px 1fr; }
    .card { background:var(--card); border:1px solid var(--line); border-radius:14px; padding:20px; box-shadow:0 8px 22px #1725540b; }
    h2 { margin:0 0 14px; font-size:18px; } label { display:block; font-weight:650; margin:13px 0 6px; }
    input, textarea { width:100%; border:1px solid #d0d5dd; border-radius:8px; padding:10px; color:var(--ink); font:inherit; }
    textarea { min-height:260px; resize:vertical; font:13px/1.5 ui-monospace,SFMono-Regular,Consolas,monospace; }
    button { width:100%; margin-top:15px; border:0; border-radius:8px; padding:11px; color:#fff; background:#2563eb; font-weight:700; cursor:pointer; }
    button:hover { background:#1d4ed8; } .hint { color:var(--muted); font-size:12px; }
    .toolbar { display:flex; justify-content:space-between; align-items:center; gap:12px; margin-bottom:14px; }
    .toolbar h2 { margin:0; } .count { color:var(--muted); font-size:13px; }
    .snippet { border:1px solid var(--line); border-radius:10px; overflow:hidden; margin-bottom:16px; }
    .snippet-head { padding:12px 15px; display:flex; align-items:center; justify-content:space-between; gap:10px; background:#fafafa; }
    .snippet-title { font-weight:750; } .filename { color:var(--muted); font-size:12px; }
    .tag { color:#1e40af; background:#dbeafe; border-radius:99px; padding:3px 9px; font:12px ui-monospace,monospace; white-space:nowrap; }
    .code { margin:0; padding:10px 0; overflow:auto; background:#111827; color:#e5e7eb; font:13px/1.65 ui-monospace,SFMono-Regular,Consolas,monospace; }
    .line { display:flex; min-width:max-content; padding-right:18px; border-left:4px solid transparent; }
    .line-no { width:45px; padding-right:12px; color:#6b7280; text-align:right; user-select:none; }
    .line-text { white-space:pre; } .line.todo { background:#7c2d1238; border-left-color:#f97316; }
    .line.note { background:#1e40af42; border-left-color:#60a5fa; }
    .legend { display:flex; gap:14px; color:var(--muted); font-size:12px; margin-top:9px; }
    .legend span::before { content:""; display:inline-block; width:9px; height:9px; border-radius:2px; margin-right:5px; background:currentColor; }
    .todo-label { color:#ea580c; } .note-label { color:#2563eb; }
    .empty { color:var(--muted); text-align:center; padding:35px 10px; border:1px dashed #cbd5e1; border-radius:10px; }
    @media (max-width:750px) { main { grid-template-columns:1fr; } }
  </style>
</head>
<body>
  <header><h1>Snippet Shelf</h1><p>Save code with automatic language tags and visible TODO / NOTE callouts.</p></header>
  <main>
    <section class="card">
      <h2>Save a snippet</h2>
      <form method="post" action="/snippets">
        <label for="title">Title</label><input id="title" name="title" placeholder="Auth helper" required>
        <label for="filename">Filename <span class="hint">(helps identify the language)</span></label>
        <input id="filename" name="filename" placeholder="auth.py">
        <label for="code">Code</label>
        <textarea id="code" name="code" placeholder="# TODO: add validation\ndef login(user):\n    # NOTE: replace this mock later\n    return user" required></textarea>
        <button type="submit">Save snippet</button>
      </form>
      <p class="hint">Language is inferred from the filename first, then common code patterns. Only TODO and NOTE markers in comment lines are highlighted.</p>
    </section>
    <section class="card">
      <div class="toolbar"><h2>Saved snippets</h2><span class="count">{{COUNT}} snippet(s)</span></div>
      {{SNIPPETS}}
    </section>
  </main>
</body>
</html>"""


def render_snippet(snippet: dict) -> str:
    rows = []
    for line in snippet.get("lines", annotate_code(snippet.get("code", ""), snippet.get("language", "Plain Text"))):
        marker = line.get("marker", "")
        rows.append(
            f'<div class="line {marker.lower()}"><span class="line-no">{line["number"]}</span>'
            f'<span class="line-text">{escape(str(line["text"]))}</span></div>'
        )
    return (
        '<article class="snippet"><div class="snippet-head">'
        f'<div><div class="snippet-title">{escape(snippet.get("title", "Untitled snippet"))}</div>'
        f'<div class="filename">{escape(snippet.get("filename", ""))}</div></div>'
        f'<span class="tag">{escape(snippet.get("tags", ["language:plain-text"])[0])}</span></div>'
        f'<div class="code">{"".join(rows)}</div></article>'
    )


class SnippetHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        if urlparse(self.path).path != "/":
            self.send_error(404)
            return
        snippets = load_snippets()
        snippets.sort(key=lambda item: item.get("created_at", ""), reverse=True)
        body = PAGE.replace("{{COUNT}}", str(len(snippets))).replace(
            "{{SNIPPETS}}", "".join(render_snippet(item) for item in snippets)
            or '<div class="empty">No snippets yet. Save your first one.</div>'
        )
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(body.encode("utf-8"))

    def do_POST(self) -> None:
        if urlparse(self.path).path != "/snippets":
            self.send_error(404)
            return
        length = int(self.headers.get("Content-Length", "0"))
        fields = parse_qs(self.rfile.read(length).decode("utf-8"), keep_blank_values=True)
        title, filename, code = (fields.get(key, [""])[0] for key in ("title", "filename", "code"))
        if not code.strip():
            self.send_error(400, "Code is required")
            return
        snippets = load_snippets()
        snippets.append(create_snippet(title, filename, code))
        save_snippets(snippets)
        self.send_response(303)
        self.send_header("Location", "/")
        self.end_headers()


if __name__ == "__main__":
    print(f"Snippet Shelf running at http://{HOST}:{PORT}")
    ThreadingHTTPServer((HOST, PORT), SnippetHandler).serve_forever()
