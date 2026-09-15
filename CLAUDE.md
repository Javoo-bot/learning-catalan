# Catalan A1 deck

> ## ⚠️ THIS REPOSITORY IS PUBLIC
>
> **Check every commit before making it.** A leak here is irreversible: GitHub
> keeps the blob reachable by SHA even after a force-push, and search engines
> and scrapers index public repos within minutes. Rotating a key afterwards is
> the only real remedy, and it is not always possible.
>
> **Never commit:**
> - `.env` or any API key, token or credential — the code must only ever
>   reference variable *names* (`OPEN_ROUTER_API_KEY`), never values.
> - `libros/` — the full transcription of *A Punt A1+ A2* is the whole
>   copyrighted work, not a quotation. The PDF and page scans likewise.
> - `content/private/` — the sentences quoted verbatim from the book.
> - `media/` — photos fetched from Unsplash/Pexels under their own licences.
> - `*.apkg` — build output; share those through AnkiWeb instead.
>
> **Before every commit, run:**
> ```bash
> git status --short                 # nothing unexpected staged
> git diff --cached --stat           # review what is actually going in
> git diff --cached | grep -iE "api[_-]?key|secret|token|password|sk-[a-zA-Z0-9]{16}"
> ```
> If anything matches, stop and fix `.gitignore` before committing.
>
> When adding a new source, a new script or a new content directory, decide
> *first* whether it is publishable, and add it to `.gitignore` if it is not.
> The default for anything derived from the book is: **not publishable.**
>
> ### Copyright: never upload third-party material
>
> Javier does not own the rights to the source material and does not want to
> risk it. The line is between **facts** and **someone's expression**:
>
> | Safe to publish | Never publish |
> |---|---|
> | Verb conjugations (forms are facts) | Any page of a book, scanned or transcribed |
> | Word ↔ word translations | Example sentences copied from a book |
> | Grammar rules **restated in our own words**, with the source cited | Grammar explanations copied verbatim from a site or blog |
> | Sentences we wrote ourselves | Photos, audio or PDFs from anywhere |
> | Short extracts from an open public glossary, attributed | A whole glossary, dictionary or wordlist lifted wholesale |
>
> Concretely, these stay out of git forever: `libros/` (the *A Punt*
> transcription, PDF and page scans), `content/private/` (sentences quoted from
> the book), `media/` (Unsplash/Pexels images).
>
> **Before adding any new source**, ask: who wrote this, and does its licence
> allow redistribution? If the answer is unclear, treat it as *no*, keep it in
> a gitignored directory, and cite it rather than copying it. Citing a source
> and linking to it is always safe; reproducing it is not.

Vocabulary database → Anki decks for a **native Spanish speaker** learning Catalan.

```bash
python scripts/build_situacions.py --situacio cor   # content/situacions/ -> cor_deck.apkg
python scripts/extract_conjugations.py              # libros/md/p199-207 -> content/verbs/
python scripts/build_content.py --verify            # prove every A Punt row is on its page
python scripts/validate_md.py                       # check the book transcription
```

## The five rules

1. **A deck is a place, not a lesson.** `CA · 01 · Al cor`, `CA · 04 · Al bar`. Order
   inside a deck comes from the `seq` column, never from where a word happened to
   come from. That mistake — ordering by source, then alphabetically — is what made
   the first version feel random, and Javier caught it while studying it.
2. **ES → CA only.** One template per note type, one card per note. CA→ES is too easy
   for a Spanish speaker to be worth reviewing.
3. **Flat numbered decks.** No parent deck: tapping a parent is what makes Anki mix
   new cards from several decks at once.
4. **Grouped, not atomised.** Four related words go on one card, not four cards. Fifty
   preposition cards is the failure mode to avoid.
5. **No images, no audio, no numbers.** System fonts only — Anki on a phone cannot
   fetch a webfont. Numbers were cut deliberately: they are a system, not 75 facts.

## The six formats

`frase` · `grup` · `taula` · `buit` · `tria` · `motlle`
(plus `produccio` and `imperatiu`, which reuse the `frase` note type)

A verb gets a **sequence of 7 consecutive cards**: taula (the only time the full
conjugation is shown) → buit → buit → tria between forms → tria between verbs →
imperatiu → produccio. They stay consecutive because notes are emitted in `seq` order
and Anki is set to `Insertion order: Sequential` + `New card sort order: Order
gathered`. **Do not reorder emission** or the sequences break.

Anki templates have no loops, so tables and option lists are rendered to HTML in
Python and stored in a field.

## Layout

```
libros/md/p001..p227.md   the whole A Punt coursebook, transcribed. Done, ~$5, never redo
content/situacions/*.tsv  the study decks. One file per place, column `format`
content/verbs/*.tsv       conjugations: conjugacions.tsv from the book, derivades.tsv by model
content/sources/*.tsv     RESERVE — 1.169 entries, glossed and with pronunciation, but
                          they generate no cards. Draw from them when building a place
content/themes/*.tsv      thematic lexicon, distributed into places
docs/ANKI-SETUP.md        the deck settings. Half the design lives here, not in code
docs/TRANSCRIPTION.md     how the book got scanned, and the model bake-off
```

## Provenance is checkable, not claimed

`confidence` says how literally the Catalan matches the source: `verbatim` (on the
cited page exactly), `lemma` (citation form of a word the page prints), `derived` (the
book prints the *pattern* — e.g. `cantar` follows the `parlar` model on p. 202),
`dictionary` (no page; from a dictionary or the AVL glossary).

The book is **monolingual Catalan**. Every Spanish gloss is produced, never from the
source. That is the one thing to be honest about.

Conjugations come from the book's own tables (p. 202 present, 203 3rd conj., 204
imperfet, 205 futur, **206 imperatiu**, 207 subjuntiu) — verified 9/9 against the
pages. Prefer these over `beveradb-verbs.tsv`, which has typos (`battre`) and 14
labels for 8 tenses.

## Things that bite

**Never auto-apply a model's Catalan "correction".** Unattended it drifts Catalan
toward Spanish: it "fixed" `afeccionar-se` → `aficionar-se` (backwards — DIEC2 lists
the first) and `comissaria` → `comisaria`. Suggestions land in a review file;
decisions are judged in `make_decisions.py` and recorded with a reason.

**Never cache a failed API batch.** An empty cached result makes the retry skip the
batch and lose those entries silently. Cache only on success.

**The cache key includes a hash of the prompt.** Editing a prompt must invalidate old
answers.

**GUIDs must not depend on the deck.** genanki hashes *every* field by default,
including the deck locator, so adding vocabulary re-chunks the decks, changes the
locator, and re-imports everything as duplicates. Situation cards key on
`place:seq`; the old word deck keys on the Catalan word.

**Cognates are excluded from cards, kept in the data.** `la partitura` → `la partitura` has
nothing to recall. ~223 of them.

**`so` is a Spanish respelling, not IPA** — `casa` → `CA-za`, `gener` → `zhe-NÉ`.
Only where a Spanish reading misleads, and only if it covers the whole entry: a
partial hint (`Tant de gust.` → `da`) is worse than none.

**`tria` options:** exactly 4, exactly one marked `*`, no duplicates, and the marked
one must equal `back`. Vary which position is correct between cards — order is fixed
within a card because Anki renders static HTML.

## Why no images

Wyner's method builds connections for words that have none. `muntanya` already arrives
wired to `montaña`, so a photo buys almost nothing. Where Catalan is genuinely hard —
the clitics `en/hi/ho/li`, divergences like `taula`/`finestra`, gender mismatches — a
picture cannot help either. Context sentences do the job with no visual weight.

## Open

- Places still to build: `bar` (110), `moures` (133), `verbs` motor (70),
  `passejant` (93), `motlles` (25). Build one at a time, only when the previous is done.
- `passejant` and `parlar amb algú` need more lexicon than the reserve holds.
- `build_a1a2_deck.py` is superseded by `build_situacions.py`; it still builds the old
  flat word deck from the reserve if ever needed.
