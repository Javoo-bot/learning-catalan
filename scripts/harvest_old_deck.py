"""Pull the usable vocabulary out of the original catalan_deck.apkg.

That deck was built before any of this: it makes two cards per note (CA->ES as
well as ES->CA), it reviews words that are identical in Spanish, and it carries
43 MB of photographs. Roughly 77% of its words appear nowhere else though, so
the words are worth keeping even though the deck is not.

This takes the vocabulary out and leaves the packaging behind. Output lands in
the same shape as the other external sources, so the normal pipeline applies:
cognates are filtered, only ES -> CA is generated, and the entries mix in with
everything else rather than sitting in a block of their own.

The cloze notes go to a separate file. They are fill-in-the-blank sentences,
which do not fit an ES -> CA card, but they are the right raw material for the
sentences tier later on.

    python scripts/harvest_old_deck.py
"""
from __future__ import annotations

import argparse
import html
import json
import re
import sqlite3
import sys
import tempfile
import unicodedata
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
APKG = ROOT / "catalan_deck.apkg"
OUT = ROOT / "content/sources/catalan-deck.glossed.tsv"
OUT_CLOZE = ROOT / "content/sources/catalan-deck-cloze.tsv"

# Same header the other external sources use, so build_a1a2_deck picks it up
# with no special cases.
COLUMNS = ["ca", "es", "so", "en", "kind", "risk", "ca_suggested", "issue", "flag", "source"]


def clean(s: str) -> str:
    s = re.sub(r"<[^>]+>", " ", html.unescape(s))
    s = s.replace("’", "'").replace(" ", " ")
    return re.sub(r"\s+", " ", s).strip()


def norm(s: str) -> str:
    s = unicodedata.normalize("NFC", s.lower().strip())
    s = re.sub(r"^(el |la |els |les |l'|un |una )", "", s)
    return re.sub(r"\s+", " ", s)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--apkg", type=Path, default=APKG)
    args = ap.parse_args()

    if not args.apkg.exists():
        sys.exit(f"[FATAL] {args.apkg} not found")

    z = zipfile.ZipFile(args.apkg)
    name = "collection.anki21" if "collection.anki21" in z.namelist() else "collection.anki2"
    tmp = tempfile.mkdtemp()
    z.extract(name, tmp)
    db = sqlite3.connect(Path(tmp) / name)
    models = json.loads(db.execute("select models from col").fetchone()[0])

    vocab: list[tuple[str, str, str]] = []
    cloze: list[tuple[str, str, str]] = []
    for mid, flds in db.execute("select mid, flds from notes"):
        parts = [clean(p) for p in flds.split("\x1f")]
        model = models.get(str(mid), {}).get("name", "")
        if "Cloze" in model:
            # Text, Notes, CategoryImage, Category
            cloze.append((parts[0], parts[1] if len(parts) > 1 else "",
                          parts[3] if len(parts) > 3 else ""))
        else:
            # Catalan, Spanish, Image, CategoryImage, Credit, Category
            ca, es = parts[0], parts[1] if len(parts) > 1 else ""
            cat = parts[5] if len(parts) > 5 else ""
            if ca and es:
                vocab.append((ca, es, cat))

    # What the new content already covers, so nothing is emitted twice.
    have: set[str] = set()
    for f in sorted((ROOT / "content").glob("unit-*.tsv")) + \
             sorted((ROOT / "content/sources").glob("*.glossed.tsv")):
        if f.resolve() == OUT.resolve():
            continue
        for line in f.read_text(encoding="utf-8").splitlines()[1:]:
            if line.strip():
                have.add(norm(line.split("\t")[0]))

    rows, skipped_dupe, seen = [], 0, set()
    for ca, es, cat in sorted(vocab, key=lambda v: norm(v[0])):
        key = norm(ca)
        if key in have or key in seen:
            skipped_dupe += 1
            continue
        seen.add(key)
        kind = "frase" if " " in ca.strip() else "mot"
        rows.append([ca, es, "", "", kind, "", "", "", cat, "catalan-deck"])

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(["\t".join(COLUMNS)] + ["\t".join(r) for r in rows]) + "\n",
                   encoding="utf-8")

    OUT_CLOZE.write_text(
        "\n".join(["text\tnotes\tcategory"] +
                  ["\t".join(c) for c in sorted(cloze, key=lambda c: c[0])]) + "\n",
        encoding="utf-8")

    n_mot = sum(1 for r in rows if r[4] == "mot")
    print(f"[DONE] {len(vocab)} vocab notes in the old deck")
    print(f"       {skipped_dupe} already covered elsewhere, skipped")
    print(f"       {len(rows)} harvested -> {OUT.name}  ({n_mot} mots, {len(rows)-n_mot} frases)")
    print(f"       {len(cloze)} cloze notes parked -> {OUT_CLOZE.name} (for the sentences tier)")
    print("\nNext: python scripts/add_sound.py content/sources/catalan-deck.glossed.tsv")
    return 0


if __name__ == "__main__":
    sys.exit(main())
