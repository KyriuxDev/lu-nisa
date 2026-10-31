# Lu-nisa 🌱

**Lu-nisa** es una app para agricultores de la Sierra Norte de Oaxaca que recomienda qué sembrar según el municipio, el mes y lo que se ve en una foto de la parcela. La foto la analiza **Gemma 4**, y la app explica cada recomendación con palabras sencillas, diciendo de dónde sale cada dato.

El nombre viene del zapoteco *lu nisa*, **"cara del agua"**.

---

## Modelos de IA que usamos

| Tarea | Modelo | Cómo se llama |
|---|---|---|
| Analizar la foto de la parcela | **Gemma 4 26B A4B** | `gemma-4-26b-a4b-it` vía **API de Gemini** (Google AI Studio) |
| Respaldo sin internet y explicaciones | **Gemma 4 E4B** | `gemma4:e4b` corriendo **local con Ollama** |

- El modelo se configura en [`backend/.env.example`](backend/.env.example) (`GEMINI_MODEL`, `OLLAMA_MODEL`) y se usa en [`backend/app/llm.py`](backend/app/llm.py).
- Si Gemini falla, no hay red o no hay API key, el backend cae automáticamente a Gemma 4 local.
- La app muestra en pantalla qué modelo respondió: *"Analizado con Gemma 4 26B"* o *"Analizado con Gemma 4 local"*.

---

## El problema

Municipios a pocos kilómetros de distancia tienen altitud, temperatura y lluvia muy distintas. La información agrícola que existe es genérica, la conexión en la sierra es inestable, y el conocimiento de las épocas de siembra se está perdiendo con la migración de los jóvenes.

## Cómo funciona

```
Municipio (67 de la Sierra Norte)  +  mes
        ↓
Foto de la parcela  ──→  Gemma 4 describe solo lo observable:
        │                 ¿es parcela?, humedad, pendiente, piedras, cobertura
        ↓
Puntaje por cultivo con datos de clima 2018-2023 y requerimiento de agua
        ↓
Explicación en español sencillo, citando la fuente de cada dato:
"se ve en tu foto" · "nos dijiste" · "en esta época suele llover 141 mm"
```

### Decisiones para no inventar

- **Gemma solo describe lo que se ve.** El prompt le prohíbe estimar fertilidad, nutrientes o pH, porque eso no se puede saber con una foto.
- **Las razones salen de los números.** La frase de la fecha de siembra se arma con datos ([`backend/app/razones.py`](backend/app/razones.py)) y el modelo solo la redacta.
- **Si el modelo local no puede distinguir tierra húmeda de seca, la app le pregunta al campesino** en lugar de adivinar.

---

## Hecho en el HackDay (31 de octubre de 2026)

El proyecto ya existía antes del evento (ver abajo). Esto es lo que agregamos hoy:

- [ ] **Preguntas por voz:** el campesino pregunta hablando ("¿ya puedo sembrar frijol?") y Gemma 4 responde con los datos de su municipio.
- [ ] **Respuesta en voz alta**, para quien no lee con facilidad.
- [ ] **Vocabulario zapoteco de la Sierra Norte** en las respuestas (*Shiah* = lluvia, *Yúu* = tierra, *Dháh* = frijol). Gemma responde en español y las palabras zapotecas las agrega el código desde un glosario verificado, así el modelo nunca inventa zapoteco.
- [ ] **Preguntar en zapoteco escrito:** "¿Bata siembro dháh?" se entiende como "¿cuándo siembro frijol?".
- [ ] **Traducción completa al zapoteco (experimental)** con Gemma 4, guiada por el glosario y marcada como no revisada.
- [x] **Licencia MIT** y README actualizado.

### Qué sigue

- **Revisión por hablantes:** que hablantes de la Sierra Norte revisen la traducción experimental y completen el glosario (maíz, milpa, sembrar, cosechar, café).
- **Frases verificadas:** plantillas como "En {mes} suelen llover {n} mm" traducidas una vez por un hablante, para dar respuestas completas en zapoteco sin traducción automática.
- **Voz en zapoteco:** el dictado del teléfono solo entiende español ("bata siembro dháh" se escucha como "mata siempre da"). Hace falta grabar a hablantes para entrenar el reconocimiento.

**Antes del evento:** app Flutter base, datos de clima por municipio y mes, y backend de análisis de fotos con Gemma 4.

---

## Tecnologías

| Capa | Tecnología |
|---|---|
| App | Flutter 3 + Dart, Provider, GoRouter |
| Backend | FastAPI (Python) |
| IA | Gemma 4 vía API de Gemini + Gemma 4 local con Ollama |
| Persistencia | SQLite local (historial de consultas) |
| Datos | JSON offline: 67 municipios × 12 meses, clima 2018-2023 |

Los datos cubren los distritos de **Ixtlán de Juárez**, **Villa Alta** y **Mixe**.

---

## Correr el proyecto

**Backend**

```bash
cd backend
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
cp .env.example .env          # pon tu GEMINI_API_KEY de Google AI Studio
ollama pull gemma4:e4b        # respaldo local
.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Más detalle de endpoints y pruebas en [`backend/README.md`](backend/README.md).

**App**

```bash
flutter pub get
flutter run --dart-define=BACKEND_URL=http://IP_DE_TU_COMPU:8000
```

El teléfono y la computadora del backend deben estar en la misma red.

---

## Limitaciones conocidas

- Los rangos de lluvia por cultivo deben validarse con un agrónomo o con SIAP/INIFAP antes de usarse como recomendación real.
- El análisis de fotos necesita el backend; sin internet funciona con Gemma 4 local, pero alguien tiene que tener la computadora con Ollama encendida.
- El vocabulario zapoteco varía entre comunidades; algunas palabras agrícolas (maíz, milpa, sembrar) faltan por confirmar con hablantes.

---

## Licencia

[MIT](LICENSE)
