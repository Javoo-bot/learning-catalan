"""Turn the model's suggested Catalan corrections into an auditable decision list.

The model proposes; a human decides. This writes one row per suggestion with an
explicit accept / reject and a reason, so the record of *why* every entry reads
the way it does survives, and so re-running never silently changes anything.

Three sources of decision, in order of precedence:

  1. MANUAL below -- every suggestion that is a real change of the Catalan,
     judged individually. This is where the model's mistakes get caught.
  2. auto-accept  -- the difference is only accents, punctuation or a " / "
     separator between a masculine and feminine form. Mechanical, safe.
  3. auto-reject  -- anything else, including additions that widen an entry's
     scope. Silence defaults to keeping what the source said.

    python scripts/make_decisions.py          # writes the decisions file
    python scripts/make_decisions.py --apply  # also rewrites the glossed TSV
"""
from __future__ import annotations

import argparse
import csv
import re
import sys
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "content/sources"
REVIEW = SRC / "beveradb-1000.review.tsv"
GLOSSED = SRC / "beveradb-1000.glossed.tsv"
DECISIONS = SRC / "beveradb-1000.decisions.tsv"

# Judged one by one.
#   ("accept", reason)          take the model's suggestion
#   ("reject", reason)          keep the source spelling
#   ("edit", reason, my_form)   neither is right; use my_form
MANUAL: dict[str, tuple] = {
    # --- source typos the model fixed correctly ---
    "cinquanta / cinquantà":    ("accept", "ordinal is cinquantè"),
    "noranta / norantà":        ("accept", "ordinal is norantè"),
    "setanta / setantà":        ("accept", "ordinal is setantè"),
    "començar a la feina":      ("accept", "gloss is empezar el trabajo, no preposition"),
    "conèixe't":                ("accept", "correct enclitic is conèixer-te"),
    "liest liesta":             ("accept", "typo: llest / llesta"),
    "llegir un llebre":         ("accept", "typo: llibre"),
    "normalament em llevo a les set.": ("accept", "typo: normalment"),
    "néixar":                   ("accept", "typo: néixer"),
    "pasar estona":             ("accept", "passar with ss, and l'estona"),
    "pèl-roig roja":            ("accept", "m/f separator"),
    "quart val?":               ("accept", "typo: quant"),
    "queder":                   ("accept", "typo: quedar"),
    "quins llibresa tens?":     ("accept", "typo: llibres"),
    "receptar, presciure":      ("accept", "typo: prescriure"),
    "roig roija":               ("accept", "feminine of roig is roja"),
    "sortir am amics":          ("accept", "typo: amb"),
    "voldria reservar una habitació sisplau.": ("accept", "si us plau, with a comma"),
    "voldria una barra de quart sisplau.": ("accept", "si us plau, with a comma"),
    "vull un paquet de sucre sisplau.": ("accept", "si us plau, with a comma"),
    "voldria un bitllet per a (lloc) pel (dia)": ("accept", "per al before the placeholder"),

    # --- the model dropped real content instead of fixing form ---
    "viu s'està":               ("edit", "s'esta is a real synonym (estar-se = to reside); "
                                         "keep both rather than delete one", "viu / s'està"),

    # --- the model is right: real typos and real Catalan errors ---
    "al constat de":            ("accept", "typo: costat"),
    "alegre alegra":            ("accept", "alegre is invariable; alegra is not a word"),
    "anar al teatro":           ("accept", "teatro is Spanish; Catalan is teatre"),
    "el noia":                  ("accept", "noia is feminine"),
    "el trebellador":           ("accept", "typo: treballador"),
    "el vostra la vostra":      ("accept", "masculine is vostre"),
    "en llenguado a la planxa": ("accept", "typo: un, not en"),
    "escocès escocèea":         ("accept", "typo in the feminine: escocesa"),
    "estar al punt de + inf":   ("accept", "the idiom is estar a punt de"),
    "està núvol":               ("accept", "nuvol is a noun; the phrase is esta ennuvolat"),
    "in":                       ("accept", "typo: en"),
    "l'autobús és més barat qie el metro.": ("accept", "typo: que"),
    "la cercavilla":            ("accept", "cercavila has one l"),
    "el ordinador, la computadora": ("accept", "elision required: l'ordinador"),
    "les cargols":              ("accept", "cargol is masculine: els cargols"),
    "la tauleta":               ("accept", "the Spanish gloss is mesita de noche"),
    "arrisat arrisada":         ("accept", "gloss is rizado, so arrissat with ss"),
    "de petit petita":          ("accept", "m/f pair separator"),
    "alemany alemana":          ("accept", "feminine is alemanya"),
    "lampista":                 ("accept", "same form both genders, articles clarify"),

    # --- the model is wrong: it pushed correct Catalan toward Spanish ---
    "afeccionar-se":            ("reject", "DIEC2 lists afeccionar-se; aficionar-se is the castellanisme"),
    "la comissaria de policia": ("reject", "Catalan comissaria has -ss-; the suggestion is neither language"),
    "anar al cine":             ("reject", "cine is a valid DIEC2 entry alongside cinema"),

    # --- not a spelling question at all ---
    "disparar-se":              ("reject", "SOURCE ENTRY IS BROKEN: disparar-se means to go off, "
                                           "not to disappear. Drop the row rather than reword it"),
    "anar (preterite tense)":   ("reject", "a verb paradigm, not a lexical entry; belongs in the verbs file"),

    # --- scope changes dressed as corrections ---
    "andalús":                  ("reject", "adding a feminine form widens the entry; not a correction"),
    "arquitecte":               ("reject", "adding a feminine form widens the entry; not a correction"),
}

# Removing "(m)" / "(f)" loses information a Spanish speaker needs: l'aigua
# hides its gender behind the elided article, and Catalan gender does not always
# match Spanish (l'aigua is feminine; Spanish "el agua" looks masculine).
GENDER_MARKER = re.compile(r"\((m|f)\)\s*$")


def fold(s: str) -> str:
    s = "".join(c for c in unicodedata.normalize("NFD", s.lower())
                if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]", "", s)


def classify(src: str, sug: str) -> str:
    if GENDER_MARKER.search(src) and not GENDER_MARKER.search(sug):
        return "gender-marker-removed"
    if fold(src) == fold(sug):
        return "accent-or-punctuation"
    if fold(sug.replace("/", " ")) == fold(src):
        return "mf-separator"
    stripped = re.sub(r"\b(el|la|l'|els|les)\s*", "", sug)
    if fold(stripped) == fold(src):
        return "article-added"
    return "real-change"


def decide(src: str, sug: str) -> tuple[str, str, str, str]:
    """-> (decision, reason, classification, final_form)"""
    kind = classify(src, sug)
    if src in MANUAL:
        entry = MANUAL[src]
        if entry[0] == "edit":
            return "edit", entry[1], kind, entry[2]
        return entry[0], entry[1], kind, (sug if entry[0] == "accept" else src)
    if kind in ("accent-or-punctuation", "mf-separator"):
        return "accept", f"mechanical: {kind}", kind, sug
    if kind == "gender-marker-removed":
        return ("reject", "the (m)/(f) marker is useful; Catalan gender can differ from Spanish",
                kind, src)
    if kind == "article-added":
        return "reject", "adds an article the source did not have; not a correction", kind, src
    return "reject", "unreviewed real change; source kept until judged", kind, src


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--apply", action="store_true",
                    help="rewrite the glossed TSV's ca column with the accepted forms")
    args = ap.parse_args()

    if not REVIEW.exists():
        sys.exit(f"[FATAL] {REVIEW} not found; run gloss_source.py first")

    with REVIEW.open(encoding="utf-8", newline="") as fh:
        suggestions = list(csv.DictReader(fh, delimiter="\t"))

    out = ["ca_source\tca_final\tdecision\tclassification\treason"]
    counts: dict[str, int] = {}
    accepted: dict[str, str] = {}
    unreviewed: list[str] = []

    for s in suggestions:
        src, sug = s["ca_source"], s["ca_suggested"]
        decision, reason, kind, final = decide(src, sug)
        if decision in ("accept", "edit"):
            accepted[src] = final
        if decision == "reject" and kind == "real-change" and src not in MANUAL:
            unreviewed.append(src)
        counts[decision] = counts.get(decision, 0) + 1
        out.append("\t".join([src, final, decision, kind, reason]))

    DECISIONS.write_text("\n".join(out) + "\n", encoding="utf-8")
    print(f"[DONE] {len(suggestions)} suggestions -> {DECISIONS}")
    for k, v in sorted(counts.items()):
        print(f"        {v:>4} {k}")
    print(f"        {len(MANUAL)} judged individually in MANUAL")
    if unreviewed:
        print(f"\n[WARN] {len(unreviewed)} real changes fell through to the default reject.")
        print("       Add them to MANUAL to decide deliberately:")
        for u in unreviewed[:20]:
            print(f"         {u}")

    if args.apply:
        if not GLOSSED.exists():
            sys.exit(f"[FATAL] {GLOSSED} not found")
        lines = GLOSSED.read_text(encoding="utf-8").splitlines()
        header = lines[0].split("\t")
        ca_i = header.index("ca")
        sug_i = header.index("ca_suggested") if "ca_suggested" in header else None
        changed = 0
        new = [lines[0]]
        for line in lines[1:]:
            if not line.strip():
                continue
            cells = line.split("\t")
            if cells[ca_i] in accepted:
                cells[ca_i] = accepted[cells[ca_i]]
                if sug_i is not None:
                    cells[sug_i] = ""      # resolved, no longer outstanding
                changed += 1
            new.append("\t".join(cells))
        GLOSSED.write_text("\n".join(new) + "\n", encoding="utf-8")
        print(f"\n[APPLIED] {changed} corrections written into {GLOSSED.name}")
    else:
        print("\n(dry run -- pass --apply to write the accepted forms into the glossed TSV)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
