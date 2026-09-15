"""Extract A Punt's own conjugation tables from the Markdown archive.

Pages 202-207 of the resum gramatical carry full paradigms as clean Markdown
tables: the header row names the verbs, the six data rows are jo / tu / ell /
nosaltres / vosaltres / ells. That is a better source than any wordlist -- it is
normative, it is complete, and every form can be cited to a printed page.

Two table shapes appear:

    | fer | poder |        <- verbs in the header (most pages)
    | faig | puc |
    ...

    | model sense -eix |    <- one verb, named in the first data row (p. 203)
    | **dormir** |
    | dormo |
    ...

The imperative on p. 206 is shaped differently again (person labels in the first
column) and is handled on its own.

    python scripts/extract_conjugations.py
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MD = ROOT / "libros" / "md"
OUT = ROOT / "content" / "verbs" / "conjugacions.tsv"

PAGES = range(199, 208)
PERSONS = ["jo", "tu", "ell", "nosaltres", "vosaltres", "ells"]

# A heading only changes the current tense if it names one. "formes irregulars"
# and "PRIMERA CONJUGACIO" are sub-labels inside a tense, not tenses.
TENSES = {
    "present d'indicatiu": "present",
    "present de subjuntiu": "subjuntiu present",
    "imperfet d'indicatiu": "imperfet",
    "passat perifràstic d'indicatiu": "passat perifràstic",
    "passat perifràstic": "passat perifràstic",
    "futur": "futur",
    "condicional": "condicional",
    "imperatiu": "imperatiu",
    "participi": "participi",
}
FM = re.compile(r"\A---\s*\n.*?\n---\s*\n", re.S)


def cells(line: str) -> list[str]:
    parts = [c.strip() for c in line.strip().strip("|").split("|")]
    return [re.sub(r"\*+", "", p).strip() for p in parts]


def is_sep(line: str) -> bool:
    return bool(re.fullmatch(r"\|[\s:|-]+\|", line.strip()))


def looks_like_verb(s: str) -> bool:
    return bool(re.fullmatch(r"[a-zà-ÿ'·\-]+(?:-se|-s'en|-hi|-ho|-se'n)?", s.strip(), re.I))


def parse_page(page: int, rows: list[dict], warnings: list[str],
               carried: list[str | None]) -> None:
    """`carried` holds the current tense across pages.

    The resum gramatical runs continuously: the third-conjugation present
    tables sit on p. 203 under the heading "TERCERA CONJUGACIO", with the
    "present d'indicatiu" heading back on p. 202. Resetting the tense at each
    page boundary silently dropped dormir and llegir.
    """
    path = MD / f"p{page:03d}.md"
    if not path.exists():
        return
    body = FM.sub("", path.read_text(encoding="utf-8"))
    lines = body.splitlines()
    tense = carried[0]

    i = 0
    while i < len(lines):
        line = lines[i]
        head = re.sub(r"[#*▸►\s]+", " ", line).strip().lower().rstrip(":")
        if head in TENSES:
            tense = TENSES[head]
        elif line.strip().startswith("#") or re.fullmatch(r"\*\*[^*]+\*\*", line.strip()):
            for k, v in TENSES.items():
                if k in head:
                    tense = v
                    break

        if line.strip().startswith("|") and i + 1 < len(lines) and is_sep(lines[i + 1]):
            header = cells(line)
            data = []
            j = i + 2
            while j < len(lines) and lines[j].strip().startswith("|"):
                data.append(cells(lines[j]))
                j += 1

            if tense == "imperatiu":
                parse_imperative(header, data, page, rows)
            elif len(header) == 1 and data and looks_like_verb(data[0][0]):
                # single-column shape: verb name is the first data row
                verb, forms = data[0][0], [d[0] for d in data[1:7]]
                if tense and len(forms) == 6:
                    rows.append(record(verb, tense, forms, page))
            elif tense and len(data) >= 6:
                for col, verb in enumerate(header):
                    if not verb or not looks_like_verb(verb):
                        continue
                    forms = [d[col] for d in data[:6] if col < len(d)]
                    if len(forms) == 6 and any(forms):
                        rows.append(record(verb, tense, forms, page))
            i = j
            continue
        i += 1
    carried[0] = tense


def parse_imperative(header: list[str], data: list[list[str]], page: int,
                     rows: list[dict]) -> None:
    """p. 206: person labels sit in the first column, verbs in the header."""
    for col, verb in enumerate(header):
        if col == 0 or not verb or not looks_like_verb(verb):
            continue
        forms = {}
        for d in data:
            if col >= len(d):
                continue
            who = d[0].lower().strip()
            if who in ("tu", "vostè", "nosaltres", "vosaltres", "vostès") and d[col]:
                forms[who] = d[col]
        if forms:
            rows.append({
                "verb": verb, "tense": "imperatiu",
                "jo": "", "tu": forms.get("tu", ""), "ell": forms.get("vostè", ""),
                "nosaltres": forms.get("nosaltres", ""),
                "vosaltres": forms.get("vosaltres", ""),
                "ells": forms.get("vostès", ""),
                "source_page": str(page),
            })


def record(verb: str, tense: str, forms: list[str], page: int) -> dict:
    r = {"verb": verb, "tense": tense, "source_page": str(page)}
    r.update(dict(zip(PERSONS, forms)))
    return r


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", type=Path, default=OUT)
    args = ap.parse_args()

    rows: list[dict] = []
    warnings: list[str] = []
    carried: list[str | None] = [None]
    for page in PAGES:
        parse_page(page, rows, warnings, carried)

    # Same verb+tense can appear twice (a page repeats a model); keep the first.
    seen, uniq = set(), []
    for r in rows:
        key = (r["verb"].lower(), r["tense"])
        if key in seen:
            continue
        seen.add(key)
        uniq.append(r)

    cols = ["verb", "tense"] + PERSONS + ["source_page"]
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", encoding="utf-8", newline="") as fh:
        fh.write("\t".join(cols) + "\n")
        for r in sorted(uniq, key=lambda x: (x["verb"].lower(), x["tense"])):
            fh.write("\t".join(r.get(c, "") for c in cols) + "\n")

    by_tense: dict[str, int] = {}
    for r in uniq:
        by_tense[r["tense"]] = by_tense.get(r["tense"], 0) + 1
    print(f"[DONE] {len(uniq)} paradigms -> {args.out}")
    print(f"       {len({r['verb'].lower() for r in uniq})} distinct verbs")
    for t, n in sorted(by_tense.items(), key=lambda kv: -kv[1]):
        print(f"         {n:>3}  {t}")
    for w in warnings:
        print(f"[WARN] {w}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
