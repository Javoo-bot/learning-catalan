"""Add a `so` pronunciation column to a TSV that already has its Spanish.

The A Punt units were curated before the pronunciation hint existed, and they
already carry a verified Spanish gloss, so they only need this one column.
Reuses the phonetic rules and the noise filter from gloss_source, so there is
one definition of how Catalan gets respelled for a Spanish reader.

    python scripts/add_sound.py content/unit-01.tsv

Rewrites the file in place, inserting `so` after `es`. Cached and resumable.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))

from gloss_source import (  # noqa: E402
    SOUND_PROMPT, call, load_env, parse_json, useful_sound,
)

CACHE = ROOT / ".cache" / "sound"
DEFAULT_MODEL = "google/gemini-2.5-pro"
BATCH = 60


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("files", nargs="+", type=Path)
    ap.add_argument("--model", default=DEFAULT_MODEL)
    ap.add_argument("--batch", type=int, default=BATCH)
    ap.add_argument("--workers", type=int, default=8)
    args = ap.parse_args()

    load_env()
    key = os.environ.get("OPEN_ROUTER_API_KEY", "")
    base = os.environ.get("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
    if not key:
        sys.exit("[FATAL] OPEN_ROUTER_API_KEY not set")

    CACHE.mkdir(parents=True, exist_ok=True)
    stamp = hashlib.sha1(SOUND_PROMPT.encode("utf-8")).hexdigest()[:8]

    for path in args.files:
        lines = path.read_text(encoding="utf-8").splitlines()
        header = lines[0].split("\t")
        rows = [dict(zip(header, l.split("\t"))) for l in lines[1:] if l.strip()]
        if "ca" not in header:
            print(f"[SKIP] {path.name}: no 'ca' column")
            continue

        batches = [rows[i:i + args.batch] for i in range(0, len(rows), args.batch)]

        def run(bi: int, batch: list[dict]) -> list[dict]:
            cf = CACHE / f"{path.stem}-{stamp}-{bi:03d}.json"
            if cf.exists():
                return json.loads(cf.read_text(encoding="utf-8"))
            payload = "\n".join(f"{bi * args.batch + j}. {r['ca']}"
                                for j, r in enumerate(batch))
            for attempt in range(4):
                try:
                    got = parse_json(call(payload, args.model, key, base,
                                          system=SOUND_PROMPT))
                    # Never cache a failure: it would make the retry skip the batch.
                    cf.write_text(json.dumps(got, ensure_ascii=False, indent=1),
                                  encoding="utf-8")
                    return got
                except Exception as e:  # noqa: BLE001
                    if attempt == 3:
                        print(f"  [FAIL] {path.name} batch {bi}: {e}", flush=True)
                        return []
                    time.sleep(2 ** attempt + 1)
            return []

        got_by_id: dict[int, str] = {}
        with ThreadPoolExecutor(max_workers=args.workers) as pool:
            futs = [pool.submit(run, bi, b) for bi, b in enumerate(batches)]
            for f in as_completed(futs):
                for item in f.result():
                    try:
                        got_by_id[int(item["id"])] = str(item.get("so") or "")
                    except (KeyError, ValueError, TypeError):
                        continue

        if "so" not in header:
            at = header.index("es") + 1 if "es" in header else len(header)
            header = header[:at] + ["so"] + header[at:]

        out = ["\t".join(header)]
        filled = 0
        for i, r in enumerate(rows):
            r["so"] = useful_sound(got_by_id.get(i, "").strip(), r["ca"])
            if r["so"]:
                filled += 1
            out.append("\t".join(r.get(c, "") for c in header))
        path.write_text("\n".join(out) + "\n", encoding="utf-8")
        print(f"[DONE] {path.name}: {filled}/{len(rows)} entries got a hint")
    return 0


if __name__ == "__main__":
    sys.exit(main())
