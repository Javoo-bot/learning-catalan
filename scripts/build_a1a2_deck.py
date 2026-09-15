"""Build the Catalan A1 decks: content/*.tsv -> a1a2_deck.apkg.

Three things this file is careful about, all of them things Javier asked for:

**Flat, numbered decks.** `CA · 01 mots · Tot un món`, not a nested tree. Anki
mixes new cards from several subdecks the moment you tap a parent deck, which
is exactly the "random card appearing" that makes him lose the thread. With no
parent there is nothing to tap by accident, and the number says what comes next.

**One direction only.** Spanish on the front, Catalan on the back, a single
template per note. Catalan -> Spanish is too easy for a Spanish speaker to be
worth reviewing, so that card is never generated.

**Design B.** Deck locator, prompt, hairline, answer, and a pronunciation hint
only where a Spanish reading of the Catalan would go wrong. System fonts: Anki
on a phone cannot fetch a webfont.

Imports build_deck for its shared CSS but never calls its main(), so
catalan_deck.apkg is untouched. Deck and model ids sit in their own range.
"""
from __future__ import annotations

import argparse
import csv
import html
import re
import sys
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import genanki  # noqa: E402

import build_deck as bd  # noqa: E402  (module level only defines data)

CONTENT = ROOT / "content"
OUT = ROOT / "a1a2_deck.apkg"

DECK_BASE = 1748295000          # clear of build_deck's 17482930xx
MODEL_ID = 1748295901

MAX_PER_DECK = 160              # small enough that finishing one is a real event

UNIT_TITLES = {
    0: "Domini.cat", 1: "Tot un món", 2: "Família, amics i coneguts",
    3: "Les coses de cada dia", 4: "Com a casa, enlloc", 5: "Històries de vida",
    6: "Menjar-se el món", 7: "Fets i gent", 8: "Temps de canvis",
    9: "Fem les maletes!", 10: "Tenir cura de la salut",
    11: "Feines de tota mena", 12: "I si sortim?",
}
# Study order within a unit: the words first, then what you build out of them.
KIND_ORDER = ["mot", "frase", "sentence"]
KIND_LABEL = {"mot": "mots", "frase": "frases", "sentence": "frases fetes"}

# Entries that must never become a card, with the reason.
DROP_CA = {
    "sóc":      "pre-2016 spelling; the normative form is soc",
    "...i tot": "a fragment of 'fins i tot', which is already an entry",
}

CSS = bd.SHARED_CSS + """
.locator {
  position: absolute; top: 14px; left: 0; right: 0;
  font-size: 11px; letter-spacing: 0.13em; text-transform: uppercase;
  color: #9AA0A4;
}
.card.nightMode .locator { color: #8A9095; }
.ask {
  font-size: 25px; font-weight: 500; line-height: 1.3; margin: 0 auto;
  max-width: 92%;
}
.ask.dim { font-size: 16px; font-weight: 400; color: #7A8084; }
.card.nightMode .ask.dim { color: #9AA1A3; }
.rule { height: 1px; background: #E7E9E7; width: 44%; margin: 16px auto; }
.card.nightMode .rule { background: #333739; }
.answer {
  font-size: 33px; font-weight: 600; line-height: 1.25; margin: 0 auto;
  max-width: 94%;
}
.so {
  margin-top: 14px; font-size: 15px; letter-spacing: 0.04em; color: #7A8084;
}
.card.nightMode .so { color: #9AA1A3; }
.eg {
  margin-top: 16px; font-size: 15px; line-height: 1.45; font-style: italic;
  color: #6B7280; max-width: 92%; margin-left: auto; margin-right: auto;
}
.card.nightMode .eg { color: #9AA1A3; }
"""

_FRONT = (
    '<div class="locator">{{Deck}}</div>'
    '<div class="ask">{{Spanish}}</div>'
)
_BACK = (
    '<div class="locator">{{Deck}}</div>'
    '<div class="ask dim">{{Spanish}}</div>'
    '<div class="rule"></div>'
    '<div class="answer">{{Catalan}}</div>'
    '{{#So}}<div class="so">{{So}}</div>{{/So}}'
    '{{#Example}}<div class="eg">{{Example}}</div>{{/Example}}'
)

MODEL = genanki.Model(
    MODEL_ID,
    "CA A1 (ES->CA)",
    fields=[{"name": n} for n in ("Spanish", "Catalan", "So", "Example", "Deck", "Source")],
    templates=[{"name": "ES -> CA", "qfmt": _FRONT, "afmt": _BACK}],
    css=CSS,
)


def is_cognate(ca: str, es: str) -> bool:
    """Do the two sides differ only by accents, articles or a parenthetical?

    Catalan and Spanish share so much core vocabulary that a card like
    la partitura -> la partitura has nothing to recall. Those stay in the data but do
    not become cards.
    """
    def strip(s: str) -> str:
        s = re.sub(r"\([^)]*\)", "", s)
        s = re.sub(r"^(el |la |els |les |l'|un |una |lo |los |las )", "", s.strip().lower())
        s = "".join(c for c in unicodedata.normalize("NFD", s) if not unicodedata.combining(c))
        return re.sub(r"[^a-z]", "", s)
    a, b = strip(ca), strip(es)
    return bool(a) and a == b


def sort_key(ca: str) -> str:
    """Alphabetical order ignoring articles and accents, so l'ambulatori files
    under 'a' next to acabar rather than under 'l'."""
    s = unicodedata.normalize("NFD", ca.lower().strip())
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = re.sub(r"^(el |la |els |les |l'|un |una )", "", s)
    return re.sub(r"[^a-z0-9 ]", "", s)


def read_tsv(path: Path) -> list[dict]:
    with path.open(encoding="utf-8", newline="") as fh:
        return [r for r in csv.DictReader(fh, delimiter="\t") if (r.get("ca") or "").strip()]


def load_overrides() -> dict[str, dict]:
    """Per-entry corrections that belong to the content, not the code.

    Kept as data so a fix is one line with a reason next to it, and so the
    record of why an entry reads the way it does stays with the entry.
    """
    path = CONTENT / "overrides.tsv"
    if not path.exists():
        return {}
    return {r["ca"].strip(): r for r in read_tsv(path)}


def load_entries(units: set[int] | None) -> list[dict]:
    """Normalise the two on-disk shapes into one entry record.

    content/unit-NN.tsv            -- curated from A Punt; has source_page, example
    content/sources/*.glossed.tsv  -- external list; has the `so` hint
    """
    out: list[dict] = []

    def order(kind: str) -> int:
        return KIND_ORDER.index(kind) if kind in KIND_ORDER else 9

    for path in sorted(CONTENT.glob("unit-*.tsv")):
        for r in read_tsv(path):
            unit = int(r["unit"])
            if units is not None and unit not in units:
                continue
            out.append({
                "ca": r["ca"], "es": r["es"], "so": r.get("so", ""),
                "kind": r["kind"], "unit": unit,
                "example": r.get("example_ca", ""),
                "source": f"A Punt p.{r['source_page']}",
                "sort": (unit, order(r["kind"])),
            })

    if units is None:
        for path in sorted((CONTENT / "sources").glob("*.glossed.tsv")):
            for r in read_tsv(path):
                if not (r.get("es") or "").strip():
                    continue
                out.append({
                    "ca": r["ca"], "es": r["es"], "so": r.get("so", ""),
                    "kind": r["kind"], "unit": 99, "example": "",
                    "source": r.get("source", path.stem),
                    "sort": (99, order(r["kind"])),
                })
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--units", help="only these units, e.g. 1 or 1,2,3")
    ap.add_argument("--decks", help="only these deck numbers, e.g. 1 or 1,2")
    ap.add_argument("--include-cognats", action="store_true",
                    help="also card the entries where ca and es are near-identical")
    ap.add_argument("--max", type=int, default=MAX_PER_DECK)
    ap.add_argument("--out", type=Path, default=OUT)
    args = ap.parse_args()

    units = {int(u) for u in args.units.split(",")} if args.units else None
    want_decks = {int(d) for d in args.decks.split(",")} if args.decks else None

    entries = load_entries(units)
    if not entries:
        sys.exit("[FATAL] no entries; is content/ populated?")

    overrides = load_overrides()
    skipped_cognate = dropped = reglossed = 0
    kept: list[dict] = []
    seen: set[str] = set()
    for e in entries:
        if e["ca"].strip() in DROP_CA:
            dropped += 1
            continue
        ov = overrides.get(e["ca"].strip())
        if ov:
            if ov["action"] == "drop":
                dropped += 1
                continue
            if ov["action"] == "regloss" and ov["value"]:
                e = dict(e, es=ov["value"])
                reglossed += 1
        # Keyed on the Catalan alone, not (ca, kind): the same entry can be
        # filed as a mot in one source and a frase in another ("em dic"), and
        # that is one word to learn, not two. A Punt rows are loaded first, so
        # first-wins keeps the one with a cited page and an example sentence.
        key = e["ca"].strip().lower()
        if key in seen:
            continue
        seen.add(key)
        if not args.include_cognats and is_cognate(e["ca"], e["es"]):
            skipped_cognate += 1
            continue
        kept.append(e)

    # Two Catalan words sharing one Spanish gloss are usually synonyms
    # (aixecar-se / llevar-se). One card teaching both beats two cards with the
    # same prompt and different right answers, which Anki also treats as a
    # duplicate. Merged rather than dropped so no vocabulary is lost.
    merged: list[str] = []
    by_front: dict[tuple, list[dict]] = {}
    for e in kept:
        by_front.setdefault((e["sort"], e["unit"], e["kind"], e["es"].strip().lower()), []).append(e)
    kept = []
    for group in by_front.values():
        head = group[0]
        if len(group) > 1:
            forms = list(dict.fromkeys(g["ca"] for g in group))
            head = dict(head)
            head["ca"] = " / ".join(forms)
            head["so"] = next((g["so"] for g in group if g["so"]), "")
            merged.append(f'{head["es"]} -> {head["ca"]}')
        kept.append(head)

    # Flat decks, unit by unit, words before phrases within a unit.
    #
    # Inside the extra-vocabulary pool (unit 99) entries are ordered
    # alphabetically across *all* sources rather than source by source. Without
    # this, every external list would land as its own block and you would feel
    # the seam between them; sorted together they interleave and read as one
    # body of vocabulary.
    def within_unit(e: dict) -> str:
        return sort_key(e["ca"]) if e["unit"] == 99 else ""

    groups: dict[tuple, list[dict]] = {}
    for e in sorted(kept, key=lambda x: (x["sort"], within_unit(x))):
        groups.setdefault((e["sort"], e["unit"], e["kind"]), []).append(e)

    decks: list[tuple[str, genanki.Deck]] = []
    n = 0
    for (_, unit, kind), items in sorted(groups.items()):
        title = UNIT_TITLES.get(unit, "vocabulari extra")
        label = KIND_LABEL.get(kind, kind)
        chunks = [items[i:i + args.max] for i in range(0, len(items), args.max)]
        for ci, chunk in enumerate(chunks):
            n += 1
            if want_decks is not None and n not in want_decks:
                continue
            suffix = f" ({ci + 1}/{len(chunks)})" if len(chunks) > 1 else ""
            name = f"CA · {n:02d} {label} · {title}{suffix}"
            deck = genanki.Deck(DECK_BASE + n, name)
            locator = f"{n:02d} · {label}"
            for e in chunk:
                deck.add_note(genanki.Note(
                    model=MODEL,
                    fields=[e["es"], e["ca"], e["so"],
                            html.escape(e["example"]) if e["example"] else "",
                            locator, e["source"]],
                    # Identity is the Catalan word alone. genanki's default guid
                    # hashes *every* field, including the deck locator, so adding
                    # vocabulary would re-chunk the decks, change the locator, and
                    # re-import the same words as brand-new duplicates. Keying on
                    # the headword means a card keeps its review history no matter
                    # how the decks are later reorganised.
                    guid=genanki.guid_for(e["ca"]),
                    tags=["ca-a1", f"deck{n:02d}", kind],
                ))
            decks.append((name, deck))

    if not decks:
        sys.exit("[FATAL] nothing selected")

    # The Spanish gloss is the front of the card and Anki's duplicate key. Two
    # different Catalan words sharing one gloss make a card with no single right
    # answer, so they are reported rather than shipped silently.
    fronts: dict[str, list[str]] = {}
    for _, d in decks:
        for nt in d.notes:
            fronts.setdefault(nt.fields[0].strip().lower(), []).append(nt.fields[1])
    ambiguous = {k: v for k, v in fronts.items() if len(set(v)) > 1}
    if ambiguous:
        print(f"[WARN] {len(ambiguous)} Spanish prompts still map to more than one Catalan word")
        print("       (these span different decks, so merging did not catch them):")
        for k, v in list(ambiguous.items())[:12]:
            print(f"         {k!r} -> {sorted(set(v))}")
        print()
    if merged:
        print(f"[merged] {len(merged)} synonym pairs share one card:")
        for m in merged[:12]:
            print(f"         {m}")
        print()

    genanki.Package([d for _, d in decks]).write_to_file(str(args.out))

    total = sum(len(d.notes) for _, d in decks)
    with_so = sum(1 for _, d in decks for nt in d.notes if nt.fields[2])
    print(f"[DONE] {args.out}")
    print(f"  {total} notes in {len(decks)} flat decks (1 card each, ES -> CA)")
    print(f"  {skipped_cognate} cognates skipped (kept in the TSV)")
    print(f"  {dropped} dropped and {reglossed} reglossed via content/overrides.tsv")
    print(f"  {with_so} cards carry a pronunciation hint")
    print()
    for name, d in decks:
        print(f"    {name:<46} {len(d.notes):>4}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
