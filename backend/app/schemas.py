from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.cultivo import CultivoAnalisis

MAX_PALABRAS_OBSERVACIONES = 25


class ParcelaAnalisis(BaseModel):
    """Atributos observables de la foto. Nada de fertilidad, nutrientes ni pH."""

    model_config = ConfigDict(extra="forbid")

    es_parcela: bool
    suelo_desnudo: bool | Literal["no_determinable"]
    humedad_aparente: Literal["seca", "humeda", "encharcada", "no_determinable"]
    pendiente: Literal["plana", "moderada", "fuerte", "no_determinable"]
    piedras: Literal["pocas", "muchas", "no_determinable"]
    cobertura_vegetal: Literal["nula", "parcial", "total"]
    # Informativo: se devuelve pero ninguna lógica lo usa
    confianza: Literal["baja", "media", "alta"]
    observaciones: str

    @field_validator("observaciones")
    @classmethod
    def recortar_observaciones(cls, v: str) -> str:
        # Se recorta en vez de rechazar: no vale la pena reintentar por esto
        palabras = v.split()
        if len(palabras) > MAX_PALABRAS_OBSERVACIONES:
            return " ".join(palabras[:MAX_PALABRAS_OBSERVACIONES]) + "…"
        return " ".join(palabras)


class AnalisisRespuesta(BaseModel):
    analisis: ParcelaAnalisis
    # true cuando respondió el modelo local, que no distingue bien la humedad
    humedad_preguntar_usuario: bool
    # Por qué se usó el respaldo local (None si respondió el proveedor preferido)
    respaldo: Literal["sin_conexion", "error_gemini", "respuesta_invalida", "sin_api_key"] | None
    proveedor: str
    modelo: str
    intentos: int
    latencia_ms: int


class DatoRegla(BaseModel):
    valor: str | int | float | bool
    # foto → "se ve", campesino → "nos dijiste", datos → históricos del municipio
    fuente: Literal["foto", "campesino", "datos"]


class Siembra(BaseModel):
    """Fecha de siembra del cultivo; con esto el backend arma la razón (no el modelo)."""

    meses: str = Field(min_length=1)  # "junio-julio"
    se_siembra_este_mes: bool
    # Lluvia total del mes, promedio histórico (mm)
    lluvia_meses_siembra_mm: float | None = None
    lluvia_mes_actual_mm: float | None = None
    agua_cultivo: Literal["bajo", "medio", "alto"] | None = None


class ExplicarEntrada(BaseModel):
    municipio: str = Field(min_length=1)
    cultivo: str = Field(min_length=1)
    puntaje: int = Field(ge=0, le=100)
    # Mes en que se hace la consulta (ej. "octubre"), para distinguirlo de la fecha de siembra
    mes_actual: str | None = None
    siembra: Siembra | None = None
    datos_regla: dict[str, DatoRegla] = {}


class ExplicarRespuesta(BaseModel):
    explicacion: str
    # Por qué se usó Ollama en vez del proveedor preferido (None si respondió el preferido)
    respaldo: Literal["sin_conexion", "error_gemini", "respuesta_invalida", "sin_api_key"] | None
    proveedor: str
    modelo: str
    latencia_ms: int


Respaldo = Literal["sin_conexion", "error_gemini", "respuesta_invalida", "sin_api_key", "mas_rapido_local"] | None


class PreguntarEntrada(BaseModel):
    # Texto que transcribió el teléfono (reconocimiento de voz) o que escribió el campesino
    texto: str = Field(min_length=1, max_length=500)
    municipio: str | None = None
    # 1-12; si no viene, el mes actual
    mes: int | None = Field(default=None, ge=1, le=12)


class OtraVariante(BaseModel):
    zapoteco: str
    variante: str


class PalabraZapoteca(BaseModel):
    espanol: str
    zapoteco: str
    categoria: str
    # sierra_norte (vocabulario del equipo) | jaltepec (diccionario INPI); son variantes distintas
    variante: str = "sierra_norte"
    otras_variantes: list[OtraVariante] = []


class Segmento(BaseModel):
    texto: str
    # Traducción al zapoteco de este trozo (None si es texto normal)
    zapoteco: str | None


class PreguntarRespuesta(BaseModel):
    respuesta: str
    # La misma respuesta en trozos, para mostrar el zapoteco dentro de la frase
    respuesta_segmentos: list[Segmento]
    # La pregunta con las palabras zapotecas cambiadas a español (None si no tenía)
    pregunta_traducida: str | None
    # Palabras de la respuesta que tienen traducción en el glosario (las pone el código, no el modelo)
    zapoteco: list[PalabraZapoteca]
    # Palabras zapotecas que reconocimos en la pregunta
    zapoteco_pregunta: list[PalabraZapoteca]
    saludo: str
    despedida: str
    municipio: str | None
    respaldo: Respaldo
    proveedor: str
    modelo: str
    latencia_ms: int


class TraducirEntrada(BaseModel):
    texto: str = Field(min_length=1, max_length=600)


class TraducirRespuesta(BaseModel):
    traduccion: str
    # false si el modelo se quedó repitiendo palabras y no se pudo rescatar nada
    confiable: bool = True
    # Siempre true: es traducción automática, no revisada por un hablante
    experimental: bool = True
    aviso: str
    # Palabras del glosario verificado que se le dieron al modelo como guía
    vocabulario_usado: list[PalabraZapoteca]
    respaldo: Respaldo
    proveedor: str
    modelo: str
    latencia_ms: int


class CultivoRespuesta(BaseModel):
    analisis: CultivoAnalisis
    # Pasos seguros armados por el código (nunca productos ni dosis)
    pasos: list[str]
    aviso: str
    zapoteco: list[PalabraZapoteca]
    # true si respondió el modelo local, que es menos confiable para esto
    modelo_local: bool
    respaldo: Respaldo
    proveedor: str
    modelo: str
    intentos: int
    latencia_ms: int
