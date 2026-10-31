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


def _alineado(texto: str) -> str:
    """Como normalizar(), pero con el mismo largo que el texto para poder reemplazar por posición."""
    salida = []
    for c in texto:
        n = normalizar(c)
        salida.append(n if len(n) == 1 else c)
    return "".join(salida)


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
        if campo == "espanol":
            formas = p["terminos"]
        else:
            # alias_voz: cómo transcribe el teléfono la palabra al dictarla ("shiah" → "chía")
            formas = [p["zapoteco"], *p.get("alias_voz", [])]
        for forma in formas:
            # Las palabras zapotecas muy cortas ("Gú", "Yí", "Bi") darían falsos positivos en español
            if campo == "zapoteco" and len(normalizar(forma)) < 3:
                continue
            sensible = campo == "espanol" and forma.lower() in SENSIBLES_A_ACENTO
            base = forma.lower() if sensible else normalizar(forma)
            base = base.strip("¿?¡! ")
            # Plural sencillo: lluvia → lluvias, frijol → frijoles
            sufijo = r"(?:e?s)?" if campo == "espanol" else ""
            salida.append((re.compile(rf"(?<!\w){re.escape(base)}{sufijo}(?!\w)"), sensible, p))
    # Las formas largas primero: "chile verde" antes que "chile"
    return sorted(salida, key=lambda t: -len(t[0].pattern))


def _coincidencias(texto: str, campo: str, solo_respuesta: bool) -> list[tuple[int, int, dict]]:
    """Todas las coincidencias sin traslaparse, en orden: (inicio, fin, entrada)."""
    texto = unicodedata.normalize("NFC", texto)
    minus, norm = texto.lower(), _alineado(texto)
    tomadas: list[tuple[int, int, dict]] = []
    for patron, sensible, p in _patrones(campo):
        if solo_respuesta and not p.get("buscar_en_respuesta", True):
            continue
        for m in patron.finditer(minus if sensible else norm):
            if all(m.end() <= a or m.start() >= b for a, b, _ in tomadas):
                tomadas.append((m.start(), m.end(), p))
    return sorted(tomadas, key=lambda t: t[0])


def _salida(p: dict) -> dict:
    return {"espanol": p["espanol"], "zapoteco": p["zapoteco"], "categoria": p["categoria"]}


def _unicas(coincidencias: list[tuple[int, int, dict]]) -> list[dict]:
    vistas, salida = set(), []
    for _, _, p in coincidencias:
        if p["espanol"] not in vistas:
            vistas.add(p["espanol"])
            salida.append(_salida(p))
    return salida


def palabras_en_texto(texto: str) -> list[dict]:
    """Palabras del glosario que aparecen (en español) en la respuesta del modelo."""
    return _unicas(_coincidencias(texto, "espanol", solo_respuesta=True))


def zapoteco_en_pregunta(texto: str) -> list[dict]:
    """Palabras zapotecas que el campesino usó al preguntar."""
    return _unicas(_coincidencias(texto, "zapoteco", solo_respuesta=False))


def _en_espanol(p: dict) -> str:
    """'¿Cuándo?' → 'cuándo', 'Semillas/pepitas' → 'semillas'."""
    if p["espanol"] == "Saludo general":
        return "hola"
    return p["espanol"].split("/")[0].strip("¿?¡! ").lower()


def traducir_pregunta(texto: str) -> str:
    """Cambia las palabras zapotecas por su significado: '¿Bata siembro dháh?' → '¿cuándo siembro frijol?'."""
    texto = unicodedata.normalize("NFC", texto)
    partes, pos = [], 0
    for ini, fin, p in _coincidencias(texto, "zapoteco", solo_respuesta=False):
        partes += [texto[pos:ini], _en_espanol(p)]
        pos = fin
    partes.append(texto[pos:])
    return "".join(partes)


def segmentos_respuesta(texto: str) -> list[dict]:
    """La respuesta en trozos para mostrar el zapoteco dentro de la frase.

    [{"texto": "El ", "zapoteco": None}, {"texto": "frijol", "zapoteco": "Dháh"}, ...]
    Solo se marca la primera vez que aparece cada palabra, para que se lea fácil.
    """
    texto = unicodedata.normalize("NFC", texto)
    segmentos, pos, vistas = [], 0, set()
    for ini, fin, p in _coincidencias(texto, "espanol", solo_respuesta=True):
        if p["espanol"] in vistas:
            continue
        vistas.add(p["espanol"])
        if ini > pos:
            segmentos.append({"texto": texto[pos:ini], "zapoteco": None})
        segmentos.append({"texto": texto[ini:fin], "zapoteco": p["zapoteco"]})
        pos = fin
    if pos < len(texto):
        segmentos.append({"texto": texto[pos:], "zapoteco": None})
    return segmentos
