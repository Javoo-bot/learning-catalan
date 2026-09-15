"""Stage 1 QA: check the Markdown archive before anything is derived from it.

Two classes of finding:

  FAIL  -- the page is unusable and must be re-transcribed (missing file,
           no frontmatter, refusal text, unreplaced prompt placeholders, or
           a folio that disagrees with the page we actually sent).
  WARN  -- worth a human glance but often legitimate: a short body is normal
           for a full-bleed photo page, and a page with no accented character
           is possible though rare in Catalan.

Exit code is non-zero only when there is at least one FAIL, so this is safe
to wire into a build step.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MD_DIR = ROOT / "libros" / "md"
WEB_DIR = ROOT / "libros" / "pages" / "web"

SHORT_BODY = 200
DIACRITICS = "àèéíïòóúüçÀÈÉÍÏÒÓÚÜÇ·"

# Section dividers carrying artwork but no text at all. Confirmed by eye
# against libros/pages/web/, so an empty body here is correct, not a failure.
TEXTLESS_PAGES = {188, 208}

# A complete transcription normally ends on a sentence, a table row, a list
# item, or the printed folio. Ending on a bare word usually means the model
# stopped early -- that is how the truncation of p142 was caught.
TERMINAL = tuple('.!?…:;|)]»*_' + '"' + "'")

# Text that means the model talked to us instead of transcribing the page.
REFUSAL = re.compile(
    r"(i'm sorry|i am sorry|i cannot|i can't|unable to (?:process|read|assist)"
    r"|as an ai|i'm not able to)",
    re.I,
)
# Prompt scaffolding that leaked into the output instead of being filled in.
PLACEHOLDER = re.compile(r"<the page number|<unit number|<any of:|<the banner")

FM_RE = re.compile(r"\A---\s*\n(.*?)\n---\s*\n", re.S)


def parse_front_matter(text: str) -> tuple[dict, str]:
    m = FM_RE.match(text)
    if not m:
        return {}, text
    fm = {}
    for line in m.group(1).splitlines():
        if ":" not in line:
            continue
        k, v = line.split(":", 1)
        fm[k.strip()] = v.strip().strip('"')
    return fm, text[m.end():]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dir", type=Path, default=MD_DIR)
    ap.add_argument("--quiet", action="store_true", help="only print problems")
    args = ap.parse_args()

    expected = sorted(int(p.stem[1:]) for p in WEB_DIR.glob("p*.jpg"))
    if not expected:
        sys.exit(f"[FATAL] no page images in {WEB_DIR} -- run extract_pages.py first")

    fails: list[str] = []
    warns: list[str] = []
    units: dict[str, int] = {}
    total_chars = 0
    seen = 0

    for page in expected:
        path = args.dir / f"p{page:03d}.md"
        if not path.exists():
            fails.append(f"p{page:03d}  MISSING")
            continue

        seen += 1
        raw = path.read_text(encoding="utf-8")
        fm, body = parse_front_matter(raw)
        body = body.strip()
        total_chars += len(body)

        if not fm:
            fails.append(f"p{page:03d}  no frontmatter")
            continue
        if fm.get("folio_ok") == "false":
            fails.append(f"p{page:03d}  folio mismatch: model read {fm.get('folio_read')}")
        if REFUSAL.search(body):
            fails.append(f"p{page:03d}  refusal / model commentary in body")
        if PLACEHOLDER.search(raw):
            fails.append(f"p{page:03d}  unreplaced prompt placeholder")
        if not body:
            if page in TEXTLESS_PAGES:
                continue
            fails.append(f"p{page:03d}  empty body")
            continue

        if len(body) < SHORT_BODY:
            warns.append(f"p{page:03d}  short body ({len(body)} chars) -- photo page?")
        last = body.rstrip().splitlines()[-1].rstrip() if body.strip() else ""
        # A trailing hyphen is the book's own mid-word page break, so it is fine.
        if (last
                and not last.endswith(TERMINAL)
                and not last.endswith("-")
                and str(page) not in body[-90:]):
            warns.append(f"p{page:03d}  may be truncated -- ends: ...{last[-48:]!r}")
        if not any(c in body for c in DIACRITICS):
            warns.append(f"p{page:03d}  no Catalan diacritics")

        unit = fm.get("unit", "null")
        units[unit] = units.get(unit, 0) + 1

    if not args.quiet:
        print(f"pages expected : {len(expected)}")
        print(f"pages present  : {seen}")
        print(f"total chars    : {total_chars:,}")
        if seen:
            print(f"mean body      : {total_chars // seen:,} chars")
        print("units seen     : " + ", ".join(
            f"{k}={v}" for k, v in sorted(units.items(), key=lambda kv: (kv[0] == "null", kv[0]))
        ))
        print()

    for w in warns:
        print(f"[WARN] {w}")
    for f in fails:
        print(f"[FAIL] {f}")

    print()
    print(f"{len(fails)} fail | {len(warns)} warn")
    if fails:
        pages = sorted({m.group(1) for m in (re.match(r"p(\d+)", x) for x in fails) if m})
        print("re-run with: python scripts/ocr_pages.py --force --pages " +
              ",".join(str(int(p)) for p in pages))
        return 1
    print("OK -- archive is usable")
    return 0


if __name__ == "__main__":
    sys.exit(main())
