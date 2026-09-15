"""Concatenate libros/md/pNNN.md into one searchable libros/book.md.

The per-page files stay the source of truth; this is a convenience view for
reading a whole unit at once or grepping across the book. It also prints the
page->unit map, which is what tells you which pages to curate for a unit.
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MD_DIR = ROOT / "libros" / "md"
OUT = ROOT / "libros" / "book.md"

FM_RE = re.compile(r"\A---\s*\n(.*?)\n---\s*\n", re.S)

UNIT_TITLES = {
    "0": "Domini.cat",
    "1": "Tot un món",
    "2": "Família, amics i coneguts",
    "3": "Les coses de cada dia",
    "4": "Com a casa, enlloc",
    "5": "Històries de vida",
    "6": "Menjar-se el món",
    "7": "Fets i gent",
    "8": "Temps de canvis",
    "9": "Fem les maletes!",
    "10": "Tenir cura de la salut",
    "11": "Feines de tota mena",
    "12": "I si sortim?",
}


# The book's layout is strictly regular: unit 0 runs pp. 14-19, then every
# numbered unit occupies exactly 14 pages starting at p. 20. Everything from
# p. 188 on is reference matter (resum gramatical, then transcripcions), and
# those pages carry "UNITAT N" headers that point back at the course units --
# which is why unit membership is derived from the page number, not the header.
UNIT0 = range(14, 20)
UNIT_START, UNIT_LEN, LAST_UNIT = 20, 14, 12
BODY_END = 187
BACK_MATTER = range(188, 228)
SECTIONS = {"resum gramatical": range(189, 208), "transcripcions": range(209, 228)}


def unit_of(page: int) -> int | None:
    """Course unit a body page belongs to, or None for front/back matter."""
    if page in UNIT0:
        return 0
    if UNIT_START <= page <= BODY_END:
        unit = (page - UNIT_START) // UNIT_LEN + 1
        return unit if unit <= LAST_UNIT else None
    return None


def unit_range(unit: int) -> range:
    if unit == 0:
        return UNIT0
    start = UNIT_START + (unit - 1) * UNIT_LEN
    return range(start, start + UNIT_LEN)


def parse(text: str) -> tuple[dict, str]:
    m = FM_RE.match(text)
    if not m:
        return {}, text
    fm = {}
    for line in m.group(1).splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            fm[k.strip()] = v.strip().strip('"')
    return fm, text[m.end():]


def main() -> None:
    pages = sorted(MD_DIR.glob("p*.md"), key=lambda p: int(p.stem[1:]))
    if not pages:
        raise SystemExit(f"no pages in {MD_DIR}")

    parts: list[str] = [
        "# A Punt A1+ A2 — curs de català",
        "",
        "Transcription of the scanned coursebook. Catalan is verbatim from the",
        "page; see `docs/TRANSCRIPTION.md` for how it was produced.",
        "",
        "Headings below carry the printed book page, so `p. 142` here is p. 142",
        "in the paper book.",
        "",
        "---",
        "",
    ]

    mismatches: list[str] = []

    for path in pages:
        page = int(path.stem[1:])
        fm, body = parse(path.read_text(encoding="utf-8"))
        body = body.strip()

        unit = unit_of(page)
        # The back matter repeats "UNITAT N" headers that point back at the
        # course units, so only trust the model's reading inside the body.
        declared = fm.get("unit")
        if (unit is not None and declared not in (None, "null", "")
                and declared != str(unit) and page not in BACK_MATTER):
            mismatches.append(f"p{page}: layout says unit {unit}, page header says {declared}")

        section = fm.get("section")
        label = f"p. {page}"
        if section and section != "null":
            label += f" — {section}"
        if unit:
            label += f"  ·  unitat {unit}"

        parts.append(f"## {label}")
        parts.append("")
        parts.append(body if body else "*(no text on this page)*")
        parts.append("")

    OUT.write_text("\n".join(parts), encoding="utf-8")
    size = OUT.stat().st_size

    print(f"[DONE] {len(pages)} pages -> {OUT} ({size:,} bytes)")
    print()
    print("page ranges by unit (use these to curate content/unit-NN.tsv):")
    for unit in range(0, LAST_UNIT + 1):
        r = unit_range(unit)
        title = UNIT_TITLES.get(str(unit), "?")
        print(f"  unit {unit:>2} {title:<28} pp. {r.start}-{r.stop - 1}")
    for name, r in SECTIONS.items():
        print(f"  {'':>7} {name:<28} pp. {r.start}-{r.stop - 1}")
    print()
    if mismatches:
        print(f"[WARN] {len(mismatches)} page(s) whose header disagrees with the layout:")
        for m in mismatches:
            print(f"  {m}")
    else:
        print("[OK] every body page's printed UNITAT header matches the layout")


if __name__ == "__main__":
    main()
