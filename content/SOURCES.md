# Where every field comes from

One row per vocabulary item, in `unit-NN.tsv`. The point of this file is that
you can tell, per column, what is the book's and what is not.

| Column | Origin |
|---|---|
| `ca` | **The book.** Catalan as printed in *A Punt A1+ A2*. See `confidence` for how exactly. |
| `es` | **Produced, not from the book.** *A Punt* is monolingual — it contains no Spanish at all. Every gloss is a translation of the real Catalan, never an invented word. |
| `example_ca` | **The book.** A sentence or label printed on the same page, quoted verbatim. |
| `source_page` | **The book.** Printed page number, so you can open the paper book and check. |
| `kind` | Ours: `mot` (single word) or `frase` (usable chunk). Drives the two subdecks. |
| `scenario` | **The book.** From its own OBJECTIUS COMUNICATIUS column (syllabus, pp. 8–11). Full list in `scenarios.tsv`. |
| `topic`, `section` | Ours: grouping for badges and for finding things again. `section` is the book's own banner. |
| `gloss_by` | Which model wrote the Spanish. |
| `confidence` | How literally `ca` matches the page — see below. |

## The three provenance levels

**`verbatim`** — the string occurs on the cited page exactly as written.
Every `frase` is verbatim; that is enforced, because a phrase you are going to
say out loud should be one the book actually prints.

**`lemma`** — a dictionary citation form of a word the page does print. The
page has *Els noms més posats*; the card says `el nom`, so it teaches the
gender. The head word is still checked against the page.

**`derived`** — the book prints the pattern but leaves that cell blank as an
exercise. Only four so far, all in the numerals table on p. 26: `dos`, `dinou`,
`vint-i-u`, `vuitanta`. Listed explicitly on every verification run.

## Checking it yourself

```
python scripts/build_content.py --verify
```

This re-reads `libros/md/` and confirms that every `verbatim` row really is on
its page and every `lemma` row's head word really is too, then prints the
`derived` rows so they stay visible. It is not a claim in a document — it is a
check you can re-run.

It has already caught real mistakes: `el director` was cited to p. 23, which
only prints `la directora`, and `Parlo una mica de català.` was a sentence
shortened from `Parlo l'urdú, l'anglès i una mica de català.` Both were removed
or corrected rather than kept.

## Current state

Unit 1 (pp. 20–33): 224 entries — 200 verbatim, 20 lemma, 4 derived, 0 unverified.
