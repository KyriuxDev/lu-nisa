"""Vocabulario zapoteco de la Sierra Norte.

El modelo responde en español y las palabras zapotecas las pone este código,
sacadas de un glosario verificado. Así Gemma nunca inventa zapoteco.

Fuente: https://dev-deivis.github.io/vocabulario_zapoteco/
"""

import json
import re
import unicodedata
from functools import lru_cache
from pathlib import Path

RUTA = Path(__file__).resolve().parent / "data" / "glosario.json"

# Sin acentos chocarían con otra palabra (papa ≠ papá)
SENSIBLES_A_ACENTO = {"papa"}

SALUDO = "Padiuxi"
DESPEDIDA = "Kixarubalo"


def normalizar(texto: str) -> str:
    """Minúsculas y sin acentos."""
    sin_acentos = unicodedata.normalize("NFD", texto.lower())
    return "".join(c for c in sin_acentos if unicodedata.category(c) != "Mn")


@lru_cache
def cargar() -> list[dict]:
    """Solo las palabras que ya tienen traducción confirmada."""
    datos = json.loads(RUTA.read_text(encoding="utf-8"))
    return [p for p in datos["palabras"] if p["zapoteco"]]


@lru_cache
def _patrones(campo: str) -> list[tuple[re.Pattern, bool, dict]]:
    """(regex, sensible_a_acento, entrada) para buscar por español o por zapoteco."""
    salida = []
    for p in cargar():
        formas = p["terminos"] if campo == "espanol" else [p["zapoteco"]]
        if campo == "zapoteco":
            # Palabras muy cortas ("Gú", "Yí") o saludos darían falsos positivos en español
            if not p.get("buscar_en_respuesta", True) or len(normalizar(p["zapoteco"])) < 3:
                continue
        for forma in formas:
            sensible = campo == "espanol" and forma.lower() in SENSIBLES_A_ACENTO
            base = forma.lower() if sensible else normalizar(forma)
            # Plural sencillo: lluvia → lluvias, frijol → frijoles
            sufijo = r"(?:e?s)?" if campo == "espanol" else ""
            salida.append((re.compile(rf"(?<!\w){re.escape(base)}{sufijo}(?!\w)"), sensible, p))
    # Las formas largas primero: "chile verde" antes que "chile"
    return sorted(salida, key=lambda t: -len(t[0].pattern))


def _buscar(texto: str, campo: str, solo_respuesta: bool) -> list[dict]:
    minus, norm = texto.lower(), normalizar(texto)
    encontradas, vistas = [], set()
    for patron, sensible, p in _patrones(campo):
        if solo_respuesta and not p.get("buscar_en_respuesta", True):
            continue
        if p["espanol"] in vistas:
            continue
        coincidencia = patron.search(minus if sensible else norm)
        if coincidencia:
            vistas.add(p["espanol"])
            encontradas.append(
                (coincidencia.start(), {"espanol": p["espanol"], "zapoteco": p["zapoteco"], "categoria": p["categoria"]})
            )
    # En el orden en que aparecen en el texto
    return [p for _, p in sorted(encontradas, key=lambda t: t[0])]


def palabras_en_texto(texto: str) -> list[dict]:
    """Palabras del glosario que aparecen (en español) en la respuesta del modelo."""
    return _buscar(texto, "espanol", solo_respuesta=True)


def zapoteco_en_pregunta(texto: str) -> list[dict]:
    """Palabras zapotecas que el campesino usó al preguntar, para traducírselas al modelo."""
    return _buscar(texto, "zapoteco", solo_respuesta=False)
