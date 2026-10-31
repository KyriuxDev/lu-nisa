# Lu-nisa 🌱

**Lu-nisa** es una app para campesinos de la Sierra Norte de Oaxaca. Les dice **qué sembrar y cuándo** con datos de clima de su municipio, **revisa su cultivo con una foto**, contesta **preguntas por voz** y les habla con **palabras en zapoteco**. Todo con **Gemma 4**: en la nube cuando hay señal y **en la computadora de la comunidad cuando no hay internet**.

El nombre viene del zapoteco *lu nisa*, **"cara del agua"**. En el zapoteco de San Juan Jaltepec, *nisa* significa agua.

> Hecho en el **Hacktoberfest Hack Day Oaxaca x Oaxacoders** (31 de octubre de 2026).

---

## Modelos de IA

| Tarea | Modelo | Dónde corre |
|---|---|---|
| Preguntas por voz, revisar cultivo por foto, analizar parcela, traducción al zapoteco | **Gemma 4 26B A4B** · `gemma-4-26b-a4b-it` | **API de Gemini** (Google AI Studio) |
| Respaldo sin internet para todo lo anterior, y explicaciones | **Gemma 4 E4B** · `gemma4:e4b` | **Local, con Ollama** (modelo open-weight) |

- Se configuran en [`backend/.env.example`](backend/.env.example) (`GEMINI_MODEL`, `OLLAMA_MODEL`) y se usan en [`backend/app/llm.py`](backend/app/llm.py).
- Si Gemini falla, no hay red o no hay API key, el backend usa Gemma 4 local automáticamente.
- La app siempre dice en pantalla qué modelo respondió: *"Respondido con Gemma 4 26B"* o *"Gemma 4 local (sin internet)"*.

### Cómo encaja en los retos

- **Best Use of Gemma 4:** Gemma 4 por la API de Gemini, **multimodal** (texto + imagen): revisa fotos del cultivo, contesta preguntas con datos reales y traduce al zapoteco guiado por un diccionario.
- **Best Open-Source AI Project:** repositorio público con licencia **MIT**; Gemma 4 **open-weight corriendo local con Ollama** como respaldo sin internet, que es lo normal en la sierra.

---

## El problema

Municipios a pocos kilómetros de distancia tienen altitud, temperatura y lluvia muy distintas. La información agrícola que existe es genérica, la señal en la sierra es inestable, muchos productores prefieren hablar a escribir, y el conocimiento de las épocas de siembra y la lengua zapoteca se están perdiendo con la migración de los jóvenes.

---

## Qué hace

### 🎙️ Pregúntale a Lu-nisa (voz)
El campesino pregunta hablando ("¿cuándo siembro frijol?") y la respuesta se **lee en voz alta**. Gemma 4 contesta **solo con los datos de su municipio**: clima de 2018-2023, cultivos, meses de siembra y cosecha. El código le da ya calculado qué se siembra este mes y qué cultivo sigue, así no inventa fechas.

### 🗣️ Zapoteco sin inventar
- **Gemma responde en español, y el zapoteco lo pone el código** desde un glosario verificado: *"El **Dháh** (frijol) se siembra en junio…"*. Si el modelo intenta escribir zapoteco, el código quita esa oración.
- **Se puede preguntar en zapoteco escrito:** *"¿Bata siembro dháh?"* → "Entendimos: ¿cuándo siembro frijol?".
- **Dos variantes, siempre etiquetadas:** el vocabulario de la Sierra Norte del equipo y palabras del campo del diccionario de **San Juan Jaltepec** (maíz *xhoꞌbaꞌ*, milpa *guiela*, sembrar *raz*, cosechar *rláp*). Cada palabra dice de qué variante es, por ejemplo *Shiah* lluvia · Sierra Norte · *guio lasi* en Jaltepec.
- **Traducción completa (experimental):** Gemma 4 traduce la respuesta al zapoteco de Jaltepec **oración por oración**, imitando **oraciones reales del diccionario** de la comunidad que comparten palabras con cada una (~1,900 ejemplos). Si una oración sale repetitiva, se queda en español. Siempre se marca como **EXPERIMENTAL**: falta que la revise un hablante.

### 🌿 Revisar mi cultivo (foto)
Gemma 4 mira la foto y dice qué cultivo parece, **en qué etapa va** y **cómo se ve su salud**. Si hay daño, da los síntomas y hasta 3 **posibles** causas (insectos, ácaros, hongos, nutrientes, clima), cada una con su probabilidad.
- **No es diagnóstico** y **nunca recomienda productos ni dosis**: los pasos a seguir son frases fijas y seguras del código y terminan con "lleva una muestra a un técnico".
- **Gemini y Gemma local corren al mismo tiempo** y se usa la primera respuesta buena, así no se espera a que Gemini falle.

### 📷 Recomendación por parcela (antes del evento)
Gemma 4 describe la foto de la parcela (humedad, pendiente, piedras, cobertura), el código calcula el puntaje de cada cultivo y la app lo explica citando la fuente: *"se ve en tu foto"*, *"nos dijiste"*, *"en esta época suele llover 141 mm"*.

---

## Decisiones para no inventar

- **Gemma solo describe lo que se ve.** No estima fertilidad, nutrientes ni pH con una foto.
- **Los números los calcula el código** (fechas de siembra, lluvia, qué toca sembrar), y el modelo solo los redacta.
- **El zapoteco verificado nunca lo escribe el modelo.** La traducción automática va aparte y marcada.
- **Nada de productos ni dosis** en la revisión del cultivo.
- **Pruebas automáticas**: 79 en el backend, incluidas las que reproducen los errores reales que encontramos en el teléfono (traducción en bucle, "no tengo información de qué sembrar", Gemini lento con fotos).

---

## Hecho en el Hack Day (31 de octubre de 2026)

- [x] **Preguntas por voz** con respuesta en voz alta.
- [x] **Zapoteco en las respuestas** desde un glosario verificado, con dos variantes etiquetadas (Sierra Norte y San Juan Jaltepec).
- [x] **Preguntar en zapoteco escrito.**
- [x] **Traducción completa al zapoteco (experimental)** guiada con oraciones del diccionario de Jaltepec.
- [x] **Revisar mi cultivo por foto** (etapa, salud, posibles plagas y enfermedades), con Gemini y local en paralelo.
- [x] **Calendario de siembra** calculado para que el modelo no invente fechas.
- [x] **Licencia MIT**, README y pruebas.

**Antes del evento:** app Flutter base, datos de clima por municipio y mes, y backend de análisis de parcela con Gemma 4.

**Equipo:** KyriuxDev y dev-deivis. Usamos Claude (Anthropic) como asistente de programación.

### Qué sigue
- **Revisión por hablantes** de la traducción experimental y del glosario (falta, por ejemplo, *helada*).
- **Frases verificadas por hablantes** para respuestas completas en zapoteco sin traducción automática.
- **Voz en zapoteco:** el dictado del teléfono solo entiende español ("bata siembro dháh" se escucha "mata siempre da"). Hace falta grabar a hablantes.
- **Gemma en el teléfono** (E2B/E4B) para no depender de una computadora.

---

## Pruébalo: preguntas de ejemplo

Con **Ixtlán de Juárez** como municipio:

| Pregunta | Qué muestra |
|---|---|
| ¿Cuándo siembro frijol? | Respuesta con datos, *Dháh* y *raz*; luego "Traducir todo al zapoteco" |
| ¿Cuándo se cosecha el maíz? | Palabras de Jaltepec: *xhoꞌbaꞌ*, *rláp* |
| ¿Qué puedo sembrar este mes? | "En octubre no se siembra… el próximo es el trigo, en noviembre" |
| ¿Cuánto llueve en esta época? | Dos variantes: *Shiah* / *guio lasi* |
| ¿Bata siembro dháh? (escrita) | "Entendimos: ¿cuándo siembro frijol?" |

---

## Tecnologías

| Capa | Tecnología |
|---|---|
| App | Flutter 3 + Dart, Provider, GoRouter, speech_to_text, flutter_tts |
| Backend | FastAPI (Python), pytest |
| IA | Gemma 4 por la API de Gemini + Gemma 4 local con Ollama |
| Datos | 67 municipios × 12 meses, clima 2018-2023; glosario zapoteco con dos variantes |

Los datos cubren los distritos de **Ixtlán de Juárez**, **Villa Alta** y **Mixe**.

---

## Correr el proyecto

**Backend**

```bash
cd backend
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt pymupdf
cp .env.example .env          # pon tu GEMINI_API_KEY de Google AI Studio
ollama pull gemma4:e4b        # respaldo local
# Opcional, mejora la traducción: oraciones del diccionario de Jaltepec (no van en el repo)
.venv/bin/python scripts/extraer_ejemplos_jaltepec.py ruta/al/Diccionario-zapoteco-San-Juan-Jaltepec.pdf
.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

Endpoints, pruebas y detalles en [`backend/README.md`](backend/README.md).

**App**

```bash
flutter pub get
flutter run --dart-define=BACKEND_URL=http://IP_DE_TU_COMPU:8000
```

El teléfono y la computadora deben estar en la misma red Wi‑Fi.

---

## Fuentes

- Vocabulario zapoteco de la Sierra Norte: [vocabulario_zapoteco](https://dev-deivis.github.io/vocabulario_zapoteco/).
- Hernández Andrade, E. y López Nicolás, O. (2022). *Diccionario Zapoteco (di'dz xi'dza') San Juan Jaltepec, municipio de Santiago Yaveo, Sierra Norte de Oaxaca.* INPI. ISBN 978-607-8799-31-2. Usamos una selección de palabras en el glosario; las oraciones de ejemplo se extraen localmente del PDF y no se publican.
- Clima: promedios 2018-2023 por municipio (ver `descargar_clima.py`).

## Limitaciones

- Los rangos de lluvia por cultivo deben validarse con un agrónomo o con SIAP/INIFAP.
- La traducción completa es experimental: no la ha revisado un hablante.
- La revisión del cultivo no sustituye a un técnico.
- Sin internet hace falta una computadora con Ollama encendida en la comunidad.

## Licencia

[MIT](LICENSE)
