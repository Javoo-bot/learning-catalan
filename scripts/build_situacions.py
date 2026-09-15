"""Build the situation decks: content/situacions/*.tsv -> cor_deck.apkg.

Supersedes build_a1a2_deck.py, which produced one flat word-list deck. The
problem it had -- and that Javier caught while studying it -- was that the order
came from wherever each word happened to come from (a coursebook unit, then an
alphabetical list), so the difficulty never went anywhere.

Here a deck is a *place*: `CA · 01 · Al cor`. Inside it the order is set by the
`seq` column, and the six formats build up: vocabulary blocks, then phrases,
then a verb's table followed by six sentences that get harder, then sentence
frames to make your own.

Six formats, six note types:

    frase / produccio / imperatiu  ES -> CA, one line each way
    grup                           four related words in one card, as a table
    taula                          a full conjugation, pulled from content/verbs/
    buit                           a Catalan sentence with a gap
    tria                           a sentence plus four options, one right
    motlle                         a frame plus three examples to imitate

Anki templates have no loops, so tables and option lists are rendered to HTML
here and stored in a field.

The verb sequences come out consecutive because the notes are emitted in `seq`
order and Anki is configured with `Insertion order: Sequential` plus
`New card sort order: Order gathered` (see docs/ANKI-SETUP.md).

    python scripts/build_situacions.py
    python scripts/build_situacions.py --situacio cor
"""
from __future__ import annotations

import argparse
import csv
import html
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import genanki  # noqa: E402

import build_deck as bd  # noqa: E402  (module level only defines data)

CONTENT = ROOT / "content"
SITUACIONS = CONTENT / "situacions"
VERBS = CONTENT / "verbs"
OUT = ROOT / "cor_deck.apkg"

DECK_BASE = 1748296000          # clear of the earlier decks
MODEL_BASE = 1748296900

# A place, its deck number, and the colour of its stripe. One colour per
# situation is the only use of colour: it tells you at a glance which place
# you are in without reading anything.
PLACES = {
    "cor":       (1, "Al cor",                "#8C4A6B"),
    "bar":       (4, "Al bar",                "#8A5A2B"),
    "passejant": (5, "Passejant",             "#3C6E47"),
    "moures":    (3, "Moure's i situar-se",   "#2A5A7A"),
    "verbs":     (2, "Verbs motor",           "#7A3B3B"),
    "temps":     (2, "Passat i futur",        "#4A5A8C"),
    "motlles":   (99, "Motlles de frase",     "#4A4A55"),
}

PERSONS = [("jo", "jo"), ("tu", "tu"), ("ell", "ell / ella"),
           ("nosaltres", "nosaltres"), ("vosaltres", "vosaltres"),
           ("ells", "ells / elles")]

CSS = bd.SHARED_CSS + """
.stripe { position:absolute; top:0; left:0; right:0; height:3px; }
.loc { position:absolute; top:14px; left:0; right:0; font-size:10.5px;
       letter-spacing:.13em; text-transform:uppercase; color:#9AA0A4; }
.card.nightMode .loc { color:#8A9095; }
.ask { font-size:23px; font-weight:500; line-height:1.34; margin:0 auto; max-width:93%; }
.ask.dim { font-size:15px; font-weight:400; color:#7A8084; }
.card.nightMode .ask.dim { color:#9AA1A3; }
.ask.small { font-size:19px; }
.rule { height:1px; background:#E7E9E7; width:44%; margin:15px auto; }
.card.nightMode .rule { background:#333739; }
.answer { font-size:29px; font-weight:600; line-height:1.26; margin:0 auto; max-width:94%; }
.answer.small { font-size:23px; }
.fill { font-size:31px; font-weight:600; }
.so { margin-top:12px; font-size:14px; letter-spacing:.04em; color:#7A8084; }
.card.nightMode .so { color:#9AA1A3; }
.eg { margin-top:14px; font-size:14.5px; line-height:1.45; font-style:italic;
      color:#6B7280; max-width:93%; margin-left:auto; margin-right:auto; }
.card.nightMode .eg { color:#9AA1A3; }
.src { margin-top:16px; font-size:10px; color:#9AA0A4; letter-spacing:.03em; }
table.t { width:100%; border-collapse:collapse; font-size:16px; margin:2px auto 0; }
table.t td { padding:5px 7px; border-bottom:1px solid #E7E9E7; text-align:left; }
.card.nightMode table.t td { border-bottom-color:#333739; }
table.t td.k { color:#7A8084; font-size:13.5px; width:44%; }
.card.nightMode table.t td.k { color:#9AA1A3; }
table.t td.v { font-weight:600; }
.opts { display:flex; flex-direction:column; gap:7px; margin-top:16px; }
.opt { border:1px solid #E7E9E7; border-radius:7px; padding:8px 12px;
       font-size:16px; text-align:left; }
.card.nightMode .opt { border-color:#333739; }
.opt.ok { font-weight:600; }
.gap { display:inline-block; min-width:62px; border-bottom:2px dashed currentColor;
       margin:0 3px; opacity:.55; }
.frame { font-size:22px; font-weight:500; line-height:1.4; }
.gram { background:#FBF3E2; border:1px solid #E4CE9C; color:#6B4E12;
        border-radius:10px; padding:11px 13px; margin-top:16px; font-size:13.5px;
        line-height:1.5; text-align:left; }
.card.nightMode .gram { background:#2B2517; border-color:#5C4C24; color:#E0C88A; }
.gram b { font-weight:600; }
.hl { background:#FBF3E2; border-bottom:2px solid #E4CE9C; padding:0 3px;
      border-radius:3px; font-weight:600; }
.card.nightMode .hl { background:#2B2517; border-bottom-color:#5C4C24; }
"""


def _wrap(inner: str) -> str:
    return ('<div class="stripe" style="background:{{Color}}"></div>'
            '<div class="loc">{{Deck}}</div>' + inner +
            '{{#Source}}<div class="src">{{Source}}</div>{{/Source}}')


# The grammar cloud only ever appears on the back: the rule is the explanation
# of the answer, never a hint before it.
GRAM = '{{#Gram}}<div class="gram">{{Gram}}</div>{{/Gram}}'


def _model(n: int, name: str, fields: list[str], qfmt: str, afmt: str) -> genanki.Model:
    return genanki.Model(
        MODEL_BASE + n, name,
        fields=[{"name": f} for f in fields],
        templates=[{"name": "ES -> CA", "qfmt": _wrap(qfmt),
                    "afmt": _wrap(afmt + GRAM)}],
        css=CSS,
    )


COMMON = ["Gram", "Deck", "Color", "Source"]

M_FRASE = _model(1, "CA Frase", ["Front", "Back", "So", "Note"] + COMMON,
    '<div class="ask">{{Front}}</div>',
    '<div class="ask dim">{{Front}}</div><div class="rule"></div>'
    '<div class="answer">{{Back}}</div>'
    '{{#So}}<div class="so">{{So}}</div>{{/So}}'
    '{{#Note}}<div class="eg">{{Note}}</div>{{/Note}}')

M_GRUP = _model(2, "CA Grup", ["FrontList", "Table", "Note"] + COMMON,
    '<div class="ask">{{FrontList}}</div>',
    '<div class="ask dim">{{FrontList}}</div><div class="rule"></div>{{Table}}'
    '{{#Note}}<div class="eg">{{Note}}</div>{{/Note}}')

M_TAULA = _model(3, "CA Taula", ["Label", "Table", "Note"] + COMMON,
    '<div class="ask">{{Label}}</div>',
    '<div class="ask dim">{{Label}}</div>{{Table}}'
    '{{#Note}}<div class="eg">{{Note}}</div>{{/Note}}')

M_BUIT = _model(4, "CA Buit", ["Sentence", "Answer", "Note"] + COMMON,
    '<div class="ask">{{Sentence}}</div>',
    '<div class="ask">{{Sentence}}</div><div class="rule"></div>'
    '<div class="answer fill" style="color:{{Color}}">{{Answer}}</div>'
    '{{#Note}}<div class="eg">{{Note}}</div>{{/Note}}')

M_TRIA = _model(5, "CA Tria", ["Sentence", "OptsFront", "OptsBack", "Note"] + COMMON,
    '<div class="ask small">{{Sentence}}</div>{{OptsFront}}',
    '<div class="ask small">{{Sentence}}</div>{{OptsBack}}'
    '{{#Note}}<div class="eg">{{Note}}</div>{{/Note}}')

# Three items on one card, so you have to think all three through before
# turning it over instead of reacting to a single prompt.
M_MULTI = _model(7, "CA Multi", ["Items", "Answers", "Note"] + COMMON,
    '<div class="ask small">{{Items}}</div>',
    '<div class="ask dim">{{Items}}</div><div class="rule"></div>{{Answers}}'
    '{{#Note}}<div class="eg">{{Note}}</div>{{/Note}}')

M_MOTLLE = _model(6, "CA Motlle", ["Frame", "Examples", "Note"] + COMMON,
    '<div class="ask dim">motlle</div><div class="frame">{{Frame}}</div>',
    '<div class="ask dim">{{Frame}}</div><div class="rule"></div>{{Examples}}'
    '{{#Note}}<div class="eg">{{Note}}</div>{{/Note}}')


def e(s: str) -> str:
    return html.escape(s or "", quote=False)


def rich(s: str) -> str:
    """Escape, then honour **...** as a highlight.

    Used to mark the time expression that decides the tense -- `**Ahir**` --
    so the trigger for the rule is visible in the sentence itself rather than
    only in the explanation underneath.
    """
    out = e(s)
    out = re.sub(r"\*\*(.+?)\*\*", r'<span class="hl">\1</span>', out)
    # Single asterisks mark the infinitive cue -- *(anar)* -- so it reads as a
    # prompt rather than as part of the sentence. Done after ** so the two
    # markers cannot collide.
    return re.sub(r"\*(.+?)\*", r"<i>\1</i>", out)


def gap(s: str) -> str:
    """Render ___ as a dashed gap, keeping **...** highlights."""
    return rich(s).replace("___", '<span class="gap"></span>')


def table_html(pairs: list[tuple[str, str]]) -> str:
    rows = "".join(f'<tr><td class="k">{e(k)}</td><td class="v">{e(v)}</td></tr>'
                   for k, v in pairs if v)
    return f'<table class="t">{rows}</table>'


def list_html(items: list[str]) -> str:
    return "<br>".join(e(i) for i in items)


def opts_html(raw: str, reveal: bool, color: str) -> str:
    out = []
    for o in [x for x in raw.split("|") if x]:
        ok = o.startswith("*")
        text = e(o.lstrip("*"))
        if ok and reveal:
            out.append(f'<div class="opt ok" style="border-color:{color};'
                       f'color:{color}">{text}</div>')
        else:
            out.append(f'<div class="opt">{text}</div>')
    return f'<div class="opts">{"".join(out)}</div>'


def load_conjugations() -> dict[tuple[str, str], dict]:
    conj: dict[tuple[str, str], dict] = {}
    for name in ("conjugacions.tsv", "derivades.tsv"):
        path = VERBS / name
        if not path.exists():
            continue
        with path.open(encoding="utf-8", newline="") as fh:
            for r in csv.DictReader(fh, delimiter="\t"):
                conj.setdefault((r["verb"].lower(), r["tense"]), r)
    return conj


def read_tsv(path: Path) -> list[dict]:
    """Read a situation file, refusing to guess about ragged rows.

    A row one tab short does not fail loudly on its own: DictReader just shifts
    every later value one column left, so the grammar note silently becomes the
    source and the source becomes the confidence. That happened, and it is
    invisible in the built deck. Column count is checked before anything else.
    """
    lines = path.read_text(encoding="utf-8").splitlines()
    if not lines:
        sys.exit(f"[FATAL] {path.name} is empty")
    header = lines[0].split("\t")
    ragged = [(i, len(l.split("\t"))) for i, l in enumerate(lines[1:], 2)
              if l.strip() and len(l.split("\t")) != len(header)]
    if ragged:
        print(f"[FATAL] {path.name}: {len(ragged)} row(s) do not have "
              f"{len(header)} columns — values would shift silently:")
        for line_no, count in ragged[:10]:
            print(f"          line {line_no}: {count} columns")
        sys.exit(1)
    with path.open(encoding="utf-8", newline="") as fh:
        return [r for r in csv.DictReader(fh, delimiter="\t") if r.get("format")]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--situacio", action="append",
                    help="only this place, e.g. --situacio cor")
    ap.add_argument("--out", type=Path, default=OUT)
    args = ap.parse_args()

    conj = load_conjugations()
    files = sorted(SITUACIONS.glob("*.tsv"))
    if args.situacio:
        want = set(args.situacio)
        files = [f for f in files if f.stem in want]
    if not files:
        sys.exit(f"[FATAL] no situation files matched in {SITUACIONS}")

    decks: list[genanki.Deck] = []
    totals: dict[str, int] = {}
    problems: list[str] = []

    for path in files:
        key = path.stem
        if key not in PLACES:
            problems.append(f"{path.name}: '{key}' is not in PLACES; add it with a colour")
            continue
        num, title, color = PLACES[key]
        deck_name = f"CA · {num:02d} · {title}"
        locator = f"{num:02d} · {title.lower()}"
        deck = genanki.Deck(DECK_BASE + num, deck_name)

        rows = read_tsv(path)
        rows.sort(key=lambda r: int(r["seq"]))
        counts: dict[str, int] = {}

        for r in rows:
            fmt = r["format"]
            common = [rich(r.get("gram", "")), locator, color, e(r.get("source", ""))]
            tags = ["ca-a1", f"lloc-{key}", fmt]
            if r.get("verb"):
                tags.append(f"verb-{r['verb']}")
            guid = genanki.guid_for(f"{key}:{r['seq']}")

            if fmt in ("frase", "produccio", "imperatiu"):
                note = genanki.Note(
                    model=M_FRASE, guid=guid, tags=tags,
                    fields=[rich(r["front"]), rich(r["back"]), e(r.get("so", "")),
                            e(r.get("note", ""))] + common)
            elif fmt == "grup":
                fr = [x for x in r["front"].split("|") if x]
                bk = [x for x in r["back"].split("|") if x]
                if len(fr) != len(bk):
                    problems.append(f"{path.name} seq {r['seq']}: grup has "
                                    f"{len(fr)} es vs {len(bk)} ca")
                    continue
                note = genanki.Note(
                    model=M_GRUP, guid=guid, tags=tags,
                    fields=[list_html(fr), table_html(list(zip(fr, bk))),
                            e(r.get("note", ""))] + common)
            elif fmt == "taula":
                c = conj.get((r["verb"].lower(), r["tense"]))
                if not c:
                    problems.append(f"{path.name} seq {r['seq']}: no conjugation for "
                                    f"{r['verb']} / {r['tense']}")
                    continue
                pairs = [(label, c.get(field, "")) for field, label in PERSONS]
                note = genanki.Note(
                    model=M_TAULA, guid=guid, tags=tags,
                    fields=[e(r["front"]), table_html(pairs),
                            e(r.get("note", ""))] + common)
            elif fmt == "buit":
                note = genanki.Note(
                    model=M_BUIT, guid=guid, tags=tags,
                    fields=[gap(r["front"]), e(r["back"]),
                            e(r.get("note", ""))] + common)
            elif fmt == "tria":
                note = genanki.Note(
                    model=M_TRIA, guid=guid, tags=tags,
                    fields=[gap(r["front"]),
                            opts_html(r["options"], False, color),
                            opts_html(r["options"], True, color),
                            e(r.get("note", ""))] + common)
            elif fmt == "multi":
                items = [x for x in r["front"].split("|") if x]
                answers = [x for x in r["back"].split("|") if x]
                if len(items) != len(answers):
                    problems.append(f"{path.name} seq {r['seq']}: multi has "
                                    f"{len(items)} items vs {len(answers)} answers")
                    continue
                numbered = "<br>".join(f"{i}. {gap(x)}" for i, x in enumerate(items, 1))
                note = genanki.Note(
                    model=M_MULTI, guid=guid, tags=tags,
                    fields=[numbered,
                            table_html([(f"{i}.", a) for i, a in enumerate(answers, 1)]),
                            e(r.get("note", ""))] + common)
            elif fmt == "motlle":
                ex = [x for x in r["back"].split("|") if x]
                note = genanki.Note(
                    model=M_MOTLLE, guid=guid, tags=tags,
                    fields=[gap(r["front"]),
                            table_html([("", x) for x in ex]),
                            e(r.get("note", ""))] + common)
            else:
                problems.append(f"{path.name} seq {r['seq']}: unknown format {fmt!r}")
                continue

            deck.add_note(note)
            counts[fmt] = counts.get(fmt, 0) + 1

        decks.append(deck)
        totals[deck_name] = len(deck.notes)
        print(f"{deck_name}  —  {len(deck.notes)} targetes")
        for f in ("grup", "frase", "taula", "buit", "tria", "multi",
                  "imperatiu", "produccio", "motlle"):
            if counts.get(f):
                print(f"      {counts[f]:>3}  {f}")

    if problems:
        print()
        for p in problems:
            print(f"[PROBLEM] {p}")
        sys.exit(1)

    genanki.Package(decks).write_to_file(str(args.out))
    print(f"\n[DONE] {sum(totals.values())} targetes en {len(decks)} mazo(s) -> {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
