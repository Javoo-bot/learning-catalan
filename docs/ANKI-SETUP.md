# Configuración de Anki — para no saltarte nada

Tu Anki está en **inglés (en_GB)** y usa el **planificador v3**, así que abajo van
los nombres de menú tal como te aparecen.

Los mazos son planos y numerados (`CA · 01 mots · Tot un món`, `CA · 02 frases · …`).
No hay mazo padre: no existe nada que puedas pulsar por error y que mezcle varios.

> **Aviso primero.** Tu mazo antiguo `Catalan` tiene **831 tarjetas sin ver**. Si no lo
> pones en pausa, competirá con los mazos nuevos desde el primer día. El paso 3 lo
> resuelve.

---

## 1. Crea dos ajustes preestablecidos (presets)

Este es el truco que hace que todo lo demás sea fácil. En vez de editar números en
ocho mazos, cambias un mazo de preset y ya está.

Abre cualquier mazo → **⚙ → Options**. Arriba a la derecha, en el desplegable del
preset, elige **Add preset**. Crea estos dos:

| Preset | Para qué |
|---|---|
| `CA · actiu` | el único mazo que estás estudiando ahora |
| `CA · pausa` | todos los demás |

**Los dos llevan exactamente los mismos valores, salvo la primera línea.**

### Daily Limits
| Ajuste | `CA · actiu` | `CA · pausa` |
|---|---|---|
| New cards/day | **10** | **0** |
| Maximum reviews/day | **9999** | **9999** |

`9999` en repasos es deliberado: si limitas los repasos, Anki los pospone en
silencio, se acumulan, y ahí es donde se pierde el hilo. La velocidad se controla
con las tarjetas nuevas, nunca con los repasos.

### New Cards
| Ajuste | Valor |
|---|---|
| Learning steps | `1m 10m` |
| Graduating interval | `1` |
| Easy interval | `4` |
| **Insertion order** | **Sequential (oldest cards first)** |

**`Insertion order: Sequential` es el ajuste clave para no saltarte nada.** Hace que
las tarjetas salgan en el orden en que las puse en el mazo, no al azar.

### Lapses
| Ajuste | Valor |
|---|---|
| Relearning steps | `10m` |
| Minimum interval | `1` |
| Leech threshold | `8` |
| Leech action | **Tag Only** |

`Tag Only` y no `Suspend`: si una palabra se te resiste, quieres seguir viéndola, no
que desaparezca sin avisar.

### Display Order
| Ajuste | Valor |
|---|---|
| New card gather order | **Deck** |
| New card sort order | **Order gathered** |
| New/review order | **Show after reviews** |
| Interday learning/review order | **Show after reviews** |
| Review sort order | **Due date, then random** |

Las dos primeras conservan mi orden. `Show after reviews` hace que primero pagues la
deuda y luego aprendas cosas nuevas, nunca al revés.

### FSRS
Actívalo: **Options → FSRS → ON**, con **Desired retention `0.90`**.

Es mejor que el algoritmo antiguo y te ahorra tocar intervalos a mano. Deja los
parámetros vacíos (usa los de fábrica). Cuando lleves unos 1.000 repasos, vuelve
aquí y pulsa **Optimize** para que se ajuste a tu memoria.

Con FSRS activo, `Graduating interval` y `Easy interval` se ignoran — los calcula él.
Por eso los learning steps se quedan cortos (`1m 10m`) y no le metemos pasos de días.

---

## 2. Asigna los presets

Después de importar `a1a2_deck.apkg`:

- **`CA · 01 mots · Tot un món`** → preset **`CA · actiu`**
- **Todos los demás mazos `CA · …`** → preset **`CA · pausa`**

## 3. Pon en pausa el mazo antiguo

**`Catalan`** (el de 833 tarjetas) → preset **`CA · pausa`**.

No lo borres, no hace falta. Simplemente deja de darte tarjetas nuevas. Si algún día
lo quieres retomar, le pones `CA · actiu` y ya.

---

## 4. Rutina diaria

Pulsa el mazo numerado en el que estés. Ya está. Te da primero sus repasos y después
sus 10 tarjetas nuevas.

Cuando lleves tres o cuatro mazos empezados, los repasos quedan repartidos y tendrás
que ir tocando mazo por mazo. Para juntarlos en uno solo:

**Tools → Create Filtered Deck**
- Nombre: `CA · repàs`
- Search: `tag:ca-a1 is:due -is:new`
- Limit: `200`, ordenar por **Due date**
- **Deja marcado "Reschedule cards based on my answers"**

Se busca por etiqueta y no por nombre de mazo, así que seguirá funcionando cuando
añadamos mazos. Pulsa *Rebuild* cada día. Entonces la rutina son dos toques:
`CA · repàs` primero, tu mazo numerado después.

## 5. Cuando termines un mazo

Tú decides cuándo está terminado (cuando ya no salgan tarjetas nuevas y los repasos
sean cómodos). Entonces:

1. Mazo terminado → preset **`CA · pausa`**
2. Mazo siguiente → preset **`CA · actiu`**

Los repasos del mazo terminado siguen saliendo. Eso no es el problema que querías
evitar: eso es la repetición espaciada funcionando. Lo que no vuelve a pasar es que
te lleguen palabras *nuevas* de tres sitios a la vez.

---

## 6. Comprobación

En la lista de mazos, después de configurarlo:

- Número **azul** (nuevas) solo en `CA · 01`. En todos los demás, `0`.
- Ningún mazo aparece indentado bajo otro.
- `Catalan`, el antiguo, con `0` en azul.

## Dos cosas que sí dependen de ti

**No pulses "Easy" en una tarjeta nueva.** Se salta el paso de 10 minutos y la manda
a cuatro días. Usa **Good**. "Easy" es para cuando una tarjeta lleva tiempo y ya te
sobra.

**10 nuevas al día son ~3,5 meses** para las 1.030 tarjetas, con una carga diaria de
15–20 minutos cuando los repasos se estabilicen. Si te sobra tiempo sube a 15, pero
súbelo en `CA · actiu` y no en `CA · pausa`.

---

### Por qué esto no te lo dejo hecho

Anki guarda los presets en formato binario (protobuf) dentro de `collection.anki2`.
Editarlo desde fuera con Anki abierto es una buena forma de corromper la colección, y
el formato cambia entre versiones. Cinco minutos por la interfaz es más seguro.
