"""Turn a Catalan-English source list into a checked Catalan-Spanish one.

The beveradb lists came from AnkiWeb with no attribution and no review, and
they contain real errors (`el noia`, `el ordinador`, `alegre alegra`). Unlike
the A Punt archive there is no page to verify against, so this pass does two
jobs at once:

  1. gloss each entry Catalan -> Spanish *directly*, not via the English
     (the English is only a disambiguator: "a" -> "to, at, in, on")
  2. check the Catalan itself against normative IEC spelling and flag or
     correct anything wrong

Nothing is corrected silently: every change lands in a review file with the
original beside it, for a human to accept or reject.

    python scripts/gloss_source.py --in content/sources/beveradb-1000.tsv
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import time
import unicodedata
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / ".cache" / "gloss"
DEFAULT_MODEL = "google/gemini-2.5-pro"
BATCH = 40

PROMPT = """You are a Catalan lexicographer producing study material for a native SPANISH speaker learning Catalan.

For each numbered entry you get the Catalan headword and an English gloss from an unreviewed community wordlist. The English is only there to disambiguate meaning (e.g. "a" -> "to, at, in, on" tells you it is the preposition). Do NOT translate the English. Translate the CATALAN into Spanish directly.

For every entry return:
- "id": the number you were given
- "es": the Spanish translation. Match register and part of speech. For nouns include the Spanish article matching the Spanish gender ("la mesa", not "mesa"). If the Catalan is ambiguous, give the two commonest senses separated by " / " and no more.
- "ca": the Catalan, CORRECTED to normative IEC spelling if the source is wrong; otherwise copy it through unchanged. Fix: wrong articles (el noia -> la noia), missing elision (el ordinador -> l'ordinador), misspellings (arrisat -> arriscat), and non-existent forms (alegre alegra -> alegre, which is invariable). Normalise a masculine/feminine pair to the form "MASC / FEM" (el cosí la cosina -> el cosí / la cosina).
- "issue": "" if the source was already correct. Otherwise a SHORT reason, in English, max 8 words (e.g. "wrong article, noia is feminine").
- "kind": "mot" for a single lexical item including m/f pairs and articled nouns; "frase" for anything that is a phrase, question or expression.
- "risk": "cognat" if a Spanish speaker gets this free because the two are near-identical; "fals" if it looks like a Spanish word but means something else (a false friend) or diverges in gender; "" otherwise.
- "so": a pronunciation hint, RESPELLED IN SPANISH ORTHOGRAPHY so a Spanish speaker can read it aloud and land close to Central (Barcelona) Catalan. Mark the stressed syllable in CAPITALS and separate syllables with hyphens: "CA-za", "zhe-NÉ", "par-LÁ".

  Give "so" ONLY where a Spanish speaker reading the word with Spanish habits would get it WRONG. Leave it "" otherwise -- most entries need nothing, and a hint on an obvious word is noise.

  The cases that do need it:
  * s between vowels is voiced /z/, which Spanish lacks: casa -> "CA-za"
  * x and ix are /ʃ/ ("sh"): caixa -> "CA-sha", xocolata -> "shu-cu-LA-ta"
  * j, and g before e/i, are /ʒ/ (French j) -- write it "zh": gener -> "zhe-NÉ"
  * tj, tg, tx, ig are affricates: platja -> "PLAD-zha", raig -> "RRACH"
  * unstressed o is /u/: poder -> "pu-DÉ"
  * unstressed a and e are a relaxed neutral vowel; approximate with "a": pare -> "PA-ra"
  * final r is usually silent: carrer -> "ca-RÉ", parlar -> "par-LÁ"
  * final voiced consonants devoice: fred -> "FRET", verd -> "BERT"
  * l·l is a long l: paral·lel -> "pa-ral-LEL"
  * ny is Spanish ñ: canya -> "CA-ña"
  * ç and c before e/i are /s/: caça -> "CA-sa"

Return ONLY a JSON array, one object per entry, no prose and no code fence."""


# Same phonetic rules as above, for lists that already have their Spanish and
# only need the pronunciation line (the curated A Punt units).
# NOTE: keep PROMPT itself byte-stable -- its sha1 is the response cache key.
SOUND_PROMPT = """You are helping a native SPANISH speaker pronounce Catalan.

For each numbered Catalan entry, return {"id": <number>, "so": "<hint>"}.

"so" is a pronunciation hint RESPELLED IN SPANISH ORTHOGRAPHY, so that reading it
aloud as if it were Spanish lands close to Central (Barcelona) Catalan. Mark the
stressed syllable in CAPITALS, separate syllables with hyphens: "CA-za", "zhe-NÉ".

Return "so": "" unless a Spanish reading would actually get it WRONG. Most entries
need nothing, and a hint on an obvious word is noise. Never return a hint that is
just the same letters with the stress marked.

The cases that do need it:
* s between vowels is voiced /z/, which Spanish lacks: casa -> "CA-za"
* x and ix are /ʃ/ ("sh"): caixa -> "CA-sha"
* j, and g before e/i, are /ʒ/ (French j) -- write "zh": gener -> "zhe-NÉ"
* tj, tg, tx, ig are affricates: platja -> "PLAD-zha", raig -> "RRACH"
* unstressed o is /u/: poder -> "pu-DÉ"
* unstressed a and e are a relaxed neutral vowel; approximate with "a": pare -> "PA-ra"
* final r is usually silent: carrer -> "ca-RÉ", parlar -> "par-LÁ"
* final voiced consonants devoice: fred -> "FRET", verd -> "BERT"
* l·l is a long l: paral·lel -> "pa-ral-LEL"
* ny is Spanish ñ: canya -> "CA-ña"
* ç and c before e/i are /s/: caça -> "CA-sa"

Return ONLY a JSON array, no prose and no code fence."""


def useful_sound(so: str, ca: str) -> str:
    """Drop a hint that teaches nothing.

    The model tends to return a respelling even when it only marks stress
    ("a part" -> "a PART", "-ment" -> "-MENT"). If the hint reduces to the same
    letters as the Catalan, no sound change was encoded and the line is noise on
    the card. Affixes and fragments get nothing either.
    """
    if not so:
        return ""
    if ca.startswith(("-", "...")) or ca.endswith("-"):
        return ""
    # On a phrase the model often respells only the hard word and elides the
    # rest ("Molt be, gracies." -> "MULT ... GRA-si-as") or returns a fragment
    # ("Tant de gust." -> "da"). Half a hint is worse than none: you cannot tell
    # which word it refers to. Only a hint covering the whole entry is kept.
    if "..." in so or "…" in so:
        return ""

    def flat(s: str) -> str:
        s = "".join(c for c in unicodedata.normalize("NFD", s.lower())
                    if not unicodedata.combining(c))
        return re.sub(r"[^a-z]", "", s)

    fa, fs = flat(ca), flat(so)
    if not fs or not fa:
        return ""
    if len(fs) < 0.6 * len(fa):
        return ""
    return "" if fs == fa else so


def load_env() -> None:
    env = ROOT / ".env"
    if not env.exists():
        return
    for line in env.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def call(payload: str, model: str, key: str, base: str, timeout: int = 300,
         system: str | None = None) -> str:
    body = json.dumps({
        "model": model,
        "temperature": 0,
        "messages": [
            {"role": "system", "content": system or PROMPT},
            {"role": "user", "content": payload},
        ],
    }).encode("utf-8")
    req = urllib.request.Request(
        base.rstrip("/") + "/chat/completions", data=body,
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json",
                 "X-Title": "catalan-gloss"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as r:
        data = json.loads(r.read().decode("utf-8"))
    if "choices" not in data:
        raise RuntimeError(str(data)[:300])
    return (data["choices"][0]["message"].get("content") or "").strip()


def parse_json(raw: str) -> list[dict]:
    raw = raw.strip()
    raw = re.sub(r"\A```[a-z]*\s*\n", "", raw)
    raw = re.sub(r"\n```\s*\Z", "", raw)
    start, end = raw.find("["), raw.rfind("]")
    if start == -1 or end == -1:
        raise ValueError(f"no JSON array in response: {raw[:200]}")
    return json.loads(raw[start:end + 1])


def read_tsv(path: Path) -> tuple[list[str], list[dict]]:
    lines = path.read_text(encoding="utf-8").splitlines()
    header = lines[0].split("\t")
    rows = [dict(zip(header, l.split("\t"))) for l in lines[1:] if l.strip()]
    return header, rows


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--in", dest="inp", type=Path,
                    default=ROOT / "content/sources/beveradb-1000.tsv")
    ap.add_argument("--model", default=DEFAULT_MODEL)
    ap.add_argument("--batch", type=int, default=BATCH)
    ap.add_argument("--limit", type=int, help="only process the first N entries (for a trial)")
    ap.add_argument("--workers", type=int, default=8)
    args = ap.parse_args()

    load_env()
    key = os.environ.get("OPEN_ROUTER_API_KEY", "")
    base = os.environ.get("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
    if not key:
        sys.exit("[FATAL] OPEN_ROUTER_API_KEY not set")

    _, rows = read_tsv(args.inp)
    if args.limit:
        rows = rows[: args.limit]
    CACHE.mkdir(parents=True, exist_ok=True)

    results: dict[int, dict] = {}
    batches = [rows[i:i + args.batch] for i in range(0, len(rows), args.batch)]
    print(f"[RUN] {len(rows)} entries in {len(batches)} batches | {args.model}")

    # The prompt is part of the cache key: editing it must invalidate old answers,
    # otherwise a changed prompt silently reuses responses shaped by the old one.
    stamp = hashlib.sha1(PROMPT.encode("utf-8")).hexdigest()[:8]

    def run_batch(bi: int, batch: list[dict]) -> list[dict]:
        cache_file = CACHE / f"{args.inp.stem}-{args.model.replace('/', '_')}-{stamp}-{bi:03d}.json"
        if cache_file.exists():
            return json.loads(cache_file.read_text(encoding="utf-8"))
        payload = "\n".join(
            f"{bi * args.batch + j}. {r['ca']}   [en: {r['en']}]"
            for j, r in enumerate(batch)
        )
        for attempt in range(4):
            try:
                got = parse_json(call(payload, args.model, key, base))
                # Only a real answer is cached. Caching a failure would make the
                # next run skip the batch and silently lose those entries --
                # which is what happened when the API returned 402 mid-run.
                cache_file.write_text(json.dumps(got, ensure_ascii=False, indent=1),
                                      encoding="utf-8")
                return got
            except Exception as e:  # noqa: BLE001
                if attempt == 3:
                    print(f"  [FAIL] batch {bi}: {e}", flush=True)
                    return []
                time.sleep(2 ** attempt + 1)
        return []

    done = 0
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {pool.submit(run_batch, bi, b): bi for bi, b in enumerate(batches)}
        for fut in as_completed(futures):
            for item in fut.result():
                try:
                    results[int(item["id"])] = item
                except (KeyError, ValueError, TypeError):
                    continue
            done += 1
            print(f"  batch {done}/{len(batches)}  ({len(results)} entries done)", flush=True)

    # `ca` always keeps the SOURCE spelling. A model-proposed correction goes to
    # `ca_suggested` and to the review file only -- it is never applied here.
    # The trial showed why: the model "fixed" afeccionar-se into aficionar-se,
    # which is backwards (DIEC2 lists afeccionar-se; aficionar-se is the
    # castellanisme). Its normative judgement cannot be trusted unattended.
    out_cols = ["ca", "es", "so", "en", "kind", "risk", "ca_suggested", "issue",
                "flag", "source"]
    out = ["\t".join(out_cols)]
    review = ["ca_source\tca_suggested\tes\tissue"]
    missing = suggested = 0

    def cell(value: str) -> str:
        """No tabs or newlines may reach a TSV cell."""
        return re.sub(r"\s+", " ", str(value or "")).strip()

    for i, r in enumerate(rows):
        g = results.get(i)
        if not g:
            missing += 1
            continue
        ca_sugg = cell(g.get("ca"))
        issue = cell(g.get("issue"))
        if ca_sugg and ca_sugg != r["ca"]:
            suggested += 1
            review.append("\t".join([r["ca"], ca_sugg, cell(g.get("es")),
                                     issue or "changed, no reason given"]))
        else:
            ca_sugg = ""
        row = [
            r["ca"],                       # ca            (source spelling, unchanged)
            cell(g.get("es")),             # es
            useful_sound(cell(g.get("so")), r["ca"]),   # so
            cell(r["en"]),                 # en
            cell(g.get("kind") or r["kind"]),   # kind
            cell(g.get("risk")),           # risk
            ca_sugg,                       # ca_suggested  (blank unless it differs)
            issue,                         # issue
            cell(r.get("flag")),           # flag
            cell(r["source"]),             # source
        ]
        assert len(row) == len(out_cols), f"row/header mismatch: {len(row)} vs {len(out_cols)}"
        out.append("\t".join(row))

    dest = args.inp.with_suffix(".glossed.tsv")
    dest.write_text("\n".join(out) + "\n", encoding="utf-8")
    rev = args.inp.with_name(args.inp.stem + ".review.tsv")
    rev.write_text("\n".join(review) + "\n", encoding="utf-8")

    print(f"\n[DONE] {len(out) - 1} glossed -> {dest}")
    print(f"       {suggested} Catalan corrections SUGGESTED (not applied) -> {rev}")
    if missing:
        print(f"       [WARN] {missing} entries got no result; re-run to fill them")
    return 0


if __name__ == "__main__":
    sys.exit(main())
