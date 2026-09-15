"""
Build Catalan → Spanish Anki deck from vocabulari.txt content.

Outputs: catalan_deck.apkg (drag into Anki desktop to import).

Features:
- Two custom note types (CA-ES Vocab + CA Cloze) styled like card_styles_preview.html
- Per-category badge colors (fine-grained tags map to colored badges)
- Concrete nouns get an image: Unsplash → Pexels → Wikimedia Commons fallback chain
- Cloze examples mix simple drill cards with phil/lit/art context (Llull, Rodoreda,
  Borges, Tàpies, Dalí, Kant, etc.) — relevant to user interests
"""
import os
import sys
import json
import time
import unicodedata
import urllib.parse
import urllib.request
from pathlib import Path

import genanki

# Force UTF-8 stdout so prints with non-ASCII don't crash on Windows cp1252
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

ROOT = Path(__file__).parent
MEDIA_DIR = ROOT / "media"
MEDIA_DIR.mkdir(exist_ok=True)

# Stable IDs so re-runs are reproducible and Anki recognizes updates
DECK_ID = 1748293001
MODEL_VOCAB_ID = 1748293002
MODEL_CLOZE_ID = 1748293003

UA = "Mozilla/5.0 (anki-deck-builder)"


# ---------------------------------------------------------------------------
# .env LOADER (no external dep)
# ---------------------------------------------------------------------------
def load_env():
    env_path = ROOT / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip())


load_env()
UNSPLASH_KEY = os.environ.get("UNSPLASH_ACCESS_KEY", "")
PEXELS_KEY = os.environ.get("PEXELS_API_KEY", "")
OPENROUTER_KEY = os.environ.get("OPEN_ROUTER_API_KEY", "")
OPENROUTER_BASE = os.environ.get("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")


# ---------------------------------------------------------------------------
# CATEGORY IMAGES — Miró-style abstract art generated via OpenRouter
# One image per category, shown ONLY on cards without their own photo.
# ---------------------------------------------------------------------------
MIRO_STYLE = (
    "In the style of Joan Miró: abstract painting with bold flat colors "
    "(cobalt blue, vermilion red, cadmium yellow, deep black, leaf green) "
    "on a cream-white background, biomorphic organic shapes, dots, stars, "
    "a sun, a moon, simplified bird and eye motifs, calligraphic black lines, "
    "playful and dreamlike, child-like spontaneity, no text or letters, "
    "no signatures, square composition. Concept: "
)

CATEGORY_IMAGE_PROMPTS = {
    "verbs_irregulars": MIRO_STYLE + "broken twisted clock with letter-fragments scattered like birds escaping",
    "verbs_conj1": MIRO_STYLE + "a flowing river of identical leaf-shapes, regularity and rhythm",
    "verbs_conj2": MIRO_STYLE + "half-shapes mirroring each other across a vertical axis, asymmetry",
    "verbs_conj3": MIRO_STYLE + "a bifurcating path with abstract shapes at each end, directions",
    "verbs_reflexius": MIRO_STYLE + "a face split into mirror reflections looking inward at itself",
    "imperfet": MIRO_STYLE + "time flowing as nostalgic memory, melting clocks transforming into flowers and birds, soft drifting",
    "demostratius": MIRO_STYLE + "three pointing arrows or hands of different sizes near and far",
    "articles": MIRO_STYLE + "four constellation-like ornamental shapes floating, four jewels",
    "preposicions": MIRO_STYLE + "a labyrinth of rooms connected by colorful paths, spatial location",
    "conjuncions": MIRO_STYLE + "bridges and arcs connecting floating islands, connectors between worlds",
    "nhiha": MIRO_STYLE + "a horn of plenty overflowing with abstract organic objects, abundance",
    "contracte": MIRO_STYLE + "a sealed scroll floating between two abstract hands, an intangible promise",
    "historia": MIRO_STYLE + "factory chimneys turning into trees, industrial revolution dreaming, sun rising",
    "actes_socials": MIRO_STYLE + "a circle of stylized masks for joy, sorrow, celebration, gathering",
    "sabrina": MIRO_STYLE + "a split portrait, left half ghostly past, right half blooming present",
    "indicacions": MIRO_STYLE + "an abstract map with winding colorful paths leading to a bright star",
    "bar_frases": MIRO_STYLE + "a floating coffee cup, wine glass and slice of bread in a surreal cafe scene",
    "feines": MIRO_STYLE + "stylized tools floating around a central abstract worker figure",
    "formacio": MIRO_STYLE + "a graduation cap raining open books, knowledge and growth",
    "plans": MIRO_STYLE + "a calendar morphing into landscapes, days as adventures",
    "simptomes": MIRO_STYLE + "a body with glowing pain-spots, abstract symptoms as colored dots",
    "situar_se": MIRO_STYLE + "compass and crossroads with abstract directional shapes",
    "via_publica": MIRO_STYLE + "an abstract street with street lamps as stars, urban dreaming",
    "placa": MIRO_STYLE + "a town square with playful abstract objects floating",
    "equipaments": MIRO_STYLE + "a city of buildings as colorful geometric shapes",
    "parament": MIRO_STYLE + "a table setting with floating plate, fork and glass in joyful colors",
    "bar": MIRO_STYLE + "an abstract cafe terrace with colorful umbrellas and shapes",
}


# ---------------------------------------------------------------------------
# CARD DATA — VOCAB
# ---------------------------------------------------------------------------
# (catalan, spanish, category, image_query_or_None)
# Categories double as fine-grained tags AND CSS class for the badge color.
VOCAB = [
    # === equipaments públics ===
    ("casal de gent gran", "centro de día para mayores", "equipaments", "elderly community center"),
    ("cementiri", "cementerio", "equipaments", "cemetery"),
    ("hospital", "hospital", "equipaments", "hospital building"),
    ("ambulatori", "ambulatorio", "equipaments", "medical clinic"),
    ("centre cívic", "centro cívico", "equipaments", "community center"),
    ("oficina de l'ajuntament", "oficina del ayuntamiento", "equipaments", "city hall office"),
    ("protectora d'animals", "protectora de animales", "equipaments", "animal shelter dogs"),
    ("biblioteca", "biblioteca", "equipaments", "public library"),
    ("caserna de bombers", "parque de bomberos", "equipaments", "fire station"),
    ("policia local", "policía local", "equipaments", "police station"),
    ("piscina", "piscina", "equipaments", "swimming pool"),
    ("escola", "escuela", "equipaments", "elementary school"),
    ("poliesportiu", "polideportivo", "equipaments", "sports center"),
    ("pista esportiva", "pista deportiva", "equipaments", "sports court"),
    ("parc", "parque", "equipaments", "city park"),
    ("jardins", "jardines", "equipaments", "public garden"),
    ("quiosc", "quiosco", "equipaments", "newspaper kiosk"),
    ("teatre", "teatro", "equipaments", "theatre stage"),
    ("institut", "instituto", "equipaments", "high school building"),
    ("parc de mascotes", "parque para mascotas", "equipaments", "dog park"),
    ("escola bressol", "guardería", "equipaments", "kindergarten"),
    ("destacament de bombers", "destacamento de bomberos", "equipaments", "fire truck"),
    ("mercat municipal", "mercado municipal", "equipaments", "food market hall"),
    ("centre de dia", "centro de día", "equipaments", "day care center"),
    ("centre de formació professional", "centro de formación profesional", "equipaments", None),
    ("ludoteca", "ludoteca", "equipaments", "children playroom"),
    ("liceu", "liceo (teatro)", "equipaments", "opera house"),
    ("escola pública", "escuela pública", "equipaments", None),
    ("escola concertada", "escuela concertada", "equipaments", None),
    ("escola privada", "escuela privada", "equipaments", None),
    ("gimnàs", "gimnasio", "equipaments", "gym interior"),
    ("instal·lacions esportives", "instalaciones deportivas", "equipaments", None),
    ("plaça de toros", "plaza de toros", "equipaments", "bullring"),
    ("comissaria de mossos d'esquadra", "comisaría de Mossos d'Esquadra", "equipaments", None),
    ("escola d'idiomes", "escuela de idiomas", "equipaments", "language classroom"),
    ("centre de salut mental", "centro de salud mental", "equipaments", None),

    # === via pública ===
    ("cantonada", "esquina", "via_publica", None),
    ("vorera", "acera", "via_publica", "sidewalk street"),
    ("pas de vianants", "paso de peatones", "via_publica", "pedestrian crossing"),
    ("contenidors", "contenedores", "via_publica", "recycling containers street"),
    ("paperera", "papelera", "via_publica", "street trash bin"),
    ("farola", "farola", "via_publica", "street lamp"),
    ("banc", "banco (mueble)", "via_publica", "park bench"),
    ("arbre", "árbol", "via_publica", "city tree street"),
    ("parada de bus", "parada de bus", "via_publica", "bus stop"),
    ("parada de metro", "boca de metro", "via_publica", "metro entrance"),
    ("semàfor", "semáforo", "via_publica", "traffic light"),
    ("sortida de metro", "salida de metro", "via_publica", "subway exit"),
    ("fanal", "farol", "via_publica", "old street lantern"),
    ("font", "fuente", "via_publica", "public drinking fountain"),
    ("cartell informatiu", "cartel informativo", "via_publica", "information sign"),
    ("escalinata", "escalinata", "via_publica", "outdoor stairs"),

    # === objectes de la plaça ===
    ("bústia", "buzón", "placa", "mailbox"),
    ("jocs infantils", "juegos infantiles", "placa", "playground"),
    ("cavallets", "tiovivo", "placa", "carousel"),
    ("porteria de futbol", "portería de fútbol", "placa", "soccer goal"),
    ("gronxadors", "columpios", "placa", "playground swings"),
    ("tobogans", "toboganes", "placa", "playground slide"),
    ("tirolina", "tirolina", "placa", "zipline park"),
    ("balancí", "balancín", "placa", "seesaw playground"),
    ("rocòdrom", "rocódromo", "placa", "climbing wall"),
    ("gespa", "césped", "placa", "lawn grass"),
    ("carril bici", "carril bici", "placa", "bike lane"),
    ("àrea per a gossos", "área para perros", "placa", "dog park area"),
    ("taules de pícnic", "mesas de pícnic", "placa", "picnic table"),
    ("pistes de bàsquet", "pistas de baloncesto", "placa", "basketball court"),
    ("pista de patinatge", "pista de patinaje", "placa", "skating rink"),
    ("aparcament de bicicletes", "aparcamiento de bicicletas", "placa", "bike parking"),
    ("font d'aigua potable", "fuente de agua potable", "placa", "drinking fountain park"),
    ("lavabos públics", "aseos públicos", "placa", None),
    ("guingueta", "chiringuito", "placa", "outdoor bar"),
    ("pèrgola", "pérgola", "placa", "garden pergola"),
    ("mirador", "mirador", "placa", "viewpoint city"),

    # === professions (feines) ===
    ("mestra", "maestra", "feines", "teacher classroom"),
    ("policia", "policía", "feines", "police officer"),
    ("metgessa", "médica", "feines", "female doctor"),
    ("cambrera", "camarera", "feines", "waitress"),
    ("perruquera", "peluquera", "feines", "hairdresser"),
    ("dependenta", "dependienta", "feines", "shop assistant"),
    ("administratiu", "administrativo", "feines", None),
    ("taxista", "taxista", "feines", "taxi driver"),
    ("cuidador", "cuidador", "feines", None),
    ("bomber", "bombero", "feines", "firefighter"),
    ("netejador", "limpiador", "feines", None),
    ("paleta", "albañil", "feines", "construction worker"),
    ("electricista", "electricista", "feines", "electrician"),

    # === formació ===
    ("estudiant universitari", "estudiante universitario", "formacio", None),
    ("educació obligatòria", "educación obligatoria", "formacio", None),
    ("diplomat universitari", "diplomado universitario", "formacio", None),
    ("graduat universitari", "graduado universitario", "formacio", None),
    ("acadèmic", "académico", "formacio", None),
    ("formació professional", "formación profesional", "formacio", None),
    ("curs superior", "curso superior", "formacio", None),
    ("curs formatiu", "curso formativo", "formacio", None),

    # === contracte ===
    ("jornada completa", "jornada completa", "contracte", None),
    ("jornada partida", "jornada partida", "contracte", None),
    ("jornada sencera", "jornada entera", "contracte", None),
    ("sou base", "sueldo base", "contracte", None),
    ("millora de sou", "mejora de sueldo", "contracte", None),
    ("increment salarial", "incremento salarial", "contracte", None),
    ("plus de perillositat", "plus de peligrosidad", "contracte", None),
    ("plus de nocturnitat", "plus de nocturnidad", "contracte", None),
    ("plus de festius", "plus de festivos", "contracte", None),
    ("contracte de durada determinada", "contrato de duración determinada", "contracte", None),
    ("contracte temporal", "contrato temporal", "contracte", None),
    ("contracte fix", "contrato fijo", "contracte", None),
    ("contracte fix discontinu", "contrato fijo discontinuo", "contracte", None),
    ("contracte de pràctiques", "contrato de prácticas", "contracte", None),
    ("contracte de relleu", "contrato de relevo", "contracte", None),
    ("baixa", "baja (laboral)", "contracte", None),
    ("cap de setmana", "fin de semana", "contracte", None),
    ("horari flexible", "horario flexible", "contracte", None),
    ("hores extres", "horas extras", "contracte", None),
    ("hores compactades", "horas compactadas", "contracte", None),
    ("cobrar en negre", "cobrar en negro", "contracte", None),
    ("fer-se autònom", "hacerse autónomo", "contracte", None),

    # === historia (cond. treball s. XIX) ===
    ("treballadors", "trabajadores", "historia", None),
    ("pagesos", "campesinos", "historia", None),
    ("senyor", "señor", "historia", None),
    ("rei", "rey", "historia", None),
    ("aldees", "aldeas", "historia", None),
    ("estacions", "estaciones", "historia", None),
    ("tasques", "tareas", "historia", None),
    ("pobresa", "pobreza", "historia", None),
    ("ciutats", "ciudades", "historia", None),
    ("artesans", "artesanos", "historia", None),
    ("comerciants", "comerciantes", "historia", None),
    ("economia", "economía", "historia", None),
    ("burgesos", "burgueses", "historia", None),
    ("fortunes", "fortunas", "historia", None),
    ("fàbriques", "fábricas", "historia", None),
    ("mines", "minas", "historia", None),
    ("obrers", "obreros", "historia", None),
    ("barris", "barrios", "historia", None),
    ("polítics", "políticos", "historia", None),
    ("intel·lectuals", "intelectuales", "historia", None),
    ("drets", "derechos", "historia", None),
    ("desigualtats", "desigualdades", "historia", None),
    ("associacions", "asociaciones", "historia", None),
    ("salaris", "salarios", "historia", None),
    ("descans", "descanso", "historia", None),
    ("educació", "educación", "historia", None),
    ("lluita", "lucha", "historia", None),
    ("societats", "sociedades", "historia", None),

    # === parament de taula ===
    ("plat", "plato", "parament", "ceramic plate"),
    ("plat fondo", "plato hondo", "parament", "soup plate"),
    ("plat pla", "plato llano", "parament", "dinner plate"),
    ("plat de postres", "plato de postre", "parament", "dessert plate"),
    ("sopera", "sopera", "parament", "soup tureen"),
    ("amanidera", "ensaladera", "parament", "salad bowl"),
    ("safata", "bandeja", "parament", "serving tray"),
    ("panera", "panera", "parament", "bread basket"),
    ("gerra", "jarra", "parament", "water jug"),
    ("ampolla", "botella", "parament", "wine bottle"),
    ("coberts", "cubiertos", "parament", "cutlery set"),
    ("forquilla", "tenedor", "parament", "fork"),
    ("ganivet", "cuchillo", "parament", "knife"),
    ("cullera", "cuchara", "parament", "spoon"),
    ("cullereta", "cucharilla", "parament", "teaspoon"),
    ("got", "vaso", "parament", "drinking glass"),
    ("tassa", "taza", "parament", "coffee cup"),
    ("copa de vi", "copa de vino", "parament", "wine glass"),
    ("copa de cava", "copa de cava", "parament", "champagne flute"),
    ("estovalles", "mantel", "parament", "tablecloth"),
    ("tovalló", "servilleta", "parament", "cloth napkin"),
    ("saler", "salero", "parament", "salt shaker"),
    ("pebrer", "pimentero", "parament", "pepper shaker"),
    ("sucrera", "azucarera", "parament", "sugar bowl"),
    ("setrill", "aceitera", "parament", "olive oil bottle"),

    # === bar ===
    ("bar", "bar", "bar", "cafe bar"),
    ("cafeteria", "cafetería", "bar", "coffee shop"),
    ("restaurant", "restaurante", "bar", "restaurant interior"),
    ("terrassa", "terraza", "bar", "outdoor cafe terrace"),
    ("barra", "barra", "bar", "bar counter"),
    ("la carta", "la carta", "bar", "restaurant menu"),
    ("el menú", "el menú", "bar", None),
    ("la comanda", "el pedido", "bar", None),
    ("el compte", "la cuenta", "bar", "restaurant bill"),
    ("la propina", "la propina", "bar", "tip coins"),
    ("cafè", "café", "bar", "espresso coffee"),
    ("cafè sol", "café solo", "bar", "black coffee"),
    ("cafè amb llet", "café con leche", "bar", "latte coffee"),
    ("tallat", "cortado", "bar", "cortado coffee"),
    ("caputxino", "capuchino", "bar", "cappuccino"),
    ("te", "té", "bar", "tea cup"),
    ("infusió", "infusión", "bar", "herbal tea"),
    ("camamilla", "manzanilla", "bar", "chamomile tea"),
    ("xocolata desfeta", "chocolate caliente", "bar", "hot chocolate"),
    ("aigua amb gas", "agua con gas", "bar", "sparkling water"),
    ("aigua sense gas", "agua sin gas", "bar", "still water bottle"),
    ("suc de taronja", "zumo de naranja", "bar", "orange juice"),
    ("llimonada", "limonada", "bar", "lemonade"),
    ("refresc", "refresco", "bar", "soda glass"),
    ("batut", "batido", "bar", "milkshake"),
    ("cervesa", "cerveza", "bar", "beer glass"),
    ("canya", "caña (cerveza)", "bar", None),
    ("clara", "clara (cerveza con limón)", "bar", None),
    ("vi blanc", "vino blanco", "bar", "white wine glass"),
    ("vi negre", "vino tinto", "bar", "red wine glass"),
    ("vi rosat", "vino rosado", "bar", "rose wine"),
    ("cava", "cava", "bar", "cava bottle"),
    ("vermut", "vermut", "bar", "vermouth glass"),
    ("tapa", "tapa", "bar", "spanish tapas"),
    ("pinxo", "pincho", "bar", "basque pintxos"),
    ("entrepà", "bocadillo", "bar", "baguette sandwich"),
    ("torrada", "tostada", "bar", "toast bread"),
    ("pa amb tomàquet", "pan con tomate", "bar", "pan con tomate"),
    ("truita de patates", "tortilla de patatas", "bar", "spanish omelette"),
    ("patates braves", "patatas bravas", "bar", "patatas bravas"),
    ("olives", "aceitunas", "bar", "olives bowl"),
    ("croqueta", "croqueta", "bar", "croquettes"),
    ("pernil", "jamón", "bar", "iberian ham"),
    ("formatge", "queso", "bar", "cheese platter"),

    # === símptomes ===
    ("mal de cap", "dolor de cabeza", "simptomes", None),
    ("mal de panxa", "dolor de barriga", "simptomes", None),
    ("mal d'estómac", "dolor de estómago", "simptomes", None),
    ("mal d'esquena", "dolor de espalda", "simptomes", None),
    ("mal de coll", "dolor de garganta", "simptomes", None),
    ("mal de queixal", "dolor de muelas", "simptomes", None),
    ("mal d'orella", "dolor de oído", "simptomes", None),
    ("punxada", "punzada / pinchazo", "simptomes", None),
    ("cremor", "ardor", "simptomes", None),
    ("febre", "fiebre", "simptomes", None),
    ("dècimes", "décimas (de fiebre)", "simptomes", None),
    ("calfreds", "escalofríos", "simptomes", None),
    ("suor freda", "sudor frío", "simptomes", None),
    ("cansament", "cansancio", "simptomes", None),
    ("fatiga", "fatiga", "simptomes", None),
    ("esgotament", "agotamiento", "simptomes", None),
    ("debilitat", "debilidad", "simptomes", None),
    ("mareig", "mareo", "simptomes", None),
    ("vertigen", "vértigo", "simptomes", None),
    ("desmai", "desmayo", "simptomes", None),
    ("tos seca", "tos seca", "simptomes", None),
    ("mocs", "mocos", "simptomes", None),
    ("nas tapat", "nariz tapada", "simptomes", None),
    ("esternuts", "estornudos", "simptomes", None),
    ("ronquera", "ronquera", "simptomes", None),
    ("ofec", "ahogo / falta de aire", "simptomes", None),
    ("nàusees", "náuseas", "simptomes", None),
    ("vòmits", "vómitos", "simptomes", None),
    ("diarrea", "diarrea", "simptomes", None),
    ("restrenyiment", "estreñimiento", "simptomes", None),
    ("acidesa", "acidez", "simptomes", None),
    ("picor", "picor", "simptomes", None),
    ("erupció", "erupción", "simptomes", None),
    ("butllofes", "ampollas", "simptomes", None),
    ("urticària", "urticaria", "simptomes", None),
    ("inflor", "hinchazón", "simptomes", None),
    ("morat", "moratón / cardenal", "simptomes", None),
    ("insomni", "insomnio", "simptomes", None),
    ("ansietat", "ansiedad", "simptomes", None),
    ("angoixa", "angustia", "simptomes", None),
    ("formigueig", "hormigueo", "simptomes", None),
    ("rampes", "calambres", "simptomes", None),
    ("tremolors", "temblores", "simptomes", None),

    # === fer plans ===
    ("passar un dia a la platja", "pasar un día en la playa", "plans", "beach day"),
    ("fer senderisme", "hacer senderismo", "plans", "hiking trail"),
    ("fer una paella al migdia", "hacer una paella al mediodía", "plans", "paella"),
    ("anar a la piscina", "ir a la piscina", "plans", None),
    ("anar a veure un museu", "ir a ver un museo", "plans", "art museum"),
    ("fer exercici a l'aire lliure", "hacer ejercicio al aire libre", "plans", "outdoor exercise"),

    # === verbs A2 — irregulars essencials ===
    ("ser", "ser", "verbs_irregulars", None),
    ("estar", "estar", "verbs_irregulars", None),
    ("haver", "haber (auxiliar)", "verbs_irregulars", None),
    ("tenir", "tener", "verbs_irregulars", None),
    ("anar", "ir", "verbs_irregulars", None),
    ("anar-se'n", "irse / marcharse", "verbs_irregulars", None),
    ("venir", "venir", "verbs_irregulars", None),
    ("fer", "hacer", "verbs_irregulars", None),
    ("dir", "decir", "verbs_irregulars", None),
    ("poder", "poder", "verbs_irregulars", None),
    ("voler", "querer", "verbs_irregulars", None),
    ("saber", "saber", "verbs_irregulars", None),
    ("conèixer", "conocer", "verbs_irregulars", None),
    ("veure", "ver", "verbs_irregulars", None),
    ("sortir", "salir", "verbs_irregulars", None),
    ("dur", "llevar / traer", "verbs_irregulars", None),
    ("prendre", "tomar / coger", "verbs_irregulars", None),
    ("beure", "beber", "verbs_irregulars", None),
    ("escriure", "escribir", "verbs_irregulars", None),
    ("llegir", "leer", "verbs_irregulars", None),
    ("viure", "vivir", "verbs_irregulars", None),
    ("caure", "caer", "verbs_irregulars", None),
    ("riure", "reír", "verbs_irregulars", None),
    ("néixer", "nacer", "verbs_irregulars", None),
    ("morir", "morir", "verbs_irregulars", None),

    # === verbs A2 — 1a conjugació (-ar) ===
    ("parlar", "hablar", "verbs_conj1", None),
    ("treballar", "trabajar", "verbs_conj1", None),
    ("estudiar", "estudiar", "verbs_conj1", None),
    ("jugar", "jugar", "verbs_conj1", None),
    ("caminar", "caminar", "verbs_conj1", None),
    ("viatjar", "viajar", "verbs_conj1", None),
    ("esmorzar", "desayunar", "verbs_conj1", None),
    ("dinar", "comer (al mediodía)", "verbs_conj1", None),
    ("sopar", "cenar", "verbs_conj1", None),
    ("comprar", "comprar", "verbs_conj1", None),
    ("pagar", "pagar", "verbs_conj1", None),
    ("buscar", "buscar", "verbs_conj1", None),
    ("trobar", "encontrar", "verbs_conj1", None),
    ("escoltar", "escuchar", "verbs_conj1", None),
    ("mirar", "mirar", "verbs_conj1", None),
    ("esperar", "esperar", "verbs_conj1", None),
    ("ajudar", "ayudar", "verbs_conj1", None),
    ("explicar", "explicar", "verbs_conj1", None),
    ("preguntar", "preguntar", "verbs_conj1", None),
    ("contestar", "contestar", "verbs_conj1", None),
    ("començar", "empezar", "verbs_conj1", None),
    ("acabar", "acabar / terminar", "verbs_conj1", None),
    ("agafar", "coger / agarrar", "verbs_conj1", None),
    ("deixar", "dejar", "verbs_conj1", None),
    ("portar", "llevar", "verbs_conj1", None),
    ("ensenyar", "enseñar", "verbs_conj1", None),
    ("cantar", "cantar", "verbs_conj1", None),
    ("ballar", "bailar", "verbs_conj1", None),
    ("nedar", "nadar", "verbs_conj1", None),
    ("cuinar", "cocinar", "verbs_conj1", None),
    ("netejar", "limpiar", "verbs_conj1", None),
    ("descansar", "descansar", "verbs_conj1", None),
    ("recordar", "recordar", "verbs_conj1", None),
    ("oblidar", "olvidar", "verbs_conj1", None),
    ("pensar", "pensar", "verbs_conj1", None),
    ("necessitar", "necesitar", "verbs_conj1", None),
    ("trucar", "llamar (teléfono)", "verbs_conj1", None),
    ("arribar", "llegar", "verbs_conj1", None),
    ("tornar", "volver", "verbs_conj1", None),
    ("passar", "pasar", "verbs_conj1", None),
    ("canviar", "cambiar", "verbs_conj1", None),
    ("enviar", "enviar", "verbs_conj1", None),

    # === verbs A2 — 2a conjugació (-re/-er) ===
    ("aprendre", "aprender", "verbs_conj2", None),
    ("comprendre", "comprender", "verbs_conj2", None),
    ("entendre", "entender", "verbs_conj2", None),
    ("vendre", "vender", "verbs_conj2", None),
    ("perdre", "perder", "verbs_conj2", None),
    ("respondre", "responder", "verbs_conj2", None),
    ("creure", "creer", "verbs_conj2", None),
    ("deure", "deber", "verbs_conj2", None),
    ("treure", "sacar / quitar", "verbs_conj2", None),

    # === verbs A2 — 3a conjugació (-ir) ===
    ("dormir", "dormir", "verbs_conj3", None),
    ("sentir", "sentir / oír", "verbs_conj3", None),
    ("obrir", "abrir", "verbs_conj3", None),
    ("oferir", "ofrecer", "verbs_conj3", None),
    ("decidir", "decidir", "verbs_conj3", None),
    ("preferir", "preferir", "verbs_conj3", None),
    ("traduir", "traducir", "verbs_conj3", None),
    ("conduir", "conducir", "verbs_conj3", None),
    ("construir", "construir", "verbs_conj3", None),
    ("servir", "servir", "verbs_conj3", None),
    ("patir", "sufrir", "verbs_conj3", None),
    ("complir", "cumplir", "verbs_conj3", None),
    ("fugir", "huir", "verbs_conj3", None),

    # === verbs A2 — reflexius ===
    ("dir-se", "llamarse", "verbs_reflexius", None),
    ("llevar-se", "levantarse", "verbs_reflexius", None),
    ("dutxar-se", "ducharse", "verbs_reflexius", None),
    ("vestir-se", "vestirse", "verbs_reflexius", None),
    ("pentinar-se", "peinarse", "verbs_reflexius", None),
    ("afaitar-se", "afeitarse", "verbs_reflexius", None),
    ("rentar-se", "lavarse", "verbs_reflexius", None),
    ("asseure's", "sentarse", "verbs_reflexius", None),
    ("posar-se", "ponerse", "verbs_reflexius", None),
    ("despertar-se", "despertarse", "verbs_reflexius", None),
    ("adormir-se", "dormirse", "verbs_reflexius", None),
    ("casar-se", "casarse", "verbs_reflexius", None),
    ("divertir-se", "divertirse", "verbs_reflexius", None),
    ("trobar-se", "encontrarse (de salud)", "verbs_reflexius", None),
    ("queixar-se", "quejarse", "verbs_reflexius", None),
    ("oblidar-se", "olvidarse", "verbs_reflexius", None),
    ("recordar-se", "acordarse", "verbs_reflexius", None),
]


# ---------------------------------------------------------------------------
# CARD DATA — CLOZE
# ---------------------------------------------------------------------------
# Mix of pure drill cards + contextualised cards using philosophy/lit/art themes
# (Llull, Rodoreda, Borges, Tàpies, Dalí, Kant, Espriu, etc.)
CLOZE = [
    # === feines — descripcions (Anem per feina) ===
    ("{{c1::mestra}} → És una feina vocacional, exigent i molt gratificant.", "maestra", "feines"),
    ("{{c1::policia}} → És una feina arriscada, perillosa i força estressant.", "policía", "feines"),
    ("{{c1::metgessa}} → És una professió complexa, essencial i molt esgotadora.", "médica", "feines"),
    ("{{c1::cambrera}} → És un ofici ràpid, físic i sovint cansat.", "camarera", "feines"),
    ("{{c1::perruquera}} → És una feina creativa, social i molt minuciosa.", "peluquera", "feines"),
    ("{{c1::dependenta}} → És una feina dinàmica, comercial i atenta.", "dependienta", "feines"),
    ("{{c1::administratiu}} → És una tasca rutinària, organitzada i sedentària.", "administrativo", "feines"),
    ("{{c1::taxista}} → És un ofici independent, urbà i de vegades estressant.", "taxista", "feines"),
    ("{{c1::bomber}} → És una professió heroica, física i molt perillosa.", "bombero", "feines"),
    ("{{c1::paleta}} → És un ofici dur, manual i molt pràctic.", "albañil", "feines"),
    ("{{c1::electricista}} → És una feina tècnica, precisa i especialitzada.", "electricista", "feines"),

    # === demostratius (con cultura) ===
    ("{{c1::Aquest}} llibre és La plaça del Diamant, de Mercè Rodoreda.", "masc. sing. — proper", "demostratius"),
    ("{{c1::Aquell}} quadre és La persistència de la memòria, de Dalí.", "masc. sing. — llunyà", "demostratius"),
    ("{{c1::Aquests}} versos són de Salvador Espriu.", "masc. plural — proper", "demostratius"),
    ("{{c1::Aquells}} pensaments són de Ramon Llull al segle XIII.", "masc. plural — llunyà", "demostratius"),
    ("{{c1::Aquesta}} novel·la és Mirall trencat, de Rodoreda.", "fem. sing. — proper", "demostratius"),
    ("{{c1::Aquella}} obra és Camí de sirga, de Jesús Moncada.", "fem. sing. — llunyà", "demostratius"),
    ("{{c1::Aquestes}} pintures són d'Antoni Tàpies.", "fem. plural — proper", "demostratius"),
    ("{{c1::Aquelles}} escultures són de Joan Miró.", "fem. plural — llunyà", "demostratius"),
    ("{{c1::Aquell}} que escriu en català és Quim Monzó.", "masc. + que (sing.)", "demostratius"),
    ("{{c1::Aquells}} que pinten amb materials trobats són els pintors informalistes.", "masc. + que (plural)", "demostratius"),

    # === articles indefinits ===
    ("Al museu hi ha {{c1::un}} quadre de Picasso.", "indef. masc. sing.", "articles"),
    ("Al MNAC hi ha {{c1::una}} sala dedicada al romànic.", "indef. fem. sing.", "articles"),
    ("Llull va escriure {{c1::uns}} llibres de filosofia revolucionaris.", "indef. masc. plural", "articles"),
    ("Rodoreda va publicar {{c1::unes}} novel·les inoblidables.", "indef. fem. plural", "articles"),

    # === preposicions: en vs a ===
    ("Ramon Llull va néixer {{c1::a}} Mallorca al segle XIII.", "A = lloc concret", "preposicions"),
    ("Dalí pintava {{c1::a}} Portlligat, en un poble del Cap de Creus.", "A = lloc concret", "preposicions"),
    ("Espriu va viure {{c1::en}} un context d'opressió cultural.", "EN = context ampli / indefinit", "preposicions"),
    ("Picasso vivia {{c1::a}} París els anys vint.", "A = lloc concret", "preposicions"),
    ("Rodoreda escrivia {{c1::en}} unes condicions d'exili difícils.", "EN = context", "preposicions"),
    ("Borges treballava {{c1::a}} la Biblioteca Nacional de Buenos Aires.", "A = lloc concret", "preposicions"),

    # === "en" + "hi ha" → n'hi ha ===
    ("Hi ha llibres de Kant a la biblioteca? — Sí, {{c1::n'hi ha}} molts.", "resposta a pregunta amb quantitat indefinida", "nhiha"),
    ("Quants quadres de Miró hi ha al museu? — {{c1::N'hi ha}} quaranta.", "quantitat numèrica", "nhiha"),
    ("Hi ha pa amb tomàquet? — No, no {{c1::n'hi ha}}.", "forma negativa", "nhiha"),
    ("Filòsofs catalans contemporanis? {{c1::N'hi ha}} pocs però influents.", "quantitat indeterminada", "nhiha"),
    ("Vols més vermut? — Gràcies, ja {{c1::n'hi ha}} prou.", "quantitat suficient", "nhiha"),
    ("Hi ha obres de Tàpies aquí? — Sí, {{c1::n'hi ha}} tres.", "quantitat concreta", "nhiha"),

    # === conjuncions ===
    ("Llegeixo Borges {{c1::perquè}} m'apassiona la metafísica.", "causa", "conjuncions"),
    ("Estudio Kant {{c1::i}} Hegel a la vegada.", "suma", "conjuncions"),
    ("Tàpies pintava {{c1::quan}} sentia emocions fortes.", "temps", "conjuncions"),
    ("Plou, {{c1::així que}} em quedo a casa a llegir Espriu.", "conseqüència", "conjuncions"),
    ("M'agradaria llegir Wittgenstein, {{c1::però}} encara em falta nivell.", "oposició", "conjuncions"),
    ("{{c1::Com que}} avui plou, visitarem el museu en lloc de la platja.", "causa al començament", "conjuncions"),
    ("Llegeixo Dostoievski {{c1::mentre}} escolto música clàssica.", "temps simultani", "conjuncions"),
    ("Vols anar al MACBA {{c1::o}} al MNAC?", "alternativa", "conjuncions"),
    ("{{c1::Encara que}} no entengui tot, llegeixo en català.", "concessió", "conjuncions"),
    ("Estudio filosofia {{c1::per}} comprendre millor el món.", "finalitat (+ inf.)", "conjuncions"),
    ("Tradueixo Sartre {{c1::perquè}} els altres ho entenguin.", "finalitat (+ subj.)", "conjuncions"),
    ("{{c1::Primer de tot}} llegeixo el text, {{c2::després}} faig anotacions, {{c3::finalment}} l'analitzo.", "ordenar el discurs", "conjuncions"),

    # === imperfet — drill pur ===
    ("jo cant{{c1::ava}} (cantar)", "1a conj. -ar → V", "imperfet"),
    ("tu cant{{c1::aves}} (cantar)", "1a conj. -ar", "imperfet"),
    ("ell/ella cant{{c1::ava}} (cantar)", "1a conj. -ar", "imperfet"),
    ("nosaltres cant{{c1::àvem}} (cantar)", "1a conj. -ar", "imperfet"),
    ("vosaltres cant{{c1::àveu}} (cantar)", "1a conj. -ar", "imperfet"),
    ("ells/elles cant{{c1::aven}} (cantar)", "1a conj. -ar", "imperfet"),
    ("jo perd{{c1::ia}} (perdre)", "2a/3a conj. → I", "imperfet"),
    ("tu perd{{c1::ies}} (perdre)", "2a", "imperfet"),
    ("nosaltres perd{{c1::íem}} (perdre)", "2a", "imperfet"),
    ("jo dorm{{c1::ia}} (dormir)", "3a -ir → I", "imperfet"),
    ("nosaltres dorm{{c1::íem}} (dormir)", "3a", "imperfet"),
    ("ells dorm{{c1::ien}} (dormir)", "3a", "imperfet"),

    # === imperfet — temàtic (filosofia / literatura / art) ===
    ("Quan Ramon Llull {{c1::escrivia}} el Llibre d'amic e amat, vivia a Mallorca.", "imperfet de escriure", "imperfet"),
    ("Antoni Tàpies {{c1::pintava}} amb materials inesperats: sorra, terra, pols.", "imperfet de pintar", "imperfet"),
    ("Borges {{c1::llegia}} en moltes llengües des de molt jove.", "imperfet de llegir", "imperfet"),
    ("Mercè Rodoreda {{c1::escrivia}} a l'exili, a Ginebra.", "imperfet de escriure", "imperfet"),
    ("Picasso {{c1::vivia}} a París els anys vint.", "imperfet de viure", "imperfet"),
    ("Salvador Espriu {{c1::publicava}} poesia en català sota la dictadura.", "imperfet de publicar", "imperfet"),
    ("Kant {{c1::sortia}} a passejar cada dia a la mateixa hora.", "imperfet de sortir", "imperfet"),
    ("Joan Miró {{c1::treballava}} en silenci absolut al seu taller.", "imperfet de treballar", "imperfet"),
    ("Quan els filòsofs medievals {{c1::pensaven}} sobre Déu, ho feien en llatí.", "imperfet de pensar", "imperfet"),

    # === abans/ara — paral·lel amb cultura ===
    ("Abans, Sartre {{c1::escrivia}} obres de teatre.", "imperfet — passat habitual", "sabrina"),
    ("Ara, els filòsofs {{c1::escriuen}} sobretot articles acadèmics.", "present", "sabrina"),
    ("Abans, els llibres {{c1::costaven}} molts diners.", "imperfet", "sabrina"),
    ("Ara, els llibres {{c1::estan}} molt més a l'abast.", "present", "sabrina"),
    ("Abans la gent {{c1::llegia}} en silenci a les biblioteques.", "imperfet", "sabrina"),
    ("Ara molta gent {{c1::llegeix}} en mòbils i tauletes.", "present", "sabrina"),

    # === indicacions ===
    ("A la plaça, {{c1::gira}} a l'esquerra.", "imperatiu de girar", "indicacions"),
    ("Continua recte i {{c1::travessa}} el carrer.", "imperatiu de travessar", "indicacions"),
    ("{{c1::Camina}} dues illes i gira a la dreta.", "imperatiu de caminar", "indicacions"),
    ("El carrer {{c1::continua}} recte fins a la biblioteca.", "present de continuar", "indicacions"),

    # === actes socials — situació visible, frase oculta ===
    ("Naixement d'una criatura → {{c1::Enhorabona!}}", "felicitació general", "actes_socials"),
    ("Enterrament → {{c1::T'acompanyo en el sentiment}}", "condol", "actes_socials"),
    ("Ruptura sentimental → {{c1::Ho sento per tu}}", "consol", "actes_socials"),
    ("Aniversari → {{c1::Per molts anys!}}", "felicitació catalana clàssica", "actes_socials"),
    ("Casament → {{c1::Que sigueu molt feliços!}}", "felicitació nupcial", "actes_socials"),
    ("Nova feina o ascens → {{c1::T'ho mereixes!}}", "felicitació laboral", "actes_socials"),
    ("Algú malalt → {{c1::Que et milloris aviat}}", "desig de recuperació", "actes_socials"),
    ("Brindis → {{c1::Salut!}}", "brindis", "actes_socials"),
    ("Comiat → {{c1::Fins aviat}}", "comiat informal", "actes_socials"),
    ("Abans de menjar → {{c1::Bon profit!}}", "fórmula a taula", "actes_socials"),

    # === bar — frases per demanar ===
    ("Per a mi un cafè, {{c1::si us plau}}.", "fórmula de cortesia", "bar_frases"),
    ("Em pot {{c1::dur}} el compte, si us plau?", "verb dur = traer", "bar_frases"),
    ("Quin és el {{c1::plat del dia}}?", "demanar la recomanació", "bar_frases"),
    ("Pago {{c1::amb targeta}}, gràcies.", "forma de pagament", "bar_frases"),
    ("{{c1::Tot junt}}, si us plau.", "demanar un sol compte", "bar_frases"),
]


# ---------------------------------------------------------------------------
# IMAGE QUERY OVERRIDES — extends coverage for symptoms / verbs / abstract
# Maps catalan_word -> Unsplash/Pexels search query
# ---------------------------------------------------------------------------
IMAGE_OVERRIDES = {
    # --- Symptoms (visualizables) ---
    "mal de cap": "headache pain",
    "mal de panxa": "stomach pain woman",
    "mal d'estómac": "stomach ache",
    "mal d'esquena": "back pain",
    "mal de coll": "sore throat",
    "mal de queixal": "toothache",
    "mal d'orella": "ear pain",
    "punxada": "sharp chest pain",
    "cremor": "heartburn discomfort",
    "febre": "thermometer fever",
    "dècimes": "thermometer hand",
    "calfreds": "blanket cold shivering",
    "suor freda": "cold sweat forehead",
    "cansament": "tired exhausted person",
    "fatiga": "fatigue tired woman",
    "esgotament": "exhausted person work",
    "debilitat": "weak ill person",
    "mareig": "dizzy person headache",
    "vertigen": "vertigo dizziness",
    "desmai": "fainting collapse",
    "tos seca": "person coughing",
    "mocs": "tissue runny nose",
    "nas tapat": "blocked nose woman",
    "esternuts": "sneeze tissue",
    "ofec": "shortness of breath",
    "nàusees": "nausea sick person",
    "acidesa": "heartburn discomfort",
    "picor": "itching skin scratching",
    "erupció": "skin rash",
    "butllofes": "blister skin",
    "urticària": "skin hives",
    "inflor": "swollen ankle",
    "morat": "bruise skin",
    "insomni": "insomnia bed awake",
    "ansietat": "anxiety stressed person",
    "angoixa": "anguish worried face",
    "formigueig": "tingling hand",
    "rampes": "leg cramp",
    "tremolors": "shaking hands",

    # --- Verbs: NO photos — get surrealist category image instead ---

    # --- Feines (abstractes que faltaven) ---
    "administratiu": "office desk laptop",
    "cuidador": "caregiver elderly",
    "netejador": "janitor cleaning",

    # --- Formació ---
    "estudiant universitari": "university student campus",
    "diplomat universitari": "graduation diploma",
    "graduat universitari": "graduation ceremony",
    "acadèmic": "academic library books",
    "formació professional": "vocational training workshop",
    "curs superior": "university classroom",
    "curs formatiu": "workshop training",
    "educació obligatòria": "primary school classroom",

    # --- Historia (algunos visualizables) ---
    "treballadors": "factory workers vintage",
    "pagesos": "farmers field",
    "rei": "king crown",
    "fàbriques": "old factory chimney",
    "mines": "coal mine workers",
    "obrers": "workers factory",
    "drets": "human rights protest",
    "lluita": "protest fist",

    # --- Contracte (algunos) ---
    "jornada completa": "full time work",
    "jornada partida": "split shift clock",
    "hores extres": "overtime clock",
    "horari flexible": "flexible schedule",

    # --- Plans (faltaba uno) ---
    "anar a la piscina": "swimming pool day",
}


# ---------------------------------------------------------------------------
# IMAGE FETCHING — Unsplash → Pexels → Wikimedia fallback chain
# ---------------------------------------------------------------------------
def slugify(s):
    nfkd = unicodedata.normalize("NFKD", s.lower())
    ascii_str = "".join(c for c in nfkd if not unicodedata.combining(c))
    return "".join(c if c.isalnum() else "_" for c in ascii_str).strip("_")


def _fetch_url(url, headers=None, timeout=20):
    req = urllib.request.Request(url, headers={"User-Agent": UA, **(headers or {})})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


# --- Unsplash ---
def unsplash_search(query):
    if not UNSPLASH_KEY:
        return None
    url = (
        "https://api.unsplash.com/search/photos"
        f"?query={urllib.parse.quote(query)}&per_page=1&orientation=landscape"
        f"&client_id={UNSPLASH_KEY}"
    )
    try:
        data = json.loads(_fetch_url(url, {"Accept-Version": "v1"}).decode("utf-8"))
    except Exception as e:
        return ("ERROR", str(e))
    if not data.get("results"):
        return None
    p = data["results"][0]
    return {
        "source": "Unsplash",
        "url": p["urls"]["small"],
        "author": p["user"]["name"],
        "author_link": p["user"]["links"]["html"],
        "trigger_dl": p["links"]["download_location"],
    }


def unsplash_trigger_dl(endpoint):
    try:
        _fetch_url(f"{endpoint}&client_id={UNSPLASH_KEY}", {"Accept-Version": "v1"}, timeout=10)
    except Exception:
        pass


# --- Pexels ---
def pexels_search(query):
    if not PEXELS_KEY:
        return None
    url = (
        "https://api.pexels.com/v1/search"
        f"?query={urllib.parse.quote(query)}&per_page=1&orientation=landscape"
    )
    try:
        data = json.loads(
            _fetch_url(url, {"Authorization": PEXELS_KEY}).decode("utf-8")
        )
    except Exception as e:
        return ("ERROR", str(e))
    if not data.get("photos"):
        return None
    p = data["photos"][0]
    return {
        "source": "Pexels",
        "url": p["src"]["medium"],
        "author": p["photographer"],
        "author_link": p["photographer_url"],
        "trigger_dl": None,
    }


# --- Wikimedia Commons ---
def wikimedia_search(query):
    """Search Commons for a CC-licensed image. No API key required."""
    api = "https://commons.wikimedia.org/w/api.php"
    params = {
        "action": "query",
        "format": "json",
        "generator": "search",
        "gsrsearch": f"filetype:bitmap {query}",
        "gsrlimit": "1",
        "gsrnamespace": "6",
        "prop": "imageinfo",
        "iiprop": "url|extmetadata",
        "iiurlwidth": "640",
    }
    url = f"{api}?{urllib.parse.urlencode(params)}"
    try:
        data = json.loads(_fetch_url(url).decode("utf-8"))
    except Exception as e:
        return ("ERROR", str(e))
    pages = data.get("query", {}).get("pages", {})
    if not pages:
        return None
    page = next(iter(pages.values()))
    info = page.get("imageinfo", [{}])[0]
    img_url = info.get("thumburl") or info.get("url")
    if not img_url:
        return None
    meta = info.get("extmetadata", {})
    author = meta.get("Artist", {}).get("value", "Unknown")
    # Strip HTML
    import re
    author = re.sub(r"<[^>]+>", "", author).strip() or "Wikimedia Commons"
    return {
        "source": "Wikimedia",
        "url": img_url,
        "author": author,
        "author_link": "https://commons.wikimedia.org/wiki/" + page.get("title", ""),
        "trigger_dl": None,
    }


# --- OpenRouter image generation (Miró-style category images) ---
def openrouter_generate_image(prompt, out_path):
    """Generate an image via OpenRouter and save to out_path. Returns path or None."""
    if not OPENROUTER_KEY:
        return None
    body = json.dumps({
        "model": "google/gemini-2.5-flash-image",
        "messages": [{"role": "user", "content": prompt}],
        "modalities": ["image", "text"],
    }).encode("utf-8")
    req = urllib.request.Request(
        f"{OPENROUTER_BASE}/chat/completions",
        data=body,
        headers={
            "Authorization": f"Bearer {OPENROUTER_KEY}",
            "Content-Type": "application/json",
            "X-Title": "anki-deck-builder",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=180) as r:
            resp = json.loads(r.read().decode("utf-8"))
    except Exception as e:
        print(f"    OpenRouter error: {e}")
        return None
    msg = resp.get("choices", [{}])[0].get("message", {})
    imgs = msg.get("images") or []
    if not imgs:
        print(f"    OpenRouter returned no image (content: {str(msg.get('content', ''))[:100]})")
        return None
    url = imgs[0].get("image_url", {}).get("url", "")
    if not url.startswith("data:image"):
        return None
    import base64
    _, b64 = url.split(",", 1)
    out_path.write_bytes(base64.b64decode(b64))
    cost = resp.get("usage", {}).get("cost", 0)
    print(f"  [OK Miró] {out_path.name} (${cost:.4f})")
    return out_path


def fetch_category_image(category):
    """Return filename of cached Miró-style category image, or None."""
    prompt = CATEGORY_IMAGE_PROMPTS.get(category)
    if not prompt:
        return None
    target = MEDIA_DIR / f"_cat_{category}.png"
    if target.exists():
        return target.name
    print(f"  Generating Miró image for category '{category}'...")
    result = openrouter_generate_image(prompt, target)
    return target.name if result else None


# --- Fallback chain ---
def fetch_image(query, slug):
    """Returns (filename, author, source) or None. Caches to disk."""
    target = MEDIA_DIR / f"{slug}.jpg"
    credit_file = MEDIA_DIR / f"{slug}.credit.json"
    if target.exists() and credit_file.exists():
        c = json.loads(credit_file.read_text(encoding="utf-8"))
        return (target.name, c["author"], c.get("source", "Unsplash"))

    for fetcher_name, fetcher in [
        ("Unsplash", unsplash_search),
        ("Pexels", pexels_search),
        ("Wikimedia", wikimedia_search),
    ]:
        result = fetcher(query)
        if result is None:
            continue
        if isinstance(result, tuple) and result[0] == "ERROR":
            # rate limit or transient error — try next source
            print(f"    {fetcher_name}: {result[1][:60]}")
            continue
        try:
            img_bytes = _fetch_url(result["url"], timeout=30)
            target.write_bytes(img_bytes)
            credit_file.write_text(
                json.dumps({
                    "author": result["author"],
                    "link": result["author_link"],
                    "source": result["source"],
                }),
                encoding="utf-8",
            )
            if result.get("trigger_dl"):
                unsplash_trigger_dl(result["trigger_dl"])
            print(f"  [OK {result['source']}] {slug}.jpg ({result['author']})")
            return (target.name, result["author"], result["source"])
        except Exception as e:
            print(f"    download failed: {e}")
            continue
    print(f"  [MISS] no image for {slug} (query={query!r})")
    return None


# ---------------------------------------------------------------------------
# CSS — base + per-category badge colors
# ---------------------------------------------------------------------------
# Each category has a light bg + darker fg pair for the badge.
CATEGORY_COLORS = {
    # vocab — lugares físicos (azules/verdes)
    "equipaments":      ("#DBEAFE", "#1E40AF"),
    "via_publica":      ("#CCFBF1", "#115E59"),
    "placa":            ("#D1FAE5", "#065F46"),
    # vocab — gente / trabajo (naranjas/ámbar)
    "feines":           ("#FED7AA", "#9A3412"),
    "formacio":         ("#E0E7FF", "#3730A3"),
    "contracte":        ("#E2E8F0", "#334155"),
    # vocab — historia (ámbar)
    "historia":         ("#FEF3C7", "#92400E"),
    # vocab — gastronomía (rojos)
    "bar":              ("#FEE2E2", "#991B1B"),
    "parament":         ("#EDE9FE", "#5B21B6"),
    # vocab — salud
    "simptomes":        ("#FCE7F3", "#9D174D"),
    # vocab — ocio
    "plans":            ("#CFFAFE", "#155E75"),
    # verbs (rojos oscuros)
    "verbs_irregulars": ("#FECACA", "#7F1D1D"),
    "verbs_conj1":      ("#FECDD3", "#9F1239"),
    "verbs_conj2":      ("#FBCFE8", "#9D174D"),
    "verbs_conj3":      ("#F5D0FE", "#86198F"),
    "verbs_reflexius":  ("#FFE4E6", "#881337"),
    # gramatica (amarillos/oros)
    "demostratius":     ("#FEF08A", "#854D0E"),
    "articles":         ("#FDE68A", "#92400E"),
    "preposicions":     ("#FCD34D", "#78350F"),
    "imperfet":         ("#FDBA74", "#7C2D12"),
    "conjuncions":      ("#FCD34D", "#78350F"),
    "nhiha":            ("#FDE68A", "#854D0E"),
    # frases (violetas)
    "indicacions":      ("#DDD6FE", "#5B21B6"),
    "actes_socials":    ("#FBCFE8", "#9D174D"),
    "sabrina":          ("#E9D5FF", "#6B21A8"),
    "situar_se":        ("#C7D2FE", "#3730A3"),
    "bar_frases":       ("#FECACA", "#7F1D1D"),
}


def build_badge_css():
    rules = []
    for cat, (bg, fg) in CATEGORY_COLORS.items():
        rules.append(f".badge.{cat} {{ background:{bg}; color:{fg}; }}")
    return "\n".join(rules)


SHARED_CSS = """
.card {
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
  background: #FFFFFF;
  color: #1F2937;
  text-align: center;
  padding: 24px 20px 32px;
  position: relative;
  font-size: 18px;
}
.card.nightMode { background: #1F2937; color: #E5E7EB; }
.senyera {
  position: absolute; top: 0; left: 0; right: 0; height: 4px;
  background: linear-gradient(to right,
    #FFD43B 0 25%, #C8102E 25% 50%, #FFD43B 50% 75%, #C8102E 75% 100%);
  opacity: 0.85;
}
.badge {
  position: absolute; top: 14px; right: 14px;
  background: #E2EEEE; color: #4A7C7E;
  font-size: 11px; font-weight: 600;
  padding: 4px 10px; border-radius: 999px;
  letter-spacing: 0.04em; text-transform: lowercase;
}
""" + build_badge_css() + """
.card.nightMode .badge { filter: brightness(0.85) saturate(1.2); }
.word {
  font-family: Georgia, "Times New Roman", serif;
  font-size: 36px; font-weight: 600; line-height: 1.15;
  margin: 24px 0 0;
}
.translation {
  font-size: 22px; color: #6B7280; margin-top: 12px;
}
.card.nightMode .translation { color: #9CA3AF; }
.img-wrap { margin: 20px 0 8px; }
.img-wrap img {
  max-height: 200px; max-width: 90%;
  border-radius: 8px; box-shadow: 0 2px 8px rgba(0,0,0,0.15);
}
.img-wrap.miro img {
  max-height: 160px; max-width: 75%;
  border-radius: 12px;
  box-shadow: 0 2px 12px rgba(0,0,0,0.10);
  opacity: 0.92;
}
.divider {
  width: 60%; height: 1px; background: #E5E7EB; margin: 18px auto;
}
.card.nightMode .divider { background: #374151; }
.notes { margin-top: 14px; font-size: 13px; color: #6B7280; }
.card.nightMode .notes { color: #9CA3AF; }
.credit { font-size: 10px; color: #9CA3AF; margin-top: 12px; opacity: 0.8; }
.credit a { color: inherit; text-decoration: underline; }
.sentence {
  font-size: 22px; line-height: 1.5; max-width: 95%;
  margin: 24px auto 0; font-family: Georgia, serif;
}
.cloze {
  background: #FFF4C2; color: #1F2937;
  padding: 0 4px; border-radius: 3px; font-weight: 600;
  border-bottom: 2px dashed #C8102E;
}
.card.nightMode .cloze { background: #4A4020; color: #FFD43B; }
"""


# ---------------------------------------------------------------------------
# MODELS
# ---------------------------------------------------------------------------
# Helper template snippets — show Image if it exists, else CategoryImage.
# Anki's mustache supports {{^Field}}...{{/Field}} for "if NOT Field".
_VOCAB_IMG_BLOCK = (
    '{{#Image}}<div class="img-wrap">{{Image}}</div>{{/Image}}'
    '{{^Image}}{{#CategoryImage}}<div class="img-wrap miro">{{CategoryImage}}</div>{{/CategoryImage}}{{/Image}}'
)
_CLOZE_IMG_BLOCK = (
    '{{#CategoryImage}}<div class="img-wrap miro">{{CategoryImage}}</div>{{/CategoryImage}}'
)

VOCAB_MODEL = genanki.Model(
    MODEL_VOCAB_ID,
    "Catalan-Spanish Vocab",
    fields=[
        {"name": "Catalan"},
        {"name": "Spanish"},
        {"name": "Image"},
        {"name": "CategoryImage"},
        {"name": "Credit"},
        {"name": "Category"},
    ],
    templates=[
        {
            "name": "CA → ES",
            "qfmt": (
                '<div class="senyera"></div>'
                '{{#Category}}<span class="badge {{Category}}">{{Category}}</span>{{/Category}}'
                + _VOCAB_IMG_BLOCK +
                '<p class="word">{{Catalan}}</p>'
            ),
            "afmt": (
                '<div class="senyera"></div>'
                '{{#Category}}<span class="badge {{Category}}">{{Category}}</span>{{/Category}}'
                + _VOCAB_IMG_BLOCK +
                '<p class="word">{{Catalan}}</p>'
                '<div class="divider"></div>'
                '<p class="translation">{{Spanish}}</p>'
                '{{#Credit}}<p class="credit">{{Credit}}</p>{{/Credit}}'
            ),
        },
        {
            "name": "ES → CA",
            "qfmt": (
                '<div class="senyera"></div>'
                '{{#Category}}<span class="badge {{Category}}">{{Category}}</span>{{/Category}}'
                '<p class="word">{{Spanish}}</p>'
            ),
            "afmt": (
                '<div class="senyera"></div>'
                '{{#Category}}<span class="badge {{Category}}">{{Category}}</span>{{/Category}}'
                + _VOCAB_IMG_BLOCK +
                '<p class="word">{{Spanish}}</p>'
                '<div class="divider"></div>'
                '<p class="translation">{{Catalan}}</p>'
                '{{#Credit}}<p class="credit">{{Credit}}</p>{{/Credit}}'
            ),
        },
    ],
    css=SHARED_CSS,
)

CLOZE_MODEL = genanki.Model(
    MODEL_CLOZE_ID,
    "Catalan Cloze",
    fields=[
        {"name": "Text"},
        {"name": "Notes"},
        {"name": "CategoryImage"},
        {"name": "Category"},
    ],
    templates=[
        {
            "name": "Cloze",
            "qfmt": (
                '<div class="senyera"></div>'
                '{{#Category}}<span class="badge {{Category}}">{{Category}}</span>{{/Category}}'
                + _CLOZE_IMG_BLOCK +
                '<p class="sentence">{{cloze:Text}}</p>'
            ),
            "afmt": (
                '<div class="senyera"></div>'
                '{{#Category}}<span class="badge {{Category}}">{{Category}}</span>{{/Category}}'
                + _CLOZE_IMG_BLOCK +
                '<p class="sentence">{{cloze:Text}}</p>'
                '{{#Notes}}<p class="notes">{{Notes}}</p>{{/Notes}}'
            ),
        }
    ],
    css=SHARED_CSS,
    model_type=genanki.Model.CLOZE,
)


# ---------------------------------------------------------------------------
# BUILD
# ---------------------------------------------------------------------------
def main():
    deck = genanki.Deck(DECK_ID, "Catalan")
    media_files = []

    # Dedupe vocab by (Catalan word, Category) tuple
    seen = set()
    vocab_unique = []
    for v in VOCAB:
        key = (v[0], v[2])
        if key in seen:
            continue
        seen.add(key)
        vocab_unique.append(v)
    print(f"Vocab: {len(vocab_unique)} unique entries (from {len(VOCAB)})")

    # Identify categories that will need a Miró fallback (any note without image)
    cats_needing_fallback = set()
    # apply IMAGE_OVERRIDES first to get accurate count
    for catalan, _, category, query in vocab_unique:
        effective_query = query or IMAGE_OVERRIDES.get(catalan)
        if not effective_query:
            cats_needing_fallback.add(category)
    # all cloze categories always need fallback (cloze cards have no individual image)
    for _, _, category in CLOZE:
        cats_needing_fallback.add(category)

    print(f"\nPre-fetching Miró-style category images ({len(cats_needing_fallback)} cats)...")
    category_image_map = {}
    for cat in sorted(cats_needing_fallback):
        if cat not in CATEGORY_IMAGE_PROMPTS:
            print(f"  [SKIP] no prompt defined for category '{cat}'")
            continue
        fname = fetch_category_image(cat)
        if fname:
            category_image_map[cat] = fname
            media_files.append(str(MEDIA_DIR / fname))
        time.sleep(0.5)

    print(f"\nFetching individual images (Unsplash → Pexels → Wikimedia)...")
    image_count = 0
    miss_count = 0
    for catalan, spanish, category, query in vocab_unique:
        image_field = ""
        credit_field = ""
        # Apply override if no original query
        effective_query = query or IMAGE_OVERRIDES.get(catalan)
        if effective_query:
            slug = slugify(catalan)
            res = fetch_image(effective_query, slug)
            if res:
                fname, author, source = res
                image_field = f'<img src="{fname}">'
                credit_field = f"Foto: {author} / {source}"
                media_files.append(str(MEDIA_DIR / fname))
                image_count += 1
            else:
                miss_count += 1
            time.sleep(0.3)

        cat_img = category_image_map.get(category, "")
        cat_img_field = f'<img src="{cat_img}">' if cat_img else ""

        note = genanki.Note(
            model=VOCAB_MODEL,
            fields=[catalan, spanish, image_field, cat_img_field, credit_field, category],
            tags=[category],
        )
        deck.add_note(note)
    print(f"  -> {image_count} individual images, {miss_count} misses, {len(category_image_map)} Miró images cached")

    print(f"\nAdding {len(CLOZE)} cloze cards...")
    for text, notes, category in CLOZE:
        cat_img = category_image_map.get(category, "")
        cat_img_field = f'<img src="{cat_img}">' if cat_img else ""
        note = genanki.Note(
            model=CLOZE_MODEL,
            fields=[text, notes, cat_img_field, category],
            tags=[category],
        )
        deck.add_note(note)

    media_files = list(set(media_files))
    out = ROOT / "catalan_deck.apkg"
    genanki.Package(deck, media_files=media_files).write_to_file(str(out))
    print(f"\n[DONE] Wrote {out}")
    print(f"  - {len(deck.notes)} notes")
    print(f"  - {len(media_files)} media files")
    print(f"  - {len(CATEGORY_COLORS)} colored categories")


if __name__ == "__main__":
    main()
