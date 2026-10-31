import os
from pathlib import Path

from dotenv import load_dotenv

# Carga backend/.env sin importar desde dónde se arranque uvicorn
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

# Proveedor preferido por tarea: ollama | gemini
PROVEEDOR_ANALISIS = os.getenv("PROVEEDOR_ANALISIS", "gemini").strip().lower()
PROVEEDOR_EXPLICAR = os.getenv("PROVEEDOR_EXPLICAR", "ollama").strip().lower()

OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434").rstrip("/")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "gemma4:e4b")
OLLAMA_TIMEOUT = float(os.getenv("OLLAMA_TIMEOUT", "120"))

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemma-4-26b-a4b-it")
# Corto para que Gemini + respaldo en Ollama quepan en los 90 s de la app
GEMINI_TIMEOUT = float(os.getenv("GEMINI_TIMEOUT", "30"))

PORT = int(os.getenv("PORT", "8000"))

# Proveedor preferido para /preguntar (voz); cae a Ollama si Gemini falla
PROVEEDOR_PREGUNTAR = os.getenv("PROVEEDOR_PREGUNTAR", "gemini").strip().lower()
# Traducción experimental al zapoteco: el modelo grande traduce mejor que el local
PROVEEDOR_TRADUCIR = os.getenv("PROVEEDOR_TRADUCIR", "gemini").strip().lower()
# /analizar-cultivo: Gemini y Gemma local al mismo tiempo, gana el primero que responda bien
CULTIVO_EN_PARALELO = os.getenv("CULTIVO_EN_PARALELO", "true").strip().lower() in ("1", "true", "si", "sí")

# Mismo JSON que usa la app: clima y cultivos por municipio y mes
DATOS_RECOMENDACIONES = os.getenv(
    "DATOS_RECOMENDACIONES",
    str(Path(__file__).resolve().parents[2] / "assets" / "data" / "recomendaciones.json"),
)

# Límites de la imagen recibida
MAX_BYTES_IMAGEN = 10 * 1024 * 1024
LADO_MAX_IMAGEN = 1024
