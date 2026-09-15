"""Stage 0: A Punt PDF -> upright page JPEGs.

The scan has no text layer: exactly one JPEG per PDF page, stored sideways
(every page carries /Rotate 90). We undo that rotation once, here, so every
later stage sees an upright page.

Page numbering: filenames use the PDF index (1-based). The printed book page
is index + 1 -- verified against the folios on pp. 21/24/30/31/34/47/214/222/
225/227.

Idempotent: existing outputs are skipped, so re-running is free.
"""
from __future__ import annotations

import argparse
import io
import sys
from pathlib import Path

import pypdf
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
PDF = ROOT / "libros" / "A Punt A1+ A2 curs de català.pdf"
PAGES_DIR = ROOT / "libros" / "pages"
WEB_DIR = PAGES_DIR / "web"

WEB_LONG_EDGE = 2000  # long edge sent to the vision API
FULL_QUALITY = 92
WEB_QUALITY = 88


def book_page(pdf_index0: int) -> int:
    """Printed folio for a 0-based PDF index.

    Verified against the printed folios on PDF indices 20/23/29/30/33/46/
    213/221/224/226 -> pages 21/24/30/31/34/47/214/222/225/227.
    Filenames are 1-based, so the number in pNNN.jpg *is* the book page.
    """
    return pdf_index0 + 1


def extract(pdf_path: Path, force: bool = False) -> int:
    if not pdf_path.exists():
        sys.exit(f"[FATAL] PDF not found: {pdf_path}")

    PAGES_DIR.mkdir(parents=True, exist_ok=True)
    WEB_DIR.mkdir(parents=True, exist_ok=True)

    reader = pypdf.PdfReader(str(pdf_path))
    total = len(reader.pages)
    written = skipped = 0

    for i, page in enumerate(reader.pages):
        num = i + 1
        full_path = PAGES_DIR / f"p{num:03d}.jpg"
        web_path = WEB_DIR / f"p{num:03d}.jpg"

        if not force and full_path.exists() and web_path.exists():
            skipped += 1
            continue

        images = list(page.images)
        if not images:
            print(f"[WARN] page {num}: no embedded image, skipping")
            continue
        if len(images) > 1:
            print(f"[WARN] page {num}: {len(images)} embedded images, using the first")

        rotate = int(page.get("/Rotate", 0) or 0)
        im = Image.open(io.BytesIO(images[0].data))
        if im.mode != "RGB":
            im = im.convert("RGB")
        if rotate:
            # PIL rotates counter-clockwise; the PDF asks for a clockwise turn.
            im = im.rotate(-rotate, expand=True)

        im.save(full_path, "JPEG", quality=FULL_QUALITY)

        web = im.copy()
        web.thumbnail((WEB_LONG_EDGE, WEB_LONG_EDGE), Image.LANCZOS)
        web.save(web_path, "JPEG", quality=WEB_QUALITY)

        written += 1
        if written % 25 == 0:
            print(f"  ... {written} written ({num}/{total})")

    print(f"[DONE] {total} pages | written {written} | skipped {skipped}")
    print(f"       full: {PAGES_DIR}")
    print(f"       web:  {WEB_DIR}")
    return total


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--force", action="store_true", help="re-extract pages that already exist")
    ap.add_argument("--pdf", type=Path, default=PDF)
    args = ap.parse_args()
    extract(args.pdf, force=args.force)
