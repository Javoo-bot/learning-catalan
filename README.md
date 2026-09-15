<div align="center">

<img src="https://readme-typing-svg.demolab.com?font=IBM+Plex+Mono&weight=500&size=23&duration=2800&pause=900&color=4A5A8C&center=true&vCenter=true&width=760&height=45&lines=Catal%C3%A0+A1+%E2%80%94+vocabulari+per+situacions;ES+%E2%86%92+CA%2C+nom%C3%A9s+en+una+direcci%C3%B3;%C2%ABVaig+anar%C2%BB+%3D+fui%2C+not+voy+a+ir" alt="Català A1 — vocabulari per situacions · ES → CA · «Vaig anar» = fui, not voy a ir">

### ⬇️ [**Get the deck on AnkiWeb**](https://ankiweb.net/shared/info/520774121)

[![AnkiWeb](https://img.shields.io/badge/AnkiWeb-download_deck-2E7D9A?style=for-the-badge&logo=anki&logoColor=white)](https://ankiweb.net/shared/info/520774121)

![Level](https://img.shields.io/badge/level-A1-4A5A8C?style=flat-square)
![Direction](https://img.shields.io/badge/direction-ES_→_CA-8C4A6B?style=flat-square)
![Formats](https://img.shields.io/badge/card_formats-7-3C6E47?style=flat-square)
![No media](https://img.shields.io/badge/no_images_or_audio-8A5A2B?style=flat-square)

</div>

---

Anki deck generator for learning **Catalan as a Spanish speaker**. Catalan is hard
in very different places for a Spanish speaker than for an English one, and most
material ignores that.

```bash
python scripts/build_situacions.py --situacio cor    # -> cor_deck.apkg
```

## Design

- **A deck is a place, not a lesson.** `CA · 01 · Al cor`, `CA · 02 · Passat i futur`.
- **ES → CA only.** The other direction is too easy for a Spanish speaker to review.
- **Flat numbered decks.** Finish one before starting the next.
- **Grouped, not atomised.** Four related words on one card, not four cards.
- **No images, no audio, no numbers.**

| Format | Front | Back |
|---|---|---|
| `frase` | `¿por dónde vamos?` | `Per on anem?` |
| `grup` | 4 concepts | the 4 in Catalan, as a table |
| `taula` | `FER — presente` | the full conjugation |
| `buit` | `Cada dimarts ___ assaig.` | `faig` |
| `tria` | sentence + 4 unmarked options | the right one + what the others mean |
| `multi` | 5 sentences at once | all 5 answers |
| `motlle` | `Em pots ___, si us plau?` | 3 examples to imitate |

A verb produces **7 consecutive cards**: table → gap → gap → pick the form → pick the
verb → imperative → free production.

## What makes it different

**No cognates.** `marroquí → marroquí` has nothing to recall. ~223 excluded.

**Pronunciation without audio** — respelled in Spanish orthography, only where
reading it "the Spanish way" would mislead:
`casa → CA-za` · `gener → zhe-NÉ` · `parlar → par-LÁ`

**Spanish-speaker traps, head on.** The first card of the tense deck is that
**`vaig anar` means "fui", not "voy a ir"** — `vaig` looks like *voy*, and it is the
most common mistake.

**Grammar sits on the back**, never before you answer, with its source.

## Sources

Conjugations and grammar from **A Punt A1+ A2** (Barcanova) · music vocabulary from
the **Acadèmia Valenciana de la Llengua** · past-tense contrast from **CPNL** and
*Català per ser feliç* · normative checks against **DIEC2**.

This repository holds **code and vocabulary only**. The book transcription, scans
and downloaded images are gitignored and stay local. See `docs/ANKI-SETUP.md` for the
Anki settings — half the design lives there, not in the code.
