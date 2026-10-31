"""Revisión de un cultivo por foto con Gemma 4 (visión).

Dice cómo se ve la planta (qué cultivo parece, en qué etapa va y su estado general) y,
si hay daño, los síntomas y las POSIBLES causas (plagas, ácaros, hongos, nutrientes, clima).

El modelo solo describe lo que se ve. Nunca recomienda productos, dosis ni tratamientos:
los pasos a seguir son fijos y seguros, y los arma este código.
"""

import logging
from typing import Literal

from pydantic import BaseModel, ConfigDict, field_validator

from app.llm import Proveedor, extraer_json

log = logging.getLogger("lunisa.cultivo")

MAX_INTENTOS = 2
MAX_SINTOMAS = 4
MAX_CAUSAS = 3

Confianza = Literal["baja", "media", "alta"]
TipoCausa = Literal["insecto", "acaro", "hongo", "bacteria_o_virus", "falta_de_nutrientes", "clima", "otro"]
Etapa = Literal["plantula", "crecimiento", "floracion", "fruto", "madurez", "no_determinable"]
Estado = Literal["sano", "problemas_leves", "problemas_serios", "no_determinable"]


class CultivoInvalido(ValueError):
    """El modelo no devolvió un JSON válido tras MAX_INTENTOS."""


def _recortar(texto: str, palabras: int) -> str:
    p = texto.split()
    return " ".join(p[:palabras]) + ("…" if len(p) > palabras else "")


class Causa(BaseModel):
    model_config = ConfigDict(extra="ignore")

    nombre: str
    tipo: TipoCausa
    confianza: Confianza
    # Qué se ve en la foto que lo sugiere
    senales: str

    @field_validator("senales")
    @classmethod
    def corta(cls, v: str) -> str:
        return _recortar(v, 20)


class CultivoAnalisis(BaseModel):
    model_config = ConfigDict(extra="ignore")

    es_planta: bool
    cultivo_visto: str | None = None
    etapa: Etapa
    estado_general: Estado
    sintomas: list[str]
    posibles_causas: list[Causa]
    confianza: Confianza
    observaciones: str

    @field_validator("sintomas")
    @classmethod
    def pocos_sintomas(cls, v: list[str]) -> list[str]:
        return [_recortar(s, 12) for s in v if s.strip()][:MAX_SINTOMAS]

    @field_validator("posibles_causas")
    @classmethod
    def pocas_causas(cls, v: list[Causa]) -> list[Causa]:
        return v[:MAX_CAUSAS]

    @field_validator("observaciones")
    @classmethod
    def obs_corta(cls, v: str) -> str:
        return _recortar(v, 30)


SISTEMA = """Eres un observador de fotos de cultivos de la Sierra Norte de Oaxaca (por ejemplo maíz, frijol,
café, chile, calabaza, tomate, aguacate, durazno, manzana, trigo, plátano, caña o palmas).
Describes SOLO lo que se ve en la foto: qué cultivo parece, en qué etapa va, cómo se ve su salud y,
si tiene daño, sus POSIBLES causas. No eres un laboratorio: nunca das un diagnóstico seguro.

PROHIBIDO: recomendar productos químicos o naturales, marcas, dosis, mezclas o tratamientos.
Si te sientes tentado a hacerlo, no lo hagas.

Responde ÚNICAMENTE con un objeto JSON, sin texto antes ni después."""

PROMPT = """{pista}Observa la foto y responde con este JSON (mismas claves):

{{
  "es_planta": true | false,
  "cultivo_visto": "nombre común del cultivo en español, o null si no se reconoce",
  "etapa": "plantula" | "crecimiento" | "floracion" | "fruto" | "madurez" | "no_determinable",
  "estado_general": "sano" | "problemas_leves" | "problemas_serios" | "no_determinable",
  "sintomas": ["daños o señales que se ven, en palabras sencillas, máximo 12 palabras cada uno"],
  "posibles_causas": [
    {{
      "nombre": "nombre común en México (ej. gusano cogollero, roya del café, araña roja, ácaro)",
      "tipo": "insecto" | "acaro" | "hongo" | "bacteria_o_virus" | "falta_de_nutrientes" | "clima" | "otro",
      "confianza": "baja" | "media" | "alta",
      "senales": "qué se ve en la foto que lo sugiere"
    }}
  ],
  "confianza": "baja" | "media" | "alta",
  "observaciones": "cómo se ve el cultivo en general, en español sencillo, máximo 30 palabras"
}}

Reglas:
- Si la foto no muestra una planta, es_planta=false y las listas vacías.
- Si la planta se ve sana, estado_general="sano" y sintomas y posibles_causas vacías.
- Máximo 4 síntomas y 3 posibles causas, de la más probable a la menos probable.
- Los ácaros (como la araña roja) casi no se ven en una foto: si ves manchitas amarillas o puntitos
  en las hojas, considéralos como posible causa con tipo "acaro".
- Usa nombres comunes en México, sin nombres científicos.
- Si la foto está borrosa, lejana u oscura, usa "no_determinable" y confianza "baja".
- No recomiendes ningún producto ni tratamiento."""

CORRECCION = """Tu respuesta anterior no fue válida. Error: {error}
Responde de nuevo SOLO con el objeto JSON, con las claves y valores permitidos."""


async def analizar_con(llm: Proveedor, jpeg: bytes, cultivo: str | None) -> tuple[CultivoAnalisis, int]:
    """Pide el análisis a un proveedor; reintenta una vez si la respuesta no es válida."""
    pista = f"El campesino dice que el cultivo es: {cultivo}.\n\n" if cultivo else ""
    prompt = PROMPT.format(pista=pista)
    error = ""
    for intento in range(1, MAX_INTENTOS + 1):
        # pensar_minimo: sin esto Gemma 4 razona tanto que Gemini corta a los 30 s (ReadTimeout)
        texto = await llm.generar(
            prompt, sistema=SISTEMA, imagen=jpeg, json_mode=True, pensar_minimo=True, max_tokens=800
        )
        try:
            return CultivoAnalisis.model_validate(extraer_json(texto)), intento
        except ValueError as e:
            error = str(e)
            log.warning("[%s] intento %d inválido: %s | respuesta: %r", llm.nombre, intento, error, texto[:300])
            prompt = PROMPT.format(pista=pista) + "\n\n" + CORRECCION.format(error=error)
    raise CultivoInvalido(f"{llm.nombre} no devolvió un JSON válido tras {MAX_INTENTOS} intentos: {error}")


AVISO = (
    "Esto no es un diagnóstico: es lo que se alcanza a ver en la foto. Antes de aplicar cualquier producto, "
    "confírmalo con un técnico agrícola o con alguien con experiencia en tu comunidad."
)

# Pasos seguros y fijos; ninguno recomienda productos ni dosis
PASOS_GENERALES = [
    "Revisa también el revés de las hojas y otras plantas cercanas para ver si el daño se repite.",
    "Toma otra foto de cerca, con buena luz, en unos días para ver si avanza.",
]
PASOS_POR_TIPO = {
    "insecto": "Busca los insectos temprano en la mañana o al atardecer, cuando se mueven más.",
    "acaro": "Los ácaros son muy pequeños: revisa el revés de las hojas con una lupa o sacude una hoja sobre un papel blanco.",
    "hongo": "Si hay plantas muy dañadas, sepáralas o retíralas para que no contagien a las demás.",
    "bacteria_o_virus": "Si hay plantas muy dañadas, sepáralas o retíralas para que no contagien a las demás.",
    "falta_de_nutrientes": "Fíjate si el daño empieza en las hojas de abajo (viejas) o en las de arriba (nuevas).",
    "clima": "Anota si hubo helada, granizo, mucho sol o mucha agua en los últimos días.",
}
PASO_FINAL = "Lleva una muestra (una hoja o la planta) a un técnico agrícola antes de aplicar cualquier producto."
PASO_SANO = "Tu cultivo se ve sano en la foto. Sigue revisándolo cada semana."
PASO_SIN_PLANTA = "Toma una foto de cerca de la planta o de la hoja, con buena luz."


def pasos_seguros(a: CultivoAnalisis) -> list[str]:
    if not a.es_planta:
        return [PASO_SIN_PLANTA]
    if a.estado_general == "sano" and not a.posibles_causas:
        return [PASO_SANO]
    pasos = list(PASOS_GENERALES)
    for tipo in dict.fromkeys(c.tipo for c in a.posibles_causas):  # sin repetir, en orden
        paso = PASOS_POR_TIPO.get(tipo)
        if paso and paso not in pasos:
            pasos.append(paso)
    pasos.append(PASO_FINAL)
    return pasos


def texto_para_glosario(a: CultivoAnalisis) -> str:
    """Todo el texto del análisis, para buscar palabras con traducción al zapoteco."""
    partes = [a.cultivo_visto or "", *a.sintomas, a.observaciones]
    partes += [f"{c.nombre}. {c.senales}" for c in a.posibles_causas]
    return ". ".join(p for p in partes if p)
