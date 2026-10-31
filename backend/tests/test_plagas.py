"""Pruebas de /analizar-plaga. No necesitan Ollama ni Gemini.

    .venv/bin/python -m pytest tests/test_plagas.py
"""

import io
import json

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app import config, plagas
from app.llm import LLMNoDisponible
from app.main import app, obtener_proveedores

COGOLLERO = {
    "es_planta": True,
    "cultivo_visto": "maíz",
    "parte_afectada": "hoja",
    "hay_dano": True,
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
    def __init__(self, nombre, respuestas):
        self.nombre = nombre
        self.modelo = f"{nombre}-falso"
        self.respuestas = list(respuestas)
        self.llamadas = []

    async def generar(self, prompt, sistema=None, imagen=None, json_mode=False, pensar_minimo=False, max_tokens=None):
        self.llamadas.append({"prompt": prompt, "sistema": sistema, "imagen": imagen, "pensar_minimo": pensar_minimo})
        r = self.respuestas.pop(0)
        if isinstance(r, Exception):
            raise r
        return r

    async def salud(self):
        return {"ok": True}


@pytest.fixture
def cliente_con(monkeypatch):
    def _crear(gemini=None, ollama=()):
        monkeypatch.setattr(config, "PROVEEDOR_ANALISIS", "gemini")
        provs = {"ollama": ProveedorFalso("ollama", ollama)}
        if gemini is not None:
            provs["gemini"] = ProveedorFalso("gemini", gemini)
        app.dependency_overrides[obtener_proveedores] = lambda: provs
        return TestClient(app), provs

    yield _crear
    app.dependency_overrides.clear()


def enviar(cliente, cultivo=None):
    datos = {"cultivo": cultivo} if cultivo else {}
    return cliente.post("/analizar-plaga", files={"imagen": ("hoja.jpg", jpeg(), "image/jpeg")}, data=datos)


def test_plaga_con_gemini(cliente_con):
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
    assert j["pasos"][-1] == plagas.PASO_FINAL
    assert "en la mañana o al atardecer" in pasos  # insecto
    assert "hojas de abajo" in pasos  # falta de nutrientes
    assert "no es un diagnóstico" in j["aviso"].lower()


def test_prompt_prohibe_recomendar_productos():
    assert "PROHIBIDO" in plagas.SISTEMA and "dosis" in plagas.SISTEMA


def test_planta_sana():
    a = plagas.PlagaAnalisis.model_validate({**COGOLLERO, "hay_dano": False, "posibles_causas": [], "sintomas": []})
    assert plagas.pasos_seguros(a) == ["La planta se ve sana en la foto. Sigue revisándola cada semana."]


def test_no_es_planta():
    a = plagas.PlagaAnalisis.model_validate(
        {**COGOLLERO, "es_planta": False, "hay_dano": "no_determinable", "posibles_causas": [], "sintomas": []}
    )
    assert "foto de cerca" in plagas.pasos_seguros(a)[0]


def test_recorta_listas_largas():
    a = plagas.PlagaAnalisis.model_validate(
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
    r = cliente.post("/analizar-plaga", files={"imagen": ("x.jpg", b"no soy imagen", "image/jpeg")})
    assert r.status_code == 415


def test_pide_razonamiento_minimo(cliente_con):
    # En la prueba real Gemini cortaba a los 30 s porque Gemma razonaba demasiado
    cliente, provs = cliente_con(gemini=[json.dumps(COGOLLERO)])
    enviar(cliente)
    assert provs["gemini"].llamadas[0]["pensar_minimo"] is True
