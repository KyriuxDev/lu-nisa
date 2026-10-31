"""Traducción experimental al zapoteco de San Juan Jaltepec (di'dz xi'dza') con Gemma 4.

Cómo se evita que el modelo invente o se quede en bucle ("naxhi' naxhi'…"):
- Se traduce ORACIÓN POR ORACIÓN, en paralelo: los bucles salen en textos largos.
- A cada oración se le dan como modelo las oraciones del diccionario de Jaltepec que
  comparten palabras con ella (zapoteco ↔ español), y el vocabulario verificado de Jaltepec.
- Todo en UNA variante (Jaltepec) para no mezclar variantes.
- Si una oración sale repetitiva, se deja en español en vez de mostrar basura.

Las oraciones de ejemplo salen del PDF con scripts/extraer_ejemplos_jaltepec.py y no se
suben al repositorio (son del diccionario). Sin ese archivo, se traduce solo con el glosario.
"""

import asyncio
import json
import logging
import re
from functools import lru_cache
from pathlib import Path

from app import glosario, prompts
from app.llm import LLMError, LLMNoDisponible, Proveedor

log = logging.getLogger("lunisa.traduccion")

RUTA_EJEMPLOS = Path(__file__).resolve().parent / "data" / "ejemplos_jaltepec.json"
EJEMPLOS_POR_ORACION = 6

# Palabras que no ayudan a buscar ejemplos parecidos
VACIAS = set(
    """el la los las un una unos unas de del al a en y o que se es son por para con sin su sus tu tus mi mis
    lo le les me te nos este esta estos estas ese esa eso muy mas más pero como cuando ya no si sí hay
    también todo toda todos todas otro otra entre sobre hasta desde porque pues""".split()
)


@lru_cache
def ejemplos() -> list[dict]:
    if not RUTA_EJEMPLOS.exists():
        log.warning("No hay %s: se traduce solo con el glosario (corre scripts/extraer_ejemplos_jaltepec.py)", RUTA_EJEMPLOS)
        return []
    return json.loads(RUTA_EJEMPLOS.read_text(encoding="utf-8"))


def _raices(texto: str) -> set[str]:
    """Raíces simples (5 letras) de las palabras con contenido: 'frijoles' → 'frijo'.

    Se deshacen los cambios de raíz del español para que 'siembra' encuentre 'sembré' y
    'llueve' encuentre 'llover' (ie → e, ue → o).
    """
    palabras = re.findall(r"[a-zñ]+", glosario.normalizar(texto))
    return {p.replace("ie", "e").replace("ue", "o")[:5] for p in palabras if p not in VACIAS and len(p) > 2}


@lru_cache
def _indice() -> list[tuple[set[str], dict]]:
    return [(_raices(e["espanol"]), e) for e in ejemplos()]


def ejemplos_para(oracion: str, n: int = EJEMPLOS_POR_ORACION) -> list[dict]:
    """Las oraciones del diccionario que más palabras comparten con la oración."""
    buscadas = _raices(oracion)
    if not buscadas:
        return []
    puntuados = []
    for raices, e in _indice():
        comunes = len(buscadas & raices)
        if comunes:
            # Preferir ejemplos cortos: son más fáciles de imitar
            puntuados.append((comunes, -len(e["zapoteco"]), e))
    puntuados.sort(key=lambda t: (t[0], t[1]), reverse=True)
    return [e for _, _, e in puntuados[:n]]


def vocabulario_jaltepec(oracion: str) -> list[tuple[str, str]]:
    """(español, zapoteco de Jaltepec) de las palabras de la oración, para no mezclar variantes."""
    salida = []
    for p in glosario.palabras_en_texto(oracion):
        if p["variante"] == "jaltepec":
            salida.append((p["espanol"].lower(), p["zapoteco"]))
        for o in p["otras_variantes"]:
            if o["variante"] == "jaltepec":
                salida.append((p["espanol"].lower(), o["zapoteco"]))
    return salida


def dividir_oraciones(texto: str) -> list[str]:
    return [o for o in re.split(r"(?<=[.!?])\s+", " ".join(texto.split())) if o.strip()]


def limpiar(texto: str, minimo: int = 2) -> str | None:
    """Corta bucles ("naxhi' naxhi' naxhi'…"). None si no queda nada confiable."""
    texto = texto.strip().strip('"').splitlines()[0] if texto.strip() else ""
    palabras = texto.split()
    claves = [re.sub(r"[^\w']", "", p.lower()) for p in palabras]
    for i in range(len(claves)):
        for largo in (1, 2, 3):
            trozo = claves[i : i + largo]
            if (
                len(trozo) == largo
                and all(trozo)
                and claves[i + largo : i + 2 * largo] == trozo
                and claves[i + 2 * largo : i + 3 * largo] == trozo
            ):
                palabras, claves = palabras[:i], claves[:i]
                break
        else:
            continue
        break
    utiles = [c for c in claves if c]
    if len(utiles) < minimo or (len(utiles) >= 4 and len(set(utiles)) / len(utiles) < 0.5):
        return None
    return " ".join(palabras).rstrip(" ,;")


def armar_prompt(oracion: str) -> tuple[str, int]:
    muestras = ejemplos_para(oracion)
    vocab = vocabulario_jaltepec(oracion)
    bloque_ejemplos = "\n".join(f"- {e['espanol']} → {e['zapoteco']}" for e in muestras) or "- (no hay ejemplos parecidos)"
    bloque_vocab = "\n".join(f"- {es} = {z}" for es, z in vocab) or "- (ninguna)"
    prompt = prompts.PROMPT_TRADUCIR.format(ejemplos=bloque_ejemplos, vocabulario=bloque_vocab, texto=oracion)
    return prompt, len(muestras)


async def _traducir_oracion(llm: Proveedor, oracion: str) -> tuple[str | None, int]:
    prompt, n = armar_prompt(oracion)
    texto = await llm.generar(prompt, sistema=prompts.SISTEMA_TRADUCIR, pensar_minimo=True, max_tokens=120)
    return limpiar(texto), n


async def traducir(proveedores: dict[str, Proveedor], preferido: str, texto: str) -> dict:
    """Traduce oración por oración con el preferido; si no responde, con el local."""
    oraciones = dividir_oraciones(texto)
    llm = proveedores.get(preferido) or proveedores["ollama"]
    respaldo = None if llm.nombre == preferido else "sin_api_key"

    async def con(proveedor: Proveedor):
        return await asyncio.gather(*(_traducir_oracion(proveedor, o) for o in oraciones))

    try:
        resultados = await con(llm)
    except (LLMNoDisponible, LLMError) as e:
        if llm.nombre == "ollama":
            raise
        log.warning("Gemini falló al traducir, uso Ollama: %s", e)
        respaldo = "sin_conexion" if isinstance(e, LLMNoDisponible) else "error_gemini"
        llm = proveedores["ollama"]
        resultados = await con(llm)

    partes = [{"espanol": o, "zapoteco": z} for o, (z, _) in zip(oraciones, resultados)]
    traducidas = [p for p in partes if p["zapoteco"]]
    return {
        "oraciones": partes,
        "traduccion": " ".join(p["zapoteco"] for p in traducidas),
        # Confiable si salió al menos la mitad de las oraciones
        "confiable": bool(traducidas) and len(traducidas) * 2 >= len(partes),
        "ejemplos_usados": sum(n for _, n in resultados),
        "proveedor": llm,
        "respaldo": respaldo,
    }
