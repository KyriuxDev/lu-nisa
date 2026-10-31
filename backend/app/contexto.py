"""Datos del municipio que Gemma recibe para contestar una pregunta.

Salen del mismo JSON que usa la app (assets/data/recomendaciones.json):
clima 2018-2023 por mes y cultivos con su puntaje por mes.
"""

import json
import re
from functools import lru_cache
from pathlib import Path

from app import config
from app.glosario import normalizar

MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio",
         "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"]
MAX_CULTIVOS = 6


@lru_cache
def cargar() -> dict:
    return json.loads(Path(config.DATOS_RECOMENDACIONES).read_text(encoding="utf-8"))


def nombre_corto(cultivo: str) -> str:
    """'Frijol negro criollo' se queda; 'Calabaza (Cucurbita pepo...)' → 'Calabaza'."""
    return re.sub(r"\s*\(.*\)", "", cultivo).strip()


def buscar_municipio(nombre: str) -> str | None:
    buscado = normalizar(nombre).strip()
    for m in cargar():
        if normalizar(m) == buscado:
            return m
    return None


def _clave(cultivo: str) -> str:
    """Basta la primera palabra: "maíz", "frijol", "café", "chile"."""
    return normalizar(nombre_corto(cultivo).split()[0])


def _menciona(texto_normalizado: str, clave: str) -> bool:
    return re.search(rf"(?<!\w){re.escape(clave)}(?:e?s)?(?!\w)", texto_normalizado) is not None


@lru_cache
def _todas_las_claves() -> frozenset[str]:
    return frozenset(
        _clave(c["cultivo"]) for m in cargar().values() for lista in m["recomendaciones_por_mes"].values() for c in lista
    )


def _cultivos_mencionados(pregunta: str, municipio: dict) -> dict[str, dict]:
    """Cultivos que el campesino nombró ("¿y el frijol?"), aunque no estén en el top del mes."""
    texto = normalizar(pregunta)
    encontrados: dict[str, dict] = {}
    for mes, lista in municipio["recomendaciones_por_mes"].items():
        for c in lista:
            if _menciona(texto, _clave(c["cultivo"])):
                previo = encontrados.get(c["cultivo"])
                if previo is None or c["score"] > previo["score"]:
                    encontrados[c["cultivo"]] = {**c, "mes_mejor_puntaje": MESES[int(mes) - 1]}
    return encontrados


def meses_de(rango: str) -> list[int]:
    """'Mayo-Junio' → [5, 6]; 'Octubre-Enero' → [10, 11, 12, 1]. Vacío si no se entiende."""
    partes = [normalizar(p).strip() for p in rango.split("-")]
    nums = [MESES.index(p) + 1 for p in partes if p in MESES]
    if not nums:
        return []
    inicio, fin = nums[0], nums[-1]
    salida = [inicio]
    while salida[-1] != fin:
        salida.append(salida[-1] % 12 + 1)
    return salida


def _calendario_siembra(municipio: dict, mes: int) -> list[str]:
    """Qué se siembra este mes y qué toca después: así el modelo no tiene que calcularlo."""
    cultivos: dict[str, str] = {}
    for lista in municipio["recomendaciones_por_mes"].values():
        for c in lista:
            cultivos.setdefault(nombre_corto(c["cultivo"]), c["meses_siembra"])

    ahora, proximos = [], []
    for nombre, rango in cultivos.items():
        meses = meses_de(rango)
        if not meses:
            continue
        if mes in meses:
            ahora.append(f"{nombre} ({rango.lower()})")
        else:
            faltan = min((m - mes) % 12 for m in meses)
            primero = MESES[(mes + faltan - 1) % 12]
            proximos.append((faltan, f"{nombre}: empieza en {primero}, en {faltan} {'mes' if faltan == 1 else 'meses'}"))

    lineas = []
    if ahora:
        lineas.append(f"Cultivos que se siembran en {MESES[mes - 1]}: {', '.join(sorted(ahora))}")
    else:
        lineas.append(f"En {MESES[mes - 1]} no se siembra ninguno de los cultivos de los datos de este municipio.")
    if proximos:
        lineas.append("Próximos cultivos en sembrarse:")
        lineas += [f"- {texto}" for _, texto in sorted(proximos)[:3]]
    return lineas


def _linea_cultivo(c: dict) -> str:
    partes = [
        f"{nombre_corto(c['cultivo'])}: puntaje {c['score']}/100",
        f"se siembra en {c['meses_siembra'].lower()}",
        f"se cosecha en {c['meses_cosecha'].lower()}",
        f"necesita agua {c['requerimiento_agua']}",
    ]
    if c.get("mes_mejor_puntaje"):
        partes.append(f"su mejor puntaje es en {c['mes_mejor_puntaje']}")
    if c.get("notas"):
        partes.append(f"nota: {c['notas']}")
    return "- " + "; ".join(partes)


def armar(municipio_nombre: str | None, mes: int, pregunta: str) -> tuple[str, str | None]:
    """Devuelve (texto de datos para el prompt, nombre del municipio encontrado o None)."""
    nombre = buscar_municipio(municipio_nombre) if municipio_nombre else None
    if not nombre:
        return "(No sabemos el municipio: no hay datos de clima ni cultivos.)", None

    m = cargar()[nombre]
    clima = m["clima_mensual"][str(mes)]
    sig = mes % 12 + 1
    clima_sig = m["clima_mensual"][str(sig)]
    lineas = [
        f"Municipio: {nombre} (distrito {m['distrito']}, {m['altitud']} msnm)",
        f"Mes de la consulta: {MESES[mes - 1]}",
        f"Clima de {MESES[mes - 1]} (promedio 2018-2023): temperatura media {clima['temp_media']} °C, "
        f"mínima {clima['temp_min']} °C, lluvia {clima['precipitacion_mensual']} mm en el mes",
        f"Clima de {MESES[sig - 1]}: temperatura media {clima_sig['temp_media']} °C, "
        f"lluvia {clima_sig['precipitacion_mensual']} mm en el mes",
    ]
    lineas += _calendario_siembra(m, mes)
    lineas.append(f"Cultivos con mejor puntaje en {MESES[mes - 1]} (para cuidar o cosechar, no siempre para sembrar):")
    del_mes = sorted(m["recomendaciones_por_mes"].get(str(mes), []), key=lambda c: -c["score"])
    lineas += [_linea_cultivo(c) for c in del_mes[:MAX_CULTIVOS]]

    nombres_mes = {c["cultivo"] for c in del_mes[:MAX_CULTIVOS]}
    extra = [c for k, c in _cultivos_mencionados(pregunta, m).items() if k not in nombres_mes]
    if extra:
        lineas.append(f"Cultivos que mencionó el campesino (no están entre los mejores de {MESES[mes - 1]}):")
        lineas += [_linea_cultivo(c) for c in extra]

    # Mencionó un cultivo que existe en otros municipios pero no en este: que el modelo no invente
    del_municipio = {_clave(c["cultivo"]) for lista in m["recomendaciones_por_mes"].values() for c in lista}
    texto = normalizar(pregunta)
    sin_datos = sorted(k for k in _todas_las_claves() - del_municipio if _menciona(texto, k))
    if sin_datos:
        lineas.append(f"Cultivos que mencionó y que NO tenemos en los datos de {nombre}: {', '.join(sin_datos)}")
    return "\n".join(lineas), nombre
