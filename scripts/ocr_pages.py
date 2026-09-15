"""Stage 1: page JPEGs -> faithful Markdown, via an OpenRouter vision model.

The Markdown archive under libros/md/ is the durable artefact: everything
later (Anki decks, exam revision) is derived from it, so this stage aims for
a faithful transcription rather than a summary.

Caching follows the same discipline as fetch_image() in build_deck.py: check
disk first, only missing pages hit the network. The run is resumable -- an
interrupted run loses only the pages in flight.

Self-check: the model is asked to report the folio printed on the page. We
know independently what it should be (the filename), so a mismatch is a
strong signal the page was misread. Recorded as `folio_ok` in frontmatter.
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import re
import sys
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock

ROOT = Path(__file__).resolve().parent.parent
WEB_DIR = ROOT / "libros" / "pages" / "web"
MD_DIR = ROOT / "libros" / "md"

DEFAULT_MODEL = "google/gemini-2.5-pro"  # chosen by bake-off; see docs/TRANSCRIPTION.md

PROMPT = """You are transcribing one page of "A Punt A1+ A2", a Catalan language coursebook, into Markdown.

This is an ARCHIVAL TRANSCRIPTION, not a summary. A learner will study from your output instead of the page, so nothing may be lost, added, or paraphrased.

Rules:
1. Transcribe ALL text on the page, in reading order, top to bottom.
2. Reproduce Catalan orthography EXACTLY, including accents and the punt volat in l.l ligatures.
3. NEVER invent, complete, correct, or translate anything. If the book has a typo, keep it. If text is illegible, write [?].
4. Blank answer lines or empty boxes a student would fill in: write ___ (three underscores). Do not guess answers.
5. Render tables (verb conjugations, grammar boxes) as Markdown tables, preserving every cell.
6. Keep the book's own section banners as headings: PUNT DE PARTIDA, PUNT 1/2/3, PUNT DE SUPORT, GRAMATICA, LEXIC, FONETICA, CULTURA, TASCA INDIVIDUAL, TASCA FINAL, TRANSCRIPCIONS (use the book's real accented spelling).
7. Preserve audio-track markers exactly as they appear, e.g. (PISTA 10).
8. Transcribe words that label illustrations, photos or diagrams. If a picture has NO label, write nothing for it.
9. Exercise instructions and numbering (A., B., 1., 2.) are content: keep them.
10. Matching exercises with two facing columns: render as a Markdown table with a left and a right column, preserving each side's original order. Do not pair them up yourself.
11. When the page is laid out in two columns (common on PUNT DE SUPORT pages), transcribe the ENTIRE left column first, top to bottom, then the entire right column. Do not interleave them.
12. Where a table cell is merged across several rows, repeat its value in every row it covers rather than leaving the other rows blank.
13. Add bold or italic ONLY where the page actually prints it. Never add emphasis of your own.

Begin your output with exactly this metadata block, then the transcription:

---
folio: <the page number printed on the page, digits only; if none, null>
unit: <unit number printed in the header, digits only; 0 for Domini.cat; null if none>
section: <the banner in the top corner, verbatim, or null>
types: [<any of: lexic, gramatica, fonetica, cultura, tasca, transcripcio, activitats, portada, index>]
---

Then the Markdown transcription. No commentary, and no code fences around the whole output."""


_print_lock = Lock()


def log(msg: str) -> None:
    with _print_lock:
        print(msg, flush=True)


def load_env() -> None:
    """Read .env into os.environ without clobbering the real environment."""
    env = ROOT / ".env"
    if not env.exists():
        return
    for line in env.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, val = line.split("=", 1)
        os.environ.setdefault(key.strip(), val.strip().strip('"').strip("'"))


def call_model(img_b64: str, model: str, api_key: str, base: str, timeout: int = 240) -> str:
    body = json.dumps({
        "model": model,
        "temperature": 0,
        "messages": [{
            "role": "user",
            "content": [
                {"type": "text", "text": PROMPT},
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{img_b64}"}},
            ],
        }],
    }).encode("utf-8")

    req = urllib.request.Request(
        base.rstrip("/") + "/chat/completions",
        data=body,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "X-Title": "a-punt-transcription",
        },
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data = json.loads(resp.read().decode("utf-8"))

    if "choices" not in data:
        raise RuntimeError(f"no choices in response: {str(data)[:300]}")
    return (data["choices"][0]["message"].get("content") or "").strip()


META_RE = re.compile(r"\A---\s*\n(.*?)\n---\s*\n?", re.S)


def split_meta(raw: str) -> tuple[dict, str]:
    """Pull the model's leading metadata block off the transcription."""
    raw = raw.strip()
    if raw.startswith("```"):
        raw = re.sub(r"\A```[a-z]*\s*\n", "", raw)
        raw = re.sub(r"\n```\s*\Z", "", raw)
    m = META_RE.match(raw)
    if not m:
        return {}, raw
    meta: dict = {}
    for line in m.group(1).splitlines():
        if ":" not in line:
            continue
        k, v = line.split(":", 1)
        v = v.strip()
        meta[k.strip()] = None if v in ("null", "", "None") else v
    return meta, raw[m.end():].strip()


def yaml_scalar(v) -> str:
    if v is None:
        return "null"
    s = str(v)
    if s.startswith("[") or re.fullmatch(r"-?\d+", s) or s in ("true", "false"):
        return s
    return '"' + s.replace('"', '\\"') + '"'


def transcribe(page: int, model: str, api_key: str, base: str, out_dir: Path,
               retries: int = 4) -> tuple[int, str]:
    src = WEB_DIR / f"p{page:03d}.jpg"
    dst = out_dir / f"p{page:03d}.md"
    if not src.exists():
        return page, "missing-source"

    img_b64 = base64.b64encode(src.read_bytes()).decode("ascii")

    raw = ""
    for attempt in range(retries):
        try:
            raw = call_model(img_b64, model, api_key, base)
            if not raw:
                raise RuntimeError("empty response")
            break
        except Exception as e:  # noqa: BLE001 - surface any transport/API failure
            if attempt == retries - 1:
                log(f"[FAIL] p{page:03d}: {e}")
                return page, f"error: {e}"
            time.sleep(2 ** attempt + 0.5)

    meta, body = split_meta(raw)

    folio_raw = meta.get("folio")
    try:
        folio = int(str(folio_raw)) if folio_raw is not None else None
    except ValueError:
        folio = None
    # The filename number is the printed book page (verified in extract_pages).
    folio_ok = None if folio is None else (folio == page)

    fm = [
        "---",
        f"page: {page}",
        f"pdf_index: {page - 1}",
        f"folio_read: {yaml_scalar(folio)}",
        f"folio_ok: {yaml_scalar(None if folio_ok is None else str(folio_ok).lower())}",
        f"unit: {yaml_scalar(meta.get('unit'))}",
        f"section: {yaml_scalar(meta.get('section'))}",
        f"types: {meta.get('types') or '[]'}",
        f"model: {yaml_scalar(model)}",
        f"extracted_at: {yaml_scalar(datetime.now(timezone.utc).isoformat(timespec='seconds'))}",
        "---",
        "",
    ]
    dst.write_text("\n".join(fm) + body + "\n", encoding="utf-8")

    flag = "" if folio_ok in (True, None) else f"  <-- folio mismatch (read {folio})"
    log(f"[ok] p{page:03d}  {len(body):>5} chars{flag}")
    return page, "ok"


def parse_pages(spec: str | None, only_missing: bool, out_dir: Path) -> list[int]:
    if spec:
        pages: list[int] = []
        for part in spec.split(","):
            part = part.strip()
            if "-" in part:
                a, b = part.split("-", 1)
                pages.extend(range(int(a), int(b) + 1))
            elif part:
                pages.append(int(part))
    else:
        pages = sorted(int(p.stem[1:]) for p in WEB_DIR.glob("p*.jpg"))
    if only_missing:
        pages = [p for p in pages if not (out_dir / f"p{p:03d}.md").exists()]
    return pages


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--model", default=DEFAULT_MODEL)
    ap.add_argument("--pages", help="e.g. 21,24,30-34")
    ap.add_argument("--out", type=Path, default=MD_DIR)
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--force", action="store_true", help="re-transcribe pages that already exist")
    args = ap.parse_args()

    load_env()
    api_key = os.environ.get("OPEN_ROUTER_API_KEY", "")
    base = os.environ.get("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
    if not api_key:
        sys.exit("[FATAL] OPEN_ROUTER_API_KEY not set (checked environment and .env)")

    args.out.mkdir(parents=True, exist_ok=True)
    pages = parse_pages(args.pages, only_missing=not args.force, out_dir=args.out)
    if not pages:
        print("[DONE] nothing to do -- all requested pages already transcribed")
        return

    print(f"[RUN] {len(pages)} page(s) | model {args.model} | {args.workers} workers -> {args.out}")
    t0 = time.time()
    results: dict[int, str] = {}
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {
            pool.submit(transcribe, p, args.model, api_key, base, args.out): p
            for p in pages
        }
        for fut in as_completed(futures):
            page, status = fut.result()
            results[page] = status

    ok = sum(1 for s in results.values() if s == "ok")
    print(f"[DONE] {ok}/{len(pages)} ok in {time.time() - t0:.0f}s")
    bad = {p: s for p, s in results.items() if s != "ok"}
    if bad:
        print(f"[FAILED] {sorted(bad)}")
        sys.exit(1)


if __name__ == "__main__":
    main()
