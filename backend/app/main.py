import io
import logging
import re
import time
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, File, HTTPException, Request, UploadFile
from PIL import Image, ImageOps, UnidentifiedImageError
from pydantic import ValidationError

from datetime import datetime

from app import config, contexto, glosario, prompts
from app.razones import frase_siembra
from app.llm import LLMError, LLMNoDisponible, Proveedor, crear_proveedores, extraer_json
from app.schemas import (
    AnalisisRespuesta,
    ExplicarEntrada,
    ExplicarRespuesta,
    ParcelaAnalisis,
    PreguntarEntrada,
    PreguntarRespuesta,
    TraducirEntrada,
    TraducirRespuesta,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("lunisa")

FORMATOS_PERMITIDOS = {"JPEG", "PNG", "WEBP"}
MAX_INTENTOS = 2  # el primero + un reintento
FRASE_FUENTE = {"foto": "se ve en la foto", "campesino": "nos lo dijo el campesino", "datos": "datos del municipio"}


class RespuestaInvalida(Exception):
    """El modelo no devolvió un JSON válido tras MAX_INTENTOS."""


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Falla al arrancar (no en la primera petición) si la config es inválida
    app.state.proveedores = crear_proveedores()
    log.info("Proveedores: %s", {n: p.modelo for n, p in app.state.proveedores.items()})
    log.info("Análisis → %s | Explicar → %s", config.PROVEEDOR_ANALISIS, config.PROVEEDOR_EXPLICAR)
    yield


app = FastAPI(title="Lu-nisa backend", version="0.2.0", lifespan=lifespan)


def obtener_proveedores(request: Request) -> dict[str, Proveedor]:
    return request.app.state.proveedores


def ms_desde(inicio: float) -> int:
    return round((time.perf_counter() - inicio) * 1000)


def preparar_imagen(datos: bytes) -> bytes:
    """Valida que sea jpeg/png/webp y la reduce a LADO_MAX_IMAGEN px como JPEG."""
    try:
        img = Image.open(io.BytesIO(datos))
        formato = img.format
        img.load()
    except (UnidentifiedImageError, OSError):
        raise HTTPException(415, {"error": "imagen_invalida", "detalle": "No se pudo leer el archivo como imagen"})
    if formato not in FORMATOS_PERMITIDOS:
        raise HTTPException(415, {"error": "formato_no_soportado", "detalle": f"{formato}; usa jpeg, png o webp"})

    # Las fotos de celular traen la rotación en EXIF
    img = ImageOps.exif_transpose(img).convert("RGB")
    img.thumbnail((config.LADO_MAX_IMAGEN, config.LADO_MAX_IMAGEN))
    salida = io.BytesIO()
    img.save(salida, format="JPEG", quality=85)
    return salida.getvalue()


def errores_llm(e: Exception) -> HTTPException:
    if isinstance(e, LLMNoDisponible):
        return HTTPException(503, {"error": "llm_no_disponible", "detalle": str(e)})
    return HTTPException(502, {"error": "llm_error", "detalle": str(e)})


@app.get("/variantes")
async def variantes_zapoteco():
    """Nombre y fuente de cada variante del zapoteco que usa el glosario."""
    return glosario.variantes()


@app.get("/salud")
async def salud(proveedores: dict[str, Proveedor] = Depends(obtener_proveedores)):
    return {
        "analisis": config.PROVEEDOR_ANALISIS,
        "explicar": config.PROVEEDOR_EXPLICAR,
        "proveedores": {n: await p.salud() for n, p in proveedores.items()},
    }


async def analizar_con(llm: Proveedor, jpeg: bytes) -> tuple[ParcelaAnalisis, int]:
    """Pide el análisis a un proveedor; reintenta una vez si la respuesta no es válida."""
    prompt = prompts.PROMPT_PARCELA
    error = ""
    for intento in range(1, MAX_INTENTOS + 1):
        texto = await llm.generar(prompt, sistema=prompts.SISTEMA_PARCELA, imagen=jpeg, json_mode=True)
        try:
            return ParcelaAnalisis.model_validate(extraer_json(texto)), intento
        except ValueError as e:
            # ValidationError y json.JSONDecodeError heredan de ValueError
            error = str(e)
            log.warning("[%s] intento %d inválido: %s | respuesta: %r", llm.nombre, intento, error, texto[:300])
            prompt = prompts.PROMPT_PARCELA + "\n\n" + prompts.PROMPT_CORRECCION.format(error=error)
    raise RespuestaInvalida(f"{llm.nombre} no devolvió un JSON válido tras {MAX_INTENTOS} intentos: {error}")


@app.post("/analizar-parcela", response_model=AnalisisRespuesta)
async def analizar_parcela(
    imagen: UploadFile = File(...), proveedores: dict[str, Proveedor] = Depends(obtener_proveedores)
):
    inicio = time.perf_counter()

    datos = await imagen.read(config.MAX_BYTES_IMAGEN + 1)
    if len(datos) > config.MAX_BYTES_IMAGEN:
        raise HTTPException(413, {"error": "imagen_muy_grande", "detalle": "Máximo 10 MB"})
    jpeg = preparar_imagen(datos)

    llm = proveedores.get(config.PROVEEDOR_ANALISIS)
    respaldo = None if llm else "sin_api_key"
    intentos_previos = 0

    if llm and llm.nombre != "ollama":
        try:
            analisis, intentos = await analizar_con(llm, jpeg)
            return AnalisisRespuesta(
                analisis=analisis,
                humedad_preguntar_usuario=False,
                respaldo=None,
                proveedor=llm.nombre,
                modelo=llm.modelo,
                intentos=intentos,
                latencia_ms=ms_desde(inicio),
            )
        except LLMNoDisponible as e:
            respaldo = "sin_conexion"
            log.warning("Gemini no disponible, uso Ollama: %s", e)
        except LLMError as e:
            respaldo = "error_gemini"
            log.warning("Gemini falló, uso Ollama: %s", e)
        except RespuestaInvalida as e:
            respaldo = "respuesta_invalida"
            intentos_previos = MAX_INTENTOS
            log.warning("Gemini respondió inválido, uso Ollama: %s", e)

    # Respaldo local (o proveedor preferido si PROVEEDOR_ANALISIS=ollama)
    local = proveedores["ollama"]
    try:
        analisis, intentos = await analizar_con(local, jpeg)
    except (LLMNoDisponible, LLMError) as e:
        raise errores_llm(e)
    except RespuestaInvalida as e:
        raise HTTPException(
            502, {"error": "respuesta_invalida_llm", "detalle": str(e), "latencia_ms": ms_desde(inicio)}
        )

    # El modelo local no distingue tierra húmeda de seca: que la app le pregunte al campesino
    analisis.humedad_aparente = "no_determinable"
    return AnalisisRespuesta(
        analisis=analisis,
        humedad_preguntar_usuario=True,
        respaldo=respaldo,
        proveedor=local.nombre,
        modelo=local.modelo,
        intentos=intentos_previos + intentos,
        latencia_ms=ms_desde(inicio),
    )


def max_oraciones(texto: str, n: int = 3) -> str:
    oraciones = re.split(r"(?<=[.!?])\s+", " ".join(texto.split()))
    return " ".join(oraciones[:n])


@app.post("/explicar", response_model=ExplicarRespuesta)
async def explicar(entrada: ExplicarEntrada, proveedores: dict[str, Proveedor] = Depends(obtener_proveedores)):
    inicio = time.perf_counter()
    llm = proveedores.get(config.PROVEEDOR_EXPLICAR) or proveedores["ollama"]

    datos = "\n".join(
        f"- {clave}: {d.valor} (fuente: {d.fuente.upper()}, {FRASE_FUENTE[d.fuente]})"
        for clave, d in entrada.datos_regla.items()
    ) or "- (sin datos adicionales)"
    prompt = prompts.PROMPT_EXPLICAR.format(
        municipio=entrada.municipio,
        cultivo=entrada.cultivo,
        puntaje=entrada.puntaje,
        mes_actual=entrada.mes_actual or "no indicado",
        datos=datos,
        razon_siembra=frase_siembra(entrada.siembra, entrada.mes_actual) if entrada.siembra else "(no hay)",
    )
    respaldo = None if llm.nombre == config.PROVEEDOR_EXPLICAR else "sin_api_key"

    # Igual que /analizar-parcela: si Gemini falla o no hay red, cae a Ollama
    if llm.nombre != "ollama":
        try:
            explicacion = max_oraciones(
                await llm.generar(prompt, sistema=prompts.SISTEMA_EXPLICAR, pensar_minimo=True)
            )
            if explicacion:
                return ExplicarRespuesta(
                    explicacion=explicacion,
                    respaldo=None,
                    proveedor=llm.nombre,
                    modelo=llm.modelo,
                    latencia_ms=ms_desde(inicio),
                )
            respaldo = "respuesta_invalida"
            log.warning("Gemini devolvió texto vacío en /explicar, uso Ollama")
        except LLMNoDisponible as e:
            respaldo = "sin_conexion"
            log.warning("Gemini no disponible en /explicar, uso Ollama: %s", e)
        except LLMError as e:
            respaldo = "error_gemini"
            log.warning("Gemini falló en /explicar, uso Ollama: %s", e)
        llm = proveedores["ollama"]

    try:
        explicacion = max_oraciones(await llm.generar(prompt, sistema=prompts.SISTEMA_EXPLICAR))
    except (LLMNoDisponible, LLMError) as e:
        raise errores_llm(e)
    if not explicacion:
        raise HTTPException(502, {"error": "respuesta_vacia_llm", "detalle": "El modelo no devolvió texto"})

    return ExplicarRespuesta(
        explicacion=explicacion,
        respaldo=respaldo,
        proveedor=llm.nombre,
        modelo=llm.modelo,
        latencia_ms=ms_desde(inicio),
    )


async def generar_con_respaldo(
    proveedores: dict[str, Proveedor], preferido: str, prompt: str, sistema: str, tarea: str
) -> tuple[str, Proveedor, str | None]:
    """Pide texto al proveedor preferido y cae a Ollama si falla. Devuelve (texto, proveedor, respaldo)."""
    llm = proveedores.get(preferido) or proveedores["ollama"]
    respaldo = None if llm.nombre == preferido else "sin_api_key"

    if llm.nombre != "ollama":
        try:
            texto = (await llm.generar(prompt, sistema=sistema, pensar_minimo=True)).strip()
            if texto:
                return texto, llm, None
            respaldo = "respuesta_invalida"
            log.warning("Gemini devolvió texto vacío en %s, uso Ollama", tarea)
        except LLMNoDisponible as e:
            respaldo = "sin_conexion"
            log.warning("Gemini no disponible en %s, uso Ollama: %s", tarea, e)
        except LLMError as e:
            respaldo = "error_gemini"
            log.warning("Gemini falló en %s, uso Ollama: %s", tarea, e)
        llm = proveedores["ollama"]

    try:
        texto = (await llm.generar(prompt, sistema=sistema)).strip()
    except (LLMNoDisponible, LLMError) as e:
        raise errores_llm(e)
    if not texto:
        raise HTTPException(502, {"error": "respuesta_vacia_llm", "detalle": "El modelo no devolvió texto"})
    return texto, llm, respaldo


@app.post("/preguntar", response_model=PreguntarRespuesta)
async def preguntar(entrada: PreguntarEntrada, proveedores: dict[str, Proveedor] = Depends(obtener_proveedores)):
    """Pregunta libre (por voz o escrita). Gemma contesta en español con los datos del municipio;
    las palabras en zapoteco las agrega el glosario, nunca el modelo."""
    inicio = time.perf_counter()
    mes = entrada.mes or datetime.now().month
    # Si el campesino usó palabras en zapoteco, el modelo recibe la pregunta ya en español:
    # así nunca ve zapoteco y no puede repetirlo ni inventarlo
    en_pregunta = glosario.zapoteco_en_pregunta(entrada.texto)
    en_espanol = glosario.traducir_pregunta(entrada.texto)
    traducida = en_espanol if en_pregunta else None
    datos, municipio = contexto.armar(entrada.municipio, mes, en_espanol)
    prompt = prompts.PROMPT_PREGUNTA.format(datos=datos, pregunta=en_espanol.replace('"', "'"))
    texto, llm, respaldo = await generar_con_respaldo(
        proveedores, config.PROVEEDOR_PREGUNTAR, prompt, prompts.SISTEMA_PREGUNTA, "/preguntar"
    )
    # Red de seguridad: si aun así el modelo escribió zapoteco, se quita esa oración
    texto = glosario.quitar_zapoteco_del_modelo(texto) or (
        "No tengo datos suficientes para contestar eso. Pregúntale a alguien con experiencia en tu comunidad."
    )
    respuesta = max_oraciones(texto, 4)

    return PreguntarRespuesta(
        respuesta=respuesta,
        respuesta_segmentos=glosario.segmentos_respuesta(respuesta),
        pregunta_traducida=traducida,
        zapoteco=glosario.palabras_en_texto(respuesta),
        zapoteco_pregunta=en_pregunta,
        saludo=glosario.SALUDO,
        despedida=glosario.DESPEDIDA,
        municipio=municipio,
        respaldo=respaldo,
        proveedor=llm.nombre,
        modelo=llm.modelo,
        latencia_ms=ms_desde(inicio),
    )


AVISO_TRADUCCION = (
    "Traducción automática con Gemma 4, todavía no revisada por un hablante. "
    "Puede tener errores o mezclar otras variantes del zapoteco."
)


@app.post("/traducir-zapoteco", response_model=TraducirRespuesta)
async def traducir_zapoteco(
    entrada: TraducirEntrada, proveedores: dict[str, Proveedor] = Depends(obtener_proveedores)
):
    """Traducción EXPERIMENTAL de una respuesta al zapoteco de la Sierra Norte.

    Se le da al modelo el vocabulario verificado que aparece en el texto para orientarlo a la variante
    de la región, pero el resultado no está revisado: la app lo muestra siempre marcado como experimental.
    """
    inicio = time.perf_counter()
    vocabulario = glosario.palabras_en_texto(entrada.texto)
    nombres = {k: v["nombre"] for k, v in glosario.variantes().items()}
    lista = "\n".join(
        f"- {p['espanol'].lower()} = {p['zapoteco']} ({nombres.get(p['variante'], p['variante'])})" for p in vocabulario
    ) or "- (ninguna palabra del texto)"
    prompt = prompts.PROMPT_TRADUCIR.format(vocabulario=lista, texto=entrada.texto)
    texto, llm, respaldo = await generar_con_respaldo(
        proveedores, config.PROVEEDOR_TRADUCIR, prompt, prompts.SISTEMA_TRADUCIR, "/traducir-zapoteco"
    )
    return TraducirRespuesta(
        traduccion=" ".join(texto.strip().strip('"').split()),
        aviso=AVISO_TRADUCCION,
        vocabulario_usado=vocabulario,
        respaldo=respaldo,
        proveedor=llm.nombre,
        modelo=llm.modelo,
        latencia_ms=ms_desde(inicio),
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host="0.0.0.0", port=config.PORT)
