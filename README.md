# Snippet Shelf

A small dependency-free web app for saving code snippets.

## Run

```bash
python main.py
```

Then open <http://localhost:8000>.

## Smart tagging and highlights

- The language tag is inferred from the filename extension, with common code-pattern fallbacks when no filename is supplied.
- Snippets are saved to `snippets.json` beside `main.py`.
- Lines containing `TODO` in a comment get an orange highlight.
- Lines containing `NOTE` in a comment get a blue highlight.
- Code is HTML-escaped before rendering so saved snippets remain display-only in the browser.
