<div align="center">

<img src="https://readme-typing-svg.demolab.com?font=IBM+Plex+Mono&weight=500&size=26&duration=2600&pause=900&color=4A5A8C&center=true&vCenter=true&width=620&lines=Catal%C3%A0+A1+%E2%80%94+vocabulari+per+situacions;ES+%E2%86%92+CA%2C+nom%C3%A9s+en+una+direcci%C3%B3;Vaig+anar+%3D+%C2%ABfui%C2%BB%2C+no+%C2%ABvoy+a+ir%C2%BB" alt="Català A1 — vocabulari per situacions · ES → CA · vaig anar = «fui», no «voy a ir»">

### ⬇️ [**Descarrega el mazo a AnkiWeb**](https://ankiweb.net/shared/info/520774121)

[![Descargar en AnkiWeb](https://img.shields.io/badge/AnkiWeb-descargar_mazo-2E7D9A?style=for-the-badge&logo=anki&logoColor=white)](https://ankiweb.net/shared/info/520774121)

![Nivel](https://img.shields.io/badge/nivel-A1-4A5A8C?style=flat-square)
![Dirección](https://img.shields.io/badge/dirección-ES_→_CA-8C4A6B?style=flat-square)
![Formatos](https://img.shields.io/badge/formatos_de_tarjeta-7-3C6E47?style=flat-square)
![Sin audio](https://img.shields.io/badge/sin_imágenes_ni_audio-8A5A2B?style=flat-square)

</div>

---

# learning-catalan

Generador de mazos de Anki para aprender **catalán siendo castellanohablante**.

No es una lista de vocabulario más. Está construido sobre una idea concreta: para
un hispanohablante, el catalán es difícil en sitios muy distintos de donde lo es
para un angloparlante, y casi todo el material disponible ignora eso.

```bash
python scripts/build_situacions.py --situacio cor    # -> cor_deck.apkg
```

## Las cinco reglas

1. **Un mazo es un lugar, no una lección.** `CA · 01 · Al cor`, `CA · 02 · Passat i
   futur`. El orden dentro del mazo lo decide la columna `seq`, nunca el orden en
   que aparecieron las palabras en una fuente.
2. **Solo ES → CA.** Una plantilla por tipo de nota, una tarjeta por nota. La
   dirección contraria es demasiado fácil para un castellanohablante.
3. **Mazos planos y numerados.** Sin mazo padre: tocar un padre es lo que hace que
   Anki mezcle tarjetas nuevas de varios mazos a la vez.
4. **Agrupado, no atomizado.** Cuatro palabras relacionadas van en una tarjeta, no
   en cuatro. Cincuenta tarjetas de preposiciones es el fallo a evitar.
5. **Sin imágenes, sin audio, sin números.** Fuentes del sistema: Anki en el móvil
   no descarga tipografías. Los números se quitaron a propósito: son un sistema,
   no 75 hechos sueltos.

## Los seis formatos de tarjeta

| Formato | Delante | Detrás |
|---|---|---|
| `frase` | `¿por dónde vamos?` | `Per on anem?` + pronunciación |
| `grup` | 4 conceptos | los 4 en catalán, en tabla |
| `taula` | `FER — presente` | la conjugación entera |
| `buit` | `Cada dimarts ___ assaig.` | `faig` |
| `tria` | frase + 4 opciones sin marcar | la correcta + qué significan las otras |
| `multi` | 5 frases de golpe | las 5 respuestas |
| `motlle` | `Em pots ___, si us plau?` | 3 ejemplos para imitar |

Un verbo genera una **secuencia de 7 tarjetas consecutivas**: la tabla (única vez
que se ve entera) → hueco → hueco → elegir forma → elegir verbo → imperativo →
producción libre. Salen seguidas porque las notas se emiten en orden de `seq` y
Anki va configurado con `Insertion order: Sequential`.

## Lo que hace distinto a este mazo

**Sin cognados.** `marroquí → marroquí` no tiene nada que recordar. Se detectan y
se excluyen de las tarjetas (~223), aunque se conservan en los datos.

**Pronunciación sin audio.** Una reescritura con ortografía española, solo donde
leer "a la española" te engañaría:

```
casa    → CA-za        (s intervocálica sonora)
gener   → zhe-NÉ       (j / g+e,i)
caixa   → CA-sha       (x)
parlar  → par-LÁ       (r final muda)
```

**Trampas de castellanohablante, atacadas de frente.** La primera tarjeta del mazo
de tiempos verbales es que **`vaig anar` significa «fui», no «voy a ir»** — `vaig`
se parece a «voy» y es el error más común.

**La gramática va en el reverso**, nunca antes de responder, y con su fuente.

## Estructura

```
content/situacions/*.tsv   los mazos de estudio. Un fichero por lugar
content/verbs/*.tsv        conjugaciones
content/sources/*.tsv      reserva: vocabulario glosado del que sacar material
content/themes/*.tsv       léxico temático
scripts/                   extracción, glosado, validación y construcción
docs/ANKI-SETUP.md         los ajustes de Anki. Media parte del diseño vive ahí
```

`docs/ANKI-SETUP.md` importa tanto como el código: el diseño de la tarjeta no
arregla que Anki mezcle tarjetas nuevas de varios mazos. Eso se arregla en los
ajustes.

## Procedencia

Cada fila lleva una columna `confidence` que dice cuán literal es el catalán:

- `verbatim` — está tal cual en la página citada
- `lemma` — forma de diccionario de una palabra que la página sí imprime
- `derived` — el libro imprime el *patrón* (p. ej. `cantar` sigue el modelo `parlar`)
- `dictionary` — de diccionario o glosario, sin página

Las traducciones al español son **producidas**, nunca de la fuente: el libro de
referencia es monolingüe en catalán.

## Fuentes

- **A Punt A1+ A2** (Barcanova) — conjugaciones y reglas gramaticales.
  El libro **no** está en este repositorio.
- **Vocabulari de la música**, Acadèmia Valenciana de la Llengua — léxico musical.
- **CPNL** y el blog *Català per ser feliç* — contraste de pasados.
- **DIEC2** (Institut d'Estudis Catalans) — comprobación normativa.

## Aviso

Este repositorio contiene **código y vocabulario**, no material con copyright. La
transcripción del libro de referencia, el PDF y las imágenes descargadas están
excluidos en `.gitignore` y son de uso personal.

Proyecto personal de aprendizaje. Los mazos se comparten en AnkiWeb.
