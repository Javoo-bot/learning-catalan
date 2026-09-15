# How the book got into `libros/md/`

Source: `libros/A Punt A1+ A2 curs de català.pdf` — a 227-page scan with **no text layer**.
Every page holds exactly one JPEG, stored sideways (`/Rotate 90`).

```
python scripts/extract_pages.py    # PDF -> libros/pages/{,web/}pNNN.jpg, upright
python scripts/ocr_pages.py        # -> libros/md/pNNN.md   (cached, resumable)
python scripts/validate_md.py      # QA gate
```

**`pNNN` is the printed book page.** Verified against the folios on pages
21, 24, 30, 31, 34, 47, 214, 222, 225 and 227.

## Model choice

Picked by bake-off, not by reputation. Five pages spanning every layout —
24 (chart + table), 30 (two-column grammar tables), 31 (matching exercise +
fonètica), 214 and 227 (dense justified dialogue) — were transcribed by three
models and diffed against the same pages read directly during planning.

| Model | 227 pp | Result |
|---|---|---|
| `google/gemini-2.5-pro` | ~$4.60 | **Chosen.** Only model to fill both cells of the merged `l'` in the *Article personal* table (p. 30); preserved real bold; no invented formatting |
| `google/gemini-3-flash-preview` | ~$1.45 | Fast and mostly accurate, but **invented bold** on speaker lines in p. 214 and dropped the merged `l'` cell |
| `google/gemini-2.5-flash` | ~$1.15 | Wrong bold boundaries (`Em **dic**`); left a line-break hyphen unjoined (`Fi-xa't`) |

2.5-pro's one weakness — interleaving two-column layouts — is addressed by
rules 11–13 in the prompt.

## The self-check that matters

The model is asked to report the page number **printed on the page**. We
already know what it should be from the filename, so `folio_ok: false` in a
page's frontmatter means the model was not looking at the page it claimed.
`validate_md.py` treats that as a hard failure.

## Trust boundary

Everything in `libros/md/` is **Catalan, verbatim from the page**. The book is
monolingual — it contains no Spanish. Any Spanish in this repo is translation
added downstream, and is marked as such in `content/SOURCES.md`.

Re-running is free: both scripts skip work already on disk. Use `--force` to
redo specific pages, e.g. `python scripts/ocr_pages.py --force --pages 30,31`.
