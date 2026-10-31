"""Pruebas de /analizar-cultivo. No necesitan Ollama ni Gemini.

    .venv/bin/python -m pytest tests/test_cultivo.py
"""

import asyncio
import io
import json

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app import config, cultivo
from app.llm import LLMNoDisponible
from app.main import app, obtener_proveedores

COGOLLERO = {
    "es_planta": True,
    "cultivo_visto": "maíz",
    "etapa": "crecimiento",
    "estado_general": "problemas_leves",
    "sintomas": ["agujeros en las hojas nuevas", "aserrín en el cogollo"],
    "posibles_causas": [
        {"nombre": "gusano cogollero", "tipo": "insecto", "confianza": "media", "senales": "hoyos y excremento"},
        {"nombre": "falta de nitrógeno", "tipo": "falta_de_nutrientes", "confianza": "baja", "senales": "hojas pálidas"},
    ],
    "confianza": "media",
    "observaciones": "Daño en las hojas del cogollo del maíz.",
}


def jpeg() -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (800, 600), (40, 120, 40)).save(buf, format="JPEG")
    return buf.getvalue()


class ProveedorFalso:
    def __init__(self, nombre, respuestas, demora=0.0):
        self.nombre = nombre
        self.modelo = f"{nombre}-falso"
        self.respuestas = list(respuestas)
        self.llamadas = []
        self.demora = demora
        self.cancelado = False

    async def generar(self, prompt, sistema=None, imagen=None, json_mode=False, pensar_minimo=False, max_tokens=None):
        try:
            await asyncio.sleep(self.demora)
        except asyncio.CancelledError:
            self.cancelado = True
            raise
        self.llamadas.append(
            {"prompt": prompt, "sistema": sistema, "imagen": imagen, "pensar_minimo": pensar_minimo, "max_tokens": max_tokens}
        )
        r = self.respuestas.pop(0)
        if isinstance(r, Exception):
            raise r
        return r

    async def salud(self):
        return {"ok": True}


@pytest.fixture
def cliente_con(monkeypatch):
    def _crear(gemini=None, ollama=(), paralelo=False, demora_gemini=0.0, demora_ollama=0.0):
        monkeypatch.setattr(config, "PROVEEDOR_ANALISIS", "gemini")
        monkeypatch.setattr(config, "CULTIVO_EN_PARALELO", paralelo)
        provs = {"ollama": ProveedorFalso("ollama", ollama, demora_ollama)}
        if gemini is not None:
            provs["gemini"] = ProveedorFalso("gemini", gemini, demora_gemini)
        app.dependency_overrides[obtener_proveedores] = lambda: provs
        return TestClient(app), provs

    yield _crear
    app.dependency_overrides.clear()


def enviar(cliente, cultivo=None):
    datos = {"cultivo": cultivo} if cultivo else {}
    return cliente.post("/analizar-cultivo", files={"imagen": ("hoja.jpg", jpeg(), "image/jpeg")}, data=datos)


def test_cultivo_con_gemini(cliente_con):
    cliente, provs = cliente_con(gemini=[json.dumps(COGOLLERO)])
    r = enviar(cliente, cultivo="maíz")
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["proveedor"] == "gemini" and j["modelo_local"] is False
    assert j["analisis"]["posibles_causas"][0]["nombre"] == "gusano cogollero"
    # La imagen y la pista del cultivo llegan al modelo
    assert provs["gemini"].llamadas[0]["imagen"]
    assert "maíz" in provs["gemini"].llamadas[0]["prompt"]
    # Zapoteco de lo que se encontró
    assert {"Maíz", "Hoja", "Gusano"} <= {p["espanol"] for p in j["zapoteco"]}


def test_pasos_son_seguros_y_terminan_con_tecnico(cliente_con):
    cliente, _ = cliente_con(gemini=[json.dumps(COGOLLERO)])
    j = enviar(cliente).json()
    pasos = " ".join(j["pasos"]).lower()
    assert j["pasos"][-1] == cultivo.PASO_FINAL
    assert "en la mañana o al atardecer" in pasos  # insecto
    assert "hojas de abajo" in pasos  # falta de nutrientes
    assert "no es un diagnóstico" in j["aviso"].lower()


def test_prompt_prohibe_recomendar_productos():
    assert "PROHIBIDO" in cultivo.SISTEMA and "dosis" in cultivo.SISTEMA


def test_cultivo_sano():
    a = cultivo.CultivoAnalisis.model_validate(
        {**COGOLLERO, "estado_general": "sano", "posibles_causas": [], "sintomas": []}
    )
    assert cultivo.pasos_seguros(a) == [cultivo.PASO_SANO]


def test_no_es_planta():
    a = cultivo.CultivoAnalisis.model_validate(
        {**COGOLLERO, "es_planta": False, "estado_general": "no_determinable", "posibles_causas": [], "sintomas": []}
    )
    assert cultivo.pasos_seguros(a) == [cultivo.PASO_SIN_PLANTA]


def test_acaros_tienen_su_paso():
    # Caso real: ácaro rojo en hojas de palma; casi no se ve en la foto
    a = cultivo.CultivoAnalisis.model_validate(
        {
            **COGOLLERO,
            "cultivo_visto": "palma",
            "posibles_causas": [
                {"nombre": "ácaro rojo", "tipo": "acaro", "confianza": "media", "senales": "manchitas amarillas"}
            ],
        }
    )
    assert any("lupa" in p for p in cultivo.pasos_seguros(a))


def test_prompt_considera_acaros():
    assert '"acaro"' in cultivo.PROMPT and "ácaros" in cultivo.PROMPT


def test_recorta_listas_largas():
    a = cultivo.CultivoAnalisis.model_validate(
        {
            **COGOLLERO,
            "sintomas": ["a", "b", "c", "d", "e", "f"],
            "posibles_causas": [COGOLLERO["posibles_causas"][0]] * 5,
            "observaciones": " ".join(["x"] * 40),
        }
    )
    assert len(a.sintomas) == 4 and len(a.posibles_causas) == 3
    assert a.observaciones.endswith("…")


def test_reintenta_si_json_invalido(cliente_con):
    cliente, provs = cliente_con(gemini=["no es json", json.dumps(COGOLLERO)])
    j = enviar(cliente).json()
    assert j["intentos"] == 2 and j["proveedor"] == "gemini"
    assert "no fue válida" in provs["gemini"].llamadas[1]["prompt"]


def test_cae_a_ollama_y_lo_marca(cliente_con):
    cliente, _ = cliente_con(gemini=[LLMNoDisponible("sin red")], ollama=[json.dumps(COGOLLERO)])
    j = enviar(cliente).json()
    assert j["proveedor"] == "ollama" and j["modelo_local"] is True and j["respaldo"] == "sin_conexion"


def test_imagen_invalida(cliente_con):
    cliente, _ = cliente_con(gemini=[])
    r = cliente.post("/analizar-cultivo", files={"imagen": ("x.jpg", b"no soy imagen", "image/jpeg")})
    assert r.status_code == 415


def test_pide_razonamiento_minimo(cliente_con):
    # En la prueba real Gemini cortaba a los 30 s porque Gemma razonaba demasiado
    cliente, provs = cliente_con(gemini=[json.dumps(COGOLLERO)])
    enviar(cliente)
    assert provs["gemini"].llamadas[0]["pensar_minimo"] is True



# ---------- Gemini y Gemma local al mismo tiempo ----------

def test_paralelo_gana_gemini_si_es_rapido(cliente_con):
    cliente, provs = cliente_con(
        gemini=[json.dumps(COGOLLERO)], ollama=[json.dumps(COGOLLERO)], paralelo=True, demora_ollama=0.5
    )
    j = enviar(cliente).json()
    assert j["proveedor"] == "gemini" and j["respaldo"] is None and j["modelo_local"] is False
    assert provs["ollama"].cancelado  # al local se le corta para no gastar la compu


def test_paralelo_gana_local_si_gemini_es_lento(cliente_con):
    # Lo que pasaba en el teléfono: Gemini tardaba más de 30 s con la foto
    cliente, provs = cliente_con(
        gemini=[json.dumps(COGOLLERO)], ollama=[json.dumps(COGOLLERO)], paralelo=True, demora_gemini=0.5
    )
    j = enviar(cliente).json()
    assert j["proveedor"] == "ollama" and j["respaldo"] == "mas_rapido_local" and j["modelo_local"] is True
    assert provs["gemini"].cancelado


def test_paralelo_gemini_falla_y_responde_local(cliente_con):
    cliente, _ = cliente_con(
        gemini=[LLMNoDisponible("sin red")], ollama=[json.dumps(COGOLLERO)], paralelo=True, demora_ollama=0.1
    )
    j = enviar(cliente).json()
    assert j["proveedor"] == "ollama" and j["respaldo"] == "sin_conexion"


def test_paralelo_local_falla_y_espera_a_gemini(cliente_con):
    cliente, _ = cliente_con(
        gemini=[json.dumps(COGOLLERO)], ollama=[LLMNoDisponible("ollama apagado")], paralelo=True, demora_gemini=0.2
    )
    j = enviar(cliente).json()
    assert j["proveedor"] == "gemini" and j["respaldo"] is None


def test_paralelo_fallan_los_dos(cliente_con):
    cliente, _ = cliente_con(
        gemini=[LLMNoDisponible("sin red")], ollama=[LLMNoDisponible("ollama apagado")], paralelo=True
    )
    assert enviar(cliente).status_code == 503


def test_respuesta_mas_corta(cliente_con):
    # Menos texto = respuesta más rápida, sobre todo en el modelo local
    cliente, provs = cliente_con(gemini=[json.dumps(COGOLLERO)])
    enviar(cliente)
    assert provs["gemini"].llamadas[0]["max_tokens"] == 500
