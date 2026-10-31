"""Pruebas de /preguntar y del glosario zapoteco. No necesitan Ollama ni Gemini.

    .venv/bin/python -m pytest tests/test_preguntar.py
"""

import pytest
from fastapi.testclient import TestClient

from app import config, contexto, glosario
from app.llm import LLMNoDisponible
from app.main import app, obtener_proveedores


class ProveedorFalso:
    def __init__(self, nombre, respuestas):
        self.nombre = nombre
        self.modelo = f"{nombre}-falso"
        self.respuestas = list(respuestas)
        self.llamadas = []

    async def generar(self, prompt, sistema=None, imagen=None, json_mode=False, pensar_minimo=False, max_tokens=None):
        self.llamadas.append({"prompt": prompt, "sistema": sistema, "imagen": imagen, "max_tokens": max_tokens})
        r = self.respuestas.pop(0)
        if isinstance(r, Exception):
            raise r
        return r

    async def salud(self):
        return {"ok": True}


@pytest.fixture
def cliente_con(monkeypatch):
    def _crear(gemini=None, ollama=(), preferido="gemini"):
        monkeypatch.setattr(config, "PROVEEDOR_PREGUNTAR", preferido)
        provs = {"ollama": ProveedorFalso("ollama", ollama)}
        if gemini is not None:
            provs["gemini"] = ProveedorFalso("gemini", gemini)
        app.dependency_overrides[obtener_proveedores] = lambda: provs
        return TestClient(app), provs

    yield _crear
    app.dependency_overrides.clear()


# ---------- glosario ----------

def test_glosario_encuentra_palabras_en_orden():
    r = glosario.palabras_en_texto("Con la lluvia de octubre, el frijol crece en tierra húmeda.")
    assert [(p["espanol"], p["zapoteco"]) for p in r] == [
        ("Lluvia", "Shiah"), ("Frijol", "Dháh"), ("Crecer", "reꞌny"), ("Tierra", "Yúu")
    ]


def test_glosario_plurales_y_sin_acentos():
    nombres = {p["espanol"] for p in glosario.palabras_en_texto("Las lluvias y los frijoles. Arbol con limon.")}
    assert {"Lluvia", "Frijol", "Árboles", "Limón"} <= nombres


def test_glosario_no_confunde_papa_con_papa():
    assert glosario.palabras_en_texto("Pregúntale a tu papá") == []
    assert "Gú" in [p["zapoteco"] for p in glosario.palabras_en_texto("Siembra papa")]


def test_glosario_no_busca_saludos_ni_pendientes_en_respuesta():
    # "gracias" (saludo) y "helada" (sin traducción confirmada) no se agregan
    assert glosario.palabras_en_texto("Gracias. Cuidado con la helada.") == []


def test_glosario_solo_carga_palabras_con_traduccion():
    assert all(p["zapoteco"] for p in glosario.cargar())


def test_zapoteco_en_pregunta():
    r = glosario.zapoteco_en_pregunta("¿Cuándo siembro dháh si ya cayó shiah?")
    assert {p["espanol"] for p in r} == {"Frijol", "Lluvia"}


def test_zapoteco_en_pregunta_ignora_palabras_cortas():
    # "Gú" (papa) y "Yí" (fuego) darían falsos positivos en español
    assert glosario.zapoteco_en_pregunta("gu yi") == []


# ---------- contexto ----------

def test_contexto_municipio_sin_acentos():
    datos, nombre = contexto.armar("ixtlan de juarez", 10, "¿qué siembro?")
    assert nombre == "Ixtlán de Juárez"
    assert "octubre" in datos and "141 mm" in datos


def test_contexto_municipio_desconocido():
    datos, nombre = contexto.armar("Atlantis", 10, "¿qué siembro?")
    assert nombre is None
    assert "No sabemos el municipio" in datos


def test_contexto_agrega_cultivo_mencionado():
    # En enero el frijol no está entre los mejores de Ixtlán, pero se preguntó por él
    datos, _ = contexto.armar("Ixtlán de Juárez", 1, "¿y el frijol?")
    assert "Frijol negro criollo" in datos
    assert "mencionó el campesino" in datos


def test_contexto_avisa_cultivo_sin_datos_en_municipio():
    # Abejones no tiene frijol en los datos: el modelo debe saberlo para no inventar
    datos, _ = contexto.armar("Abejones", 1, "¿puedo sembrar frijoles?")
    assert "NO tenemos en los datos de Abejones: frijol" in datos


# ---------- /preguntar ----------

def test_preguntar_gemini_y_zapoteco(cliente_con):
    respuesta = "En octubre suelen llover 141 mm. Por eso el frijol va bien en tu tierra."
    cliente, provs = cliente_con(gemini=[respuesta])
    r = cliente.post("/preguntar", json={"texto": "¿siembro frijol?", "municipio": "Ixtlán de Juárez", "mes": 10})
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["proveedor"] == "gemini" and j["respaldo"] is None
    assert j["municipio"] == "Ixtlán de Juárez"
    # "llover" cuenta como lluvia (Shiah)
    assert [p["zapoteco"] for p in j["zapoteco"]] == ["Shiah", "Dháh", "Yúu"]
    assert j["saludo"] == "Padiuxi" and j["despedida"] == "Kixarubalo"
    # El modelo recibió los datos reales del municipio
    assert "141 mm" in provs["gemini"].llamadas[0]["prompt"]


def test_preguntar_el_modelo_no_ve_zapoteco(cliente_con):
    cliente, provs = cliente_con(gemini=["Sí, el frijol se siembra en junio-julio."])
    cliente.post("/preguntar", json={"texto": "¿bata siembro dháh?", "municipio": "Abejones", "mes": 5})
    prompt = provs["gemini"].llamadas[0]["prompt"].lower()
    assert "¿cuándo siembro frijol?" in prompt
    assert "dháh" not in prompt and "bata" not in prompt


def test_preguntar_quita_zapoteco_que_escriba_el_modelo(cliente_con):
    # Lo que pasó en la prueba real: Gemma repitió las traducciones al final
    eco = "El frijol se siembra en junio y julio. En octubre suelen llover 141 mm. Bata = ¿cuándo? Dháh = frijol"
    cliente, _ = cliente_con(gemini=[eco])
    j = cliente.post("/preguntar", json={"texto": "¿Bata siembro dháh?", "municipio": "Ixtlán de Juárez"}).json()
    assert j["respuesta"] == "El frijol se siembra en junio y julio. En octubre suelen llover 141 mm."
    assert "Bata" not in j["respuesta"] and "Dháh" not in j["respuesta"]


def test_preguntar_cae_a_ollama_sin_conexion(cliente_con):
    cliente, provs = cliente_con(gemini=[LLMNoDisponible("sin red")], ollama=["Con la lluvia de junio, siembra frijol."])
    r = cliente.post("/preguntar", json={"texto": "¿qué siembro?", "municipio": "Abejones", "mes": 6})
    j = r.json()
    assert j["proveedor"] == "ollama" and j["respaldo"] == "sin_conexion"
    assert [p["espanol"] for p in j["zapoteco"]] == ["Lluvia", "Sembrar", "Frijol"]


def test_preguntar_sin_api_key_usa_ollama(cliente_con):
    cliente, _ = cliente_con(gemini=None, ollama=["Respuesta local."])
    j = cliente.post("/preguntar", json={"texto": "hola"}).json()
    assert j["proveedor"] == "ollama" and j["respaldo"] == "sin_api_key"


def test_preguntar_recorta_a_cuatro_oraciones(cliente_con):
    cliente, _ = cliente_con(gemini=["Uno. Dos. Tres. Cuatro. Cinco. Seis."])
    j = cliente.post("/preguntar", json={"texto": "¿qué siembro?"}).json()
    assert j["respuesta"] == "Uno. Dos. Tres. Cuatro."


def test_preguntar_valida_entrada(cliente_con):
    cliente, _ = cliente_con(gemini=[])
    assert cliente.post("/preguntar", json={"texto": ""}).status_code == 422
    assert cliente.post("/preguntar", json={"texto": "hola", "mes": 13}).status_code == 422


# ---------- preguntar en zapoteco y respuesta mezclada ----------

def test_traducir_pregunta_con_interrogativos():
    assert glosario.traducir_pregunta("¿Bata siembro dháh si ya cayó shiah?") == "¿cuándo siembro frijol si ya cayó lluvia?"
    assert glosario.traducir_pregunta("Padiuxi, ¿kani siembro ishú?") == "hola, ¿dónde siembro aguacate?"


def test_traducir_pregunta_sin_zapoteco_no_cambia():
    assert glosario.traducir_pregunta("¿Qué siembro este mes?") == "¿Qué siembro este mes?"


def test_segmentos_marcan_solo_la_primera_vez():
    seg = glosario.segmentos_respuesta("El frijol necesita lluvia. Más lluvia, más frijol.")
    marcados = [(s["texto"], s["zapoteco"]) for s in seg if s["zapoteco"]]
    assert marcados == [("frijol", "Dháh"), ("lluvia", "Shiah")]
    # Juntando los trozos sale la respuesta original, sin perder nada
    assert "".join(s["texto"] for s in seg) == "El frijol necesita lluvia. Más lluvia, más frijol."


def test_segmentos_conservan_mayusculas_y_acentos():
    seg = glosario.segmentos_respuesta("Lluvia y Árboles.")
    assert [(s["texto"], s["zapoteco"]) for s in seg if s["zapoteco"]] == [("Lluvia", "Shiah"), ("Árboles", "Ka-yaha")]


def test_alias_voz(monkeypatch):
    # Un hablante puede registrar cómo transcribe el teléfono una palabra
    original = glosario.cargar()
    con_alias = [dict(p, alias_voz=["chía"]) if p["espanol"] == "Lluvia" else p for p in original]
    monkeypatch.setattr(glosario, "cargar", lambda: con_alias)
    glosario._patrones.cache_clear()
    try:
        assert glosario.traducir_pregunta("¿ya cayó suficiente chía?") == "¿ya cayó suficiente lluvia?"
    finally:
        glosario._patrones.cache_clear()


def test_preguntar_en_zapoteco(cliente_con):
    cliente, provs = cliente_con(gemini=["El frijol se siembra en junio y julio, con la lluvia."])
    j = cliente.post(
        "/preguntar", json={"texto": "¿Bata siembro dháh?", "municipio": "Ixtlán de Juárez", "mes": 10}
    ).json()
    assert j["pregunta_traducida"] == "¿cuándo siembro frijol?"
    prompt = provs["gemini"].llamadas[0]["prompt"]
    assert "¿cuándo siembro frijol?" in prompt
    # Encontró los datos del frijol aunque la pregunta decía "dháh"
    assert "Frijol negro criollo" in prompt
    assert [s["zapoteco"] for s in j["respuesta_segmentos"] if s["zapoteco"]] == ["Dháh", "raz", "Shiah"]


def test_preguntar_en_espanol_no_trae_traduccion(cliente_con):
    cliente, _ = cliente_con(gemini=["Respuesta."])
    j = cliente.post("/preguntar", json={"texto": "¿qué siembro?"}).json()
    assert j["pregunta_traducida"] is None


def test_preguntar_si_todo_era_zapoteco_responde_algo(cliente_con):
    cliente, _ = cliente_con(gemini=["Dháh = frijol."])
    j = cliente.post("/preguntar", json={"texto": "¿dháh?"}).json()
    assert j["respuesta"].startswith("No tengo datos suficientes")



# ---------- traducción experimental ----------

def test_traducir_da_vocabulario_verificado_al_modelo(cliente_con, monkeypatch):
    monkeypatch.setattr(config, "PROVEEDOR_TRADUCIR", "gemini")
    cliente, provs = cliente_con(gemini=['"Dháh ... Shiah ..."'])
    j = cliente.post("/traducir-zapoteco", json={"texto": "El frijol necesita lluvia."}).json()
    prompt = provs["gemini"].llamadas[0]["prompt"]
    assert "frijol = Dháh" in prompt and "lluvia = Shiah" in prompt
    assert j["experimental"] is True and "no revisada" in j["aviso"]
    assert j["traduccion"] == "Dháh ... Shiah ..."  # sin comillas
    assert [p["zapoteco"] for p in j["vocabulario_usado"]] == ["Dháh", "Shiah"]


def test_traducir_cae_a_ollama(cliente_con, monkeypatch):
    monkeypatch.setattr(config, "PROVEEDOR_TRADUCIR", "gemini")
    cliente, _ = cliente_con(gemini=[LLMNoDisponible("sin red")], ollama=["traducción local"])
    j = cliente.post("/traducir-zapoteco", json={"texto": "Hola."}).json()
    assert j["proveedor"] == "ollama" and j["respaldo"] == "sin_conexion"



# ---------- variantes (vocabulario del equipo y Jaltepec) ----------

def test_cada_palabra_dice_su_variante():
    r = {p["espanol"]: p for p in glosario.palabras_en_texto("El maíz necesita lluvia.")}
    assert r["Maíz"]["zapoteco"] == "xhoꞌbaꞌ" and r["Maíz"]["variante"] == "jaltepec"
    assert r["Lluvia"]["variante"] == "sierra_norte"
    assert {"zapoteco": "guio lasi", "variante": "jaltepec"} in r["Lluvia"]["otras_variantes"]


def test_pregunta_con_palabras_de_jaltepec():
    assert glosario.traducir_pregunta("¿Bata raz xhoꞌbaꞌ si no hay nisa?") == "¿cuándo sembrar maíz si no hay agua?"


def test_variantes_tienen_nombre_y_fuente():
    v = glosario.variantes()
    assert set(v) == {"sierra_norte", "jaltepec"}
    assert "INPI" in v["jaltepec"]["fuente"]


def test_no_confunde_yo_en_espanol():
    # "yo" es tierra en Jaltepec, pero es muy corta para buscarla en español
    assert glosario.quitar_zapoteco_del_modelo("Yo creo que sí.") == "Yo creo que sí."



def test_traducir_limita_largo_de_respuesta(cliente_con, monkeypatch):
    # En la prueba real Gemma no terminaba y Gemini cortó a los 30 s (504)
    monkeypatch.setattr(config, "PROVEEDOR_TRADUCIR", "gemini")
    cliente, provs = cliente_con(gemini=["traducción"])
    cliente.post("/traducir-zapoteco", json={"texto": "Hola."})
    assert provs["gemini"].llamadas[0]["max_tokens"] == 300
