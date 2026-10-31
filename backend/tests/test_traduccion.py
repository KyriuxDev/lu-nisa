"""Traducción experimental al zapoteco de Jaltepec. No necesitan el PDF ni Ollama ni Gemini.

    .venv/bin/python -m pytest tests/test_traduccion.py
"""

import pytest
from fastapi.testclient import TestClient

from app import config, traduccion
from app.llm import LLMNoDisponible
from app.main import app, limpiar_traduccion, obtener_proveedores

# Unas pocas oraciones con la forma del diccionario (no se usan las reales en las pruebas)
EJEMPLOS = [
    {"espanol": "Ya se acedó tu frijol", "zapoteco": "ba wxhíin za kioꞌó", "entrada": "za"},
    {"espanol": "En una ocasión sembré cebollas", "zapoteco": "tsniaꞌ góozaꞌ sbóol", "entrada": "raz"},
    {"espanol": "Mi gato cazó un ratón", "zapoteco": "wxhe mistgo kiaꞌa to bziꞌn", "entrada": "bziꞌn"},
]

BUCLE_REAL = (
    "Ndxi' xquixe' shiah 141 mm naxhi' xquixe' ndu'u 14.2 °C. Ndxi' naxhi' ndu'u naxhi' raz ndxi' ndxi' ndu'u, "
    "naxhi' ndxi' raz ndxi' ndxi' ndu'u ndxi' ndxi' ndu'u. Ndxi' " + "naxhi' " * 40
)


@pytest.fixture(autouse=True)
def ejemplos_falsos(monkeypatch):
    monkeypatch.setattr(traduccion, "ejemplos", lambda: EJEMPLOS)
    traduccion._indice.cache_clear()
    yield
    traduccion._indice.cache_clear()


class ProveedorFalso:
    def __init__(self, nombre, respuesta):
        self.nombre = nombre
        self.modelo = f"{nombre}-falso"
        self.respuesta = respuesta  # texto, excepción o función(prompt) -> texto
        self.llamadas = []

    async def generar(self, prompt, sistema=None, imagen=None, json_mode=False, pensar_minimo=False, max_tokens=None):
        self.llamadas.append({"prompt": prompt, "max_tokens": max_tokens})
        if isinstance(self.respuesta, Exception):
            raise self.respuesta
        return self.respuesta(prompt) if callable(self.respuesta) else self.respuesta

    async def salud(self):
        return {"ok": True}


@pytest.fixture
def cliente_con(monkeypatch):
    def _crear(gemini=None, ollama="traducción local de prueba"):
        monkeypatch.setattr(config, "PROVEEDOR_TRADUCIR", "gemini")
        provs = {"ollama": ProveedorFalso("ollama", ollama)}
        if gemini is not None:
            provs["gemini"] = ProveedorFalso("gemini", gemini)
        app.dependency_overrides[obtener_proveedores] = lambda: provs
        return TestClient(app), provs

    yield _crear
    app.dependency_overrides.clear()


def test_busca_ejemplos_que_comparten_palabras():
    assert traduccion.ejemplos_para("El frijol se siembra en junio")[0]["zapoteco"] == "ba wxhíin za kioꞌó"
    assert traduccion.ejemplos_para("Hola") == []


def test_vocabulario_solo_de_jaltepec():
    # lluvia es Shiah en el vocabulario del equipo, pero para traducir a Jaltepec se usa guio lasi
    vocab = dict(traduccion.vocabulario_jaltepec("El frijol necesita lluvia."))
    assert vocab == {"frijol": "zaá", "lluvia": "guio lasi"}


def test_traduce_oracion_por_oracion_con_ejemplos(cliente_con):
    cliente, provs = cliente_con(gemini="za kioꞌó raz guio lasi")
    j = cliente.post("/traducir-zapoteco", json={"texto": "El frijol necesita lluvia. Siembra en junio."}).json()
    assert len(provs["gemini"].llamadas) == 2  # una por oración
    prompt = provs["gemini"].llamadas[0]["prompt"]
    assert "Ya se acedó tu frijol → ba wxhíin za kioꞌó" in prompt
    assert "frijol = zaá" in prompt and "lluvia = guio lasi" in prompt
    assert provs["gemini"].llamadas[0]["max_tokens"] == 120
    # "siembra" encuentra "sembré" aunque cambie la raíz
    assert j["confiable"] is True and j["variante"] == "jaltepec" and j["ejemplos_usados"] >= 2
    assert [o["espanol"] for o in j["oraciones"]] == ["El frijol necesita lluvia.", "Siembra en junio."]


def test_oracion_en_bucle_se_queda_en_espanol(cliente_con):
    def responde(prompt):
        return "naxhi' naxhi' naxhi' naxhi'" if "junio" in prompt.split("Oración en español:")[1] else "za kioꞌó guio lasi"

    cliente, _ = cliente_con(gemini=responde)
    j = cliente.post("/traducir-zapoteco", json={"texto": "El frijol necesita lluvia. Siembra en junio."}).json()
    assert j["oraciones"][0]["zapoteco"] == "za kioꞌó guio lasi"
    assert j["oraciones"][1]["zapoteco"] is None
    assert j["traduccion"] == "za kioꞌó guio lasi"
    assert j["confiable"] is True  # la mitad salió bien


def test_todo_en_bucle_no_es_confiable(cliente_con):
    cliente, _ = cliente_con(gemini=BUCLE_REAL)
    j = cliente.post("/traducir-zapoteco", json={"texto": "En octubre suelen llover 141 mm."}).json()
    assert j["confiable"] is False and j["traduccion"] == ""


def test_cae_a_ollama(cliente_con):
    cliente, _ = cliente_con(gemini=LLMNoDisponible("sin red"))
    j = cliente.post("/traducir-zapoteco", json={"texto": "Hola a todos."}).json()
    assert j["proveedor"] == "ollama" and j["respaldo"] == "sin_conexion"


def test_limpiar_corta_bucles():
    assert limpiar_traduccion(BUCLE_REAL) is None
    assert limpiar_traduccion("Dháh raz guiela xhoꞌbaꞌ nisa yo yo yo yo") == "Dháh raz guiela xhoꞌbaꞌ nisa"
    assert traduccion.limpiar('"ba wxhíin za kioꞌó"') == "ba wxhíin za kioꞌó"
    assert traduccion.limpiar("za") is None  # una sola palabra no es traducción
