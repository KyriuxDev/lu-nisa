# Lu-nisa backend

FastAPI + Gemma 4 (Ollama local o API de Gemini) para analizar fotos de parcelas
y explicar recomendaciones de cultivo.

## Arrancar

```bash
cd backend
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
cp .env.example .env          # pon tu GEMINI_API_KEY
ollama pull gemma4:e4b        # respaldo local y /explicar
.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000
```

## Proveedores por tarea

| Tarea | Preferido | Respaldo |
|---|---|---|
| `/analizar-parcela` | Gemini `gemma-4-26b-a4b-it` (`PROVEEDOR_ANALISIS`) | Ollama `gemma4:e4b` si Gemini falla, no hay red o no hay API key. En ese caso `humedad_aparente="no_determinable"` y `humedad_preguntar_usuario=true` (e4b no distingue húmeda de seca) |
| `/preguntar` | Gemini `gemma-4-26b-a4b-it` (`PROVEEDOR_PREGUNTAR`) | Ollama `gemma4:e4b` si Gemini falla, no hay red o no hay API key |
| `/explicar` | Ollama (`PROVEEDOR_EXPLICAR`, funciona sin internet) | Si `PROVEEDOR_EXPLICAR=gemini` y Gemini falla, no hay red o no hay API key, cae a Ollama |

## Endpoints

| Ruta | Entrada | Salida |
|---|---|---|
| `GET /salud` | — | proveedor activo y si el modelo responde |
| `POST /analizar-parcela` | multipart `imagen` (jpeg/png/webp, ≤10 MB) | `{analisis, humedad_preguntar_usuario, respaldo, proveedor, modelo, intentos, latencia_ms}` |
| `POST /preguntar` | `{texto, municipio?, mes?}` (texto dictado por voz o escrito) | `{respuesta, respuesta_segmentos, pregunta_traducida, zapoteco: [{espanol, zapoteco, categoria}], zapoteco_pregunta, saludo, despedida, municipio, respaldo, proveedor, modelo, latencia_ms}` |
| `POST /traducir-zapoteco` | `{texto}` | `{traduccion, experimental: true, aviso, vocabulario_usado, respaldo, proveedor, modelo, latencia_ms}` (**experimental**, no revisada por hablantes) |
| `POST /analizar-cultivo` | multipart `imagen` + `cultivo` opcional | `{analisis: {es_planta, cultivo_visto, etapa, estado_general, sintomas, posibles_causas: [{nombre, tipo, confianza, senales}], confianza, observaciones}, pasos, aviso, zapoteco, modelo_local, respaldo, proveedor, modelo, intentos, latencia_ms}` |
| `POST /explicar` | `{municipio, cultivo, puntaje, datos_regla: {clave: {valor, fuente: foto\|campesino\|datos}}}` | `{explicacion, respaldo, proveedor, modelo, latencia_ms}` |

`analisis` solo trae atributos observables (`es_parcela`, `suelo_desnudo`, `humedad_aparente`,
`pendiente`, `piedras`, `cobertura_vegetal`, `confianza`, `observaciones`). Nunca fertilidad, nutrientes ni pH.
`confianza` es informativo: ninguna lógica lo usa.

Errores: `415` imagen inválida · `413` muy grande · `502` el modelo respondió mal dos veces · `503` Ollama/Gemini no disponible.

## Zapoteco en `/preguntar`

Gemma contesta **solo en español** con los datos de clima y cultivos del municipio
(`assets/data/recomendaciones.json`). Después, [`app/glosario.py`](app/glosario.py) busca en la respuesta
las palabras que tienen traducción en [`app/data/glosario.json`](app/data/glosario.json) y las devuelve en `zapoteco`.
El modelo nunca escribe zapoteco, así que no puede inventarlo.

Si la pregunta trae palabras en zapoteco ("¿Bata siembro dháh?"), el código la traduce
("¿cuándo siembro frijol?"), se la pasa así al modelo y la devuelve en `pregunta_traducida`.

`respuesta_segmentos` trae la respuesta en trozos; los que tienen `zapoteco` son palabras con traducción,
y la app los muestra dentro de la frase: "El **Dháh** (frijol) se siembra en junio…".

El reconocimiento de voz del teléfono escribe las palabras zapotecas como suenan en español
(por ejemplo "shiah" puede salir como "chía"). Cuando un hablante lo pruebe, se agrega cómo salió en
`alias_voz` de esa palabra en el glosario:

```json
{"espanol": "Lluvia", "zapoteco": "Shiah", "alias_voz": ["chía"], ...}
```

El glosario junta **dos variantes distintas** del zapoteco de la Sierra Norte, y cada palabra dice de cuál es
(`variante`), con las equivalencias en la otra (`otras_variantes`); la app siempre muestra la variante:

- `sierra_norte`: [vocabulario_zapoteco](https://dev-deivis.github.io/vocabulario_zapoteco/) del equipo.
- `jaltepec`: una selección de palabras del campo y del clima del *Diccionario Zapoteco (di'dz xi'dza')
  San Juan Jaltepec, municipio de Santiago Yaveo* (Hernández Andrade y López Nicolás, INPI, 2022).
  Llena los huecos del otro vocabulario: maíz *xhoꞌbaꞌ*, milpa *guiela*, sembrar *raz*, cosechar *rláp*.

`GET /variantes` devuelve el nombre y la fuente de cada una. Las entradas
con `"zapoteco": ""` (maíz, milpa, sembrar, cosechar, café…) faltan por confirmar con un hablante y no se muestran;
para agregarlas basta llenar ese campo.

### Traducción completa (experimental)

`/traducir-zapoteco` le pide a Gemma 4 la traducción de toda la respuesta, dándole como guía las palabras
del glosario verificado que aparecen en el texto. **No está revisada por hablantes**: puede tener errores
o mezclar otras variantes del zapoteco, y la app siempre la muestra marcada como EXPERIMENTAL.
El zapoteco verificado sigue siendo el del glosario.

Usamos Gemma y no Google Translate porque la API oficial de Google Cloud Translation no incluye el zapoteco.

## Revisar cultivo (`/analizar-cultivo`)

Gemma 4 mira la foto y dice qué cultivo parece, en qué etapa va (plántula, crecimiento, floración,
fruto, madurez) y su estado general (sano, problemas leves o serios). Si hay daño, da los síntomas
que se ven y hasta 3 **posibles** causas (insecto, ácaro, hongo, bacteria o virus, nutrientes, clima),
cada una con su probabilidad. No es un diagnóstico:

- El prompt le prohíbe recomendar productos, marcas, dosis o tratamientos.
- Los pasos a seguir (`pasos`) no los escribe el modelo: son frases fijas y seguras de
  [`app/cultivo.py`](app/cultivo.py), elegidas según el tipo de causa, y siempre terminan con
  llevar una muestra a un técnico.
- Se le pide razonamiento mínimo; sin eso Gemini cortaba a los 30 s.
- Si respondió el modelo local (`modelo_local: true`), la app avisa que es menos preciso.

## Pruebas

```bash
.venv/bin/python -m pytest -m "not integracion"   # unitarias, sin LLM
.venv/bin/python -m pytest -m integracion -s      # con el servidor corriendo + fotos en samples/
./tests/probar.sh                                  # lo mismo con curl
```

Fotos esperadas en `samples/`: `seca_desnuda.jpg`, `humeda_desnuda.jpg`, `milpa.jpg`, `mucho_cielo.jpg`, `no_parcela.jpg`.

## Limitaciones conocidas

- **Rangos de lluvia del CSV** (`assets/data/cultivos_sierra_norte.csv`): las columnas `precipitacion_min_mm` y `precipitacion_max_mm` mezclan criterios. En algunos cultivos parecen ser la lluvia del ciclo (de la siembra a la cosecha) y en otros la lluvia anual de la zona donde se siembran. Por eso el puntaje base de `generar_recomendaciones.py` todavía no compara la lluvia de forma consistente. Los rangos deben validarse con un agrónomo o con una fuente oficial (SIAP/INIFAP) antes de usar los puntajes como recomendación real.
