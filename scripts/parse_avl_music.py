"""Parse the AVL "Vocabulari de la musica" glossary into ca -> es pairs.

Source: Academia Valenciana de la Llengua, an official terminology body. The
Catalan is normative and, unusually for this project, the Spanish equivalent
comes from the source itself instead of being produced by a model. Entry shape
in the scraped PDF text:

    **cant coral** *m.* Cant interpretat per un grup de veus.
    **-***cast.* canto coral.
    **-** *angl.* choral singing.

Everything parseable is written out. Choosing which terms are worth learning is
a separate, human decision -- the glossary has ~3000 entries covering organ pipe
parts and medieval notation, and dumping those into a deck would bury the words
a chorister actually needs.

    python scripts/parse_avl_music.py <scraped.txt>
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "content/sources/avl-musica-full.tsv"

POS = r"m\.|f\.|adj\.|v\.|m\. i f\.|adv\.|loc\.|f\. pl\.|m\. pl\.|interj\."

ENTRY = re.compile(
    r"\*\*(?P<ca>[^*\n]{2,60}?)\*\*\s*\*(?P<pos>" + POS + r")\*"
    r"(?P<body>.*?)(?=\*\*[^*\n]{2,60}?\*\*\s*\*(?:" + POS + r")\*|\Z)",
    re.S,
)
CAST = re.compile(r"\*cast\.\*\s*(?P<es>[^\n]+)")


def clean_es(raw: str) -> str:
    """Strip the PDF's line-break debris out of a Spanish equivalent.

    The scraped text keeps literal backslash-n sequences, and the next line
    ("angl. ...") often bleeds into the capture, leaving tails like "ngl.".
    """
    es = raw
    es = re.sub(r"\\+n", " ", es)            # literal \n sequences
    es = re.sub(r"[|•]", " ", es)
    es = re.sub(r"\ba?ngl\.?.*$", "", es)    # the English line, if it bled in
    es = re.sub(r"^\s*\*\*\d+\.?\*\*\s*", "", es)
    es = re.sub(r"\s*\*\*\d+\.?\*\*\s*", " / ", es)
    es = re.sub(r"\*+", "", es)
    es = re.sub(r"\s+", " ", es)
    return es.strip(" ./,;:-")


def main() -> int:
    if len(sys.argv) < 2:
        sys.exit("usage: parse_avl_music.py <scraped.txt>")
    raw = Path(sys.argv[1]).read_text(encoding="utf-8")

    text = raw.replace("\\n", "\n")
    text = re.sub(r"(\w)-\s*\n\s*(\w)", r"\1\2", text)        # de-hyphenate
    text = re.sub(r"\n\s*(MUSICA|MÚSICA|LA|DE|VOCABULARI)\s*\n", "\n", text)
    text = re.sub(r"[ \t]+", " ", text)

    rows, seen = [], set()
    total = 0
    for m in ENTRY.finditer(text):
        total += 1
        ca = re.sub(r"\s+", " ", m.group("ca")).strip(" .,")
        cm = CAST.search(m.group("body"))
        if not ca or not cm:
            continue
        es = clean_es(cm.group("es"))
        if not es or len(ca) > 46 or len(es) > 70:
            continue
        if re.search(r"\d", ca) or ca.lower() in seen:
            continue
        seen.add(ca.lower())
        rows.append((ca, es, m.group("pos").rstrip(".")))

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", encoding="utf-8", newline="") as fh:
        fh.write("ca\tes\tpos\n")
        for ca, es, pos in sorted(rows, key=lambda r: r[0].lower()):
            fh.write(f"{ca}\t{es}\t{pos}\n")

    print(f"[DONE] {total} entries seen, {len(rows)} parsed -> {OUT}")
    print("       This is the reference glossary. Pick from it deliberately;")
    print("       do not card all of it.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
