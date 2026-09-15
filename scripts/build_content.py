"""Stage 2 QA: check content/unit-NN.tsv against the Markdown archive.

The important check here is `--verify`: for every row marked `verbatim`, the
Catalan string must literally occur on the book page it cites. That turns the
provenance claim into something a machine re-checks on demand, rather than
something you have to take on trust.

Rows marked `derived` are exempt -- those are forms completed from a pattern
the book prints but leaves blank as an exercise (e.g. the number 19 in the
numerals table on p. 26). They are listed separately so they stay visible.

    python scripts/build_content.py --check     structure only
    python scripts/build_content.py --verify    structure + provenance
"""
from __future__ import annotations

import argparse
import re
import sys
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONTENT = ROOT / "content"
MD_DIR = ROOT / "libros" / "md"

COLUMNS = [
    "ca", "es", "so", "kind", "unit", "section", "topic",
    "scenario", "example_ca", "source_page", "gloss_by", "confidence",
]
KINDS = {"mot", "frase"}
# verbatim -- the string occurs on the cited page exactly as written
# lemma    -- dictionary citation form of a word the page does print; the
#             article and singular were added so the card teaches gender
#             ("el nom" where p. 28 prints "Els noms més posats")
# derived  -- a form the book leaves blank as an exercise but whose pattern it
#             prints (e.g. 19 in the numerals table on p. 26)
CONFIDENCE = {"verbatim", "lemma", "derived"}
MAX_PAGE = 227

ARTICLES = ("el ", "la ", "els ", "les ", "l'", "un ", "una ")

FM_RE = re.compile(r"\A---\s*\n.*?\n---\s*\n", re.S)


def normalise(s: str) -> str:
    """Fold the differences that are noise when matching against the scan.

    Curly and straight apostrophes, non-breaking spaces, and the many dash
    shapes all vary between the book and a transcription; case does too, since
    the book sets illustration labels in caps.
    """
    s = unicodedata.normalize("NFC", s)
    for a, b in (("’", "'"), ("‘", "'"), (" ", " "),
                 ("–", "-"), ("—", "-"), ("‑", "-"),
                 ("“", '"'), ("”", '"'), ("«", '"'), ("»", '"')):
        s = s.replace(a, b)
    s = re.sub(r"\s+", " ", s)
    return s.strip().lower()


def head_word(ca: str) -> str:
    """Drop a leading article, so "el nom" can be matched against "els noms"."""
    s = normalise(ca)
    for art in ARTICLES:
        if s.startswith(art):
            return s[len(art):].strip()
    return s


def fold(s: str) -> str:
    """Drop accents, so llengua can be matched against llengues/llengues."""
    return "".join(c for c in unicodedata.normalize("NFD", s)
                   if not unicodedata.combining(c))


def attested(ca: str, text: str) -> bool:
    """Is the head word on the page, allowing the book's plural or feminine?"""
    head = head_word(ca)
    if not head:
        return False
    # Accents shift between singular and plural (llengua -> llengues), so the
    # whole comparison is also tried with accents folded away.
    if fold(head) in fold(text):
        return True
    # Feminine plural in -a -> -es: nina/nines, xiqueta/xiquetes.
    if head.endswith("a") and fold(head[:-1] + "es") in fold(text):
        return True
    if head in text:
        return True
    # The book often prints the plural ("nins i nines") where the card gives
    # the singular, or the feminine where the card gives a bare stem.
    for suffix in ("s", "es", "ns", "ns "):
        if f"{head}{suffix}" in text:
            return True
    # ...and sometimes the singular where the card gives a plural.
    for suffix in ("es", "s"):
        if head.endswith(suffix) and head[: -len(suffix)] in text:
            return True
    # Catalan plurals in -a -> -es also shift the stem: nina/nines,
    # xiqueta/xiquetes, llengua/llengues, catala/catalans. Matching on the
    # stem minus its final letter covers those without hand-listing them.
    # Guarded at 4 characters so short words cannot match by accident.
    if len(head) >= 5 and head[:-1] in text:
        return True
    return False


_page_cache: dict[int, str] = {}


def page_text(page: int) -> str:
    if page not in _page_cache:
        path = MD_DIR / f"p{page:03d}.md"
        raw = path.read_text(encoding="utf-8") if path.exists() else ""
        # Strip markdown emphasis so "**em dic** Anna" matches "em dic Anna".
        body = FM_RE.sub("", raw).replace("*", "").replace("_", "")
        _page_cache[page] = normalise(body)
    return _page_cache[page]


def load(path: Path) -> tuple[list[dict], list[str]]:
    errors: list[str] = []
    lines = path.read_text(encoding="utf-8").splitlines()
    if not lines:
        return [], [f"{path.name}: empty file"]

    header = lines[0].split("\t")
    if header != COLUMNS:
        return [], [f"{path.name}: header is {header}, expected {COLUMNS}"]

    rows = []
    for i, line in enumerate(lines[1:], start=2):
        if not line.strip():
            continue
        cells = line.split("\t")
        if len(cells) != len(COLUMNS):
            errors.append(f"{path.name}:{i}: {len(cells)} columns, expected {len(COLUMNS)}")
            continue
        row = dict(zip(COLUMNS, cells))
        row["_file"] = path.name
        row["_line"] = i
        rows.append(row)
    return rows, errors


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--check", action="store_true", help="structural checks (default)")
    ap.add_argument("--verify", action="store_true",
                    help="also confirm every verbatim row appears on its cited page")
    args = ap.parse_args()

    scen_path = CONTENT / "scenarios.tsv"
    if not scen_path.exists():
        sys.exit(f"[FATAL] missing {scen_path}")
    scenarios = {
        l.split("\t")[0]
        for l in scen_path.read_text(encoding="utf-8").splitlines()[1:] if l.strip()
    }

    files = sorted(CONTENT.glob("unit-*.tsv"))
    if not files:
        sys.exit(f"[FATAL] no unit-*.tsv in {CONTENT}")

    errors: list[str] = []
    unverified: list[str] = []
    derived: list[str] = []
    lemmas: list[str] = []
    rows: list[dict] = []

    for path in files:
        got, errs = load(path)
        errors.extend(errs)
        rows.extend(got)

    seen: dict[tuple[str, str, str], str] = {}
    for r in rows:
        where = f"{r['_file']}:{r['_line']}"
        expect_unit = re.search(r"unit-(\d+)", r["_file"]).group(1).lstrip("0") or "0"

        if not r["ca"].strip():
            errors.append(f"{where}: empty ca")
        if not r["es"].strip():
            errors.append(f"{where}: empty es ({r['ca']})")
        if r["kind"] not in KINDS:
            errors.append(f"{where}: kind {r['kind']!r} not in {sorted(KINDS)}")
        if r["confidence"] not in CONFIDENCE:
            errors.append(f"{where}: confidence {r['confidence']!r} not in {sorted(CONFIDENCE)}")
        if r["unit"] != expect_unit:
            errors.append(f"{where}: unit {r['unit']!r} but file says {expect_unit}")
        if r["scenario"] not in scenarios:
            errors.append(f"{where}: unknown scenario {r['scenario']!r}")
        if not r["source_page"].isdigit() or not 1 <= int(r["source_page"]) <= MAX_PAGE:
            errors.append(f"{where}: bad source_page {r['source_page']!r}")

        key = (normalise(r["ca"]), r["unit"], r["kind"])
        if key in seen:
            errors.append(f"{where}: duplicate of {seen[key]} -- {r['ca']!r}")
        else:
            seen[key] = where

        if r["kind"] == "frase" and r["confidence"] == "lemma":
            errors.append(f"{where}: a frase must be verbatim, not a lemma -- {r['ca']!r}")

        if args.verify and r["source_page"].isdigit():
            page = int(r["source_page"])
            text = page_text(page)
            conf = r["confidence"]
            if conf == "derived":
                derived.append(f"{where}  p{page}  {r['ca']}")
            elif conf == "lemma":
                if attested(r["ca"], text):
                    lemmas.append(where)
                else:
                    unverified.append(f"{where}  p{page}  {r['ca']!r}  (head word not on page)")
            elif normalise(r["ca"]) not in text:
                unverified.append(f"{where}  p{page}  {r['ca']!r}")

    by_kind: dict[str, int] = {}
    by_unit: dict[str, int] = {}
    for r in rows:
        by_kind[r["kind"]] = by_kind.get(r["kind"], 0) + 1
        by_unit[r["unit"]] = by_unit.get(r["unit"], 0) + 1

    print(f"files   : {len(files)}")
    print(f"entries : {len(rows)}  (" + ", ".join(f"{k}={v}" for k, v in sorted(by_kind.items())) + ")")
    print("by unit : " + ", ".join(f"u{k}={v}" for k, v in sorted(by_unit.items(), key=lambda kv: int(kv[0]))))
    print()

    if args.verify:
        exact = len(rows) - len(derived) - len(lemmas) - len(unverified)
        print(f"provenance: {exact} verbatim rows found on their cited page")
        print(f"            {len(lemmas)} lemma rows whose head word is on their cited page")
        if derived:
            print(f"            {len(derived)} row(s) marked 'derived' (exempt, completed from a printed pattern):")
            for d in derived:
                print(f"              {d}")
        print()
        for u in unverified:
            print(f"[UNVERIFIED] {u}")

    for e in errors:
        print(f"[ERROR] {e}")

    print()
    bad = len(errors) + len(unverified)
    print(f"{len(errors)} error | {len(unverified)} unverified")
    if bad:
        return 1
    print("OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
