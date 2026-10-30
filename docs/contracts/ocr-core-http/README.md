# Contrato que el integrador usa de `ocr-core` (HTTP)

Qué consume este repo del motor OCR `ocr-core`, visto desde el consumidor.
Describe lo que hacen `adapter/app/ocr_core_client.py` y
`adapter/app/worker.py`. El core es un servicio genérico que se despliega
aparte; este documento no reemplaza su documentación, pero basta para entender
y cambiar la integración sin ella.

## Conexión

- `OCR_CORE_URL`: URL interna del core en la red Docker `grh_network`.
  Vigente: `http://core-ocr:8000`.
- `OCR_CORE_HTTP_TIMEOUT_SECONDS` (30): tiempo máximo de cada llamada HTTP.
- Volumen compartido: el integrador y el core montan el mismo volumen NFS
  (`ocr-core_ocr_nfs_cache`) en `/nfs-cache`. El PDF de entrada y los
  artefactos de salida viajan como rutas dentro de ese volumen, no por HTTP.

## `GET /meta`: capacidades

El integrador lee `capabilities` y la guarda en caché
`OCR_CORE_META_TTL_SECONDS` (60 s). Antes de marcar un ítem como
`processing`, exige las capacidades que el trabajo necesita. Si falta alguna,
se detiene sin tocar la cola (`CoreCapabilityError`), y el ítem queda
pendiente:

| Capacidad | Cuándo se exige |
|---|---|
| `artifact_schemas.md == "ocr.markdown.document.v1"` | La cola pide `md` (RN-011) |
| `pdf_on_skip_reuse` | `OCR_SOURCE_REUSE_ENABLED=true` (RN-008) |
| `telemetry_schema` y `execution_provenance` | `OCR_TELEMETRY_FORWARD_ENABLED=true` |

Con `OCR_CORE_CAPABILITIES_REQUIRED=true`, el integrador verifica `/meta`
aunque el ítem no necesite ninguna capacidad. El log registra el release
(`release_id`, `version`) cada vez que cambia.

## `POST /jobs`: crear un trabajo

```json
{
  "source": {"path": "/nfs-cache/_inbox/normatividad_<queue_id>_<token>.pdf"},
  "artifacts": {
    "pdf":  {"path": "/nfs-cache/<expected.pdf_path>",  "overwrite": false},
    "text": {"path": "/nfs-cache/<expected.text_path>", "overwrite": false},
    "md":   {"path": "/nfs-cache/<expected.md_path>",   "overwrite": false}
  },
  "options": {
    "metadata": {"...": "ver más abajo"},
    "document_title": "Título compuesto por Normatividad o fallback",
    "pdf_on_skip": "reuse",
    "telemetry": {"level": "summary_and_pages"}
  },
  "idempotency_key": "<hash canónico de cola, intento, MD5 y solicitud>"
}
```

- Solo se piden los artefactos que hacen falta: los ya vigentes no se vuelven a
  pedir, salvo reproceso forzado, que lleva `overwrite: true` (RN-004).
- `document_title` solo viaja si se pidió `md` (decisión 0002).
- `pdf_on_skip` solo viaja con `OCR_SOURCE_REUSE_ENABLED=true`. Toma el valor
  de `execution_request.pdf_on_skip`, o `reuse` si no viene. Sin esa variable,
  el core usa su valor por defecto, `copy`.
- `telemetry` solo viaja con `OCR_TELEMETRY_FORWARD_ENABLED=true`.
- **Reintentos:** si hay `idempotency_key`, un error de red o un `5xx` se
  reintenta hasta `OCR_CORE_SUBMIT_MAX_RETRIES` (2) veces con la misma clave,
  y el core devuelve el mismo trabajo (RN-009). Un `4xx` no se reintenta.
- **Respuesta usada:** `job_id`.

### `options.metadata`

Un objeto opaco para el core, que lo conserva sin interpretarlo. Lo arma
`worker._text_artifact_metadata`, y el indexador de búsqueda usa estos campos:

`regulation_file_id`, `regulation_id`, `source_md5`, `pdf_path`, `text_path`,
`source_path`, `file_name`, `file_size`, `reg_num`, `reg_year`, `reg_date`,
`reg_title`, `reg_description`, `regulations_tipo`,
`regulations_tipos_sigla_id`, `regulation_type_id` y
`regulation_type_sigla_id`, más `md_path` cuando se pide `md`.

Las rutas (`*_path`) son relativas al volumen compartido.

## `GET /jobs/{job_id}`: esperar el resultado

El integrador consulta cada `OCR_CORE_JOB_POLL_INTERVAL_SECONDS` (2 s) hasta
que `status` deja de ser `queued` o `processing`, con un máximo de
`OCR_CORE_JOB_TIMEOUT_SECONDS` (1800 s). Con `OCR_QUEUE_HEARTBEAT_ENABLED=true`,
renueva el lease del ítem en Normatividad mientras espera (RN-010).

| Campo | Uso |
|---|---|
| `status` | `done`: reporta artefactos o `skip`. `blocked`: reporta `block`. `failed`: reporta `fail`, o `block` si el error es de firma digital (RN-003) |
| `preflight.decision` | `process` o `skip` (RN-002); `message` y `reason_code` viajan en el reporte |
| `artifacts.<nombre>.written` | El artefacto quedó escrito en su ruta |
| `artifacts.pdf.reused_source` | El PDF de origen se reutilizó sin copiarlo (RN-008) |
| `execution`, `metrics` | Se reenvían a Normatividad sin interpretarlos, si la telemetría está habilitada |
| `error` | Mensaje de un trabajo fallido |

Si el core no escribió un artefacto pedido, el callback no lo incluye y la cola
no se cierra (`finalize_queue: false`).

## Garantías que el integrador espera del core

- La escritura de artefactos es atómica, y con `overwrite: false` el core no
  pisa un archivo existente.
- La misma `idempotency_key` devuelve el mismo trabajo.
- El core copia la fuente a su almacenamiento privado antes de responder
  `202`, así que el integrador puede borrar el PDF del inbox apenas recibe el
  `job_id`.
- `options.metadata` llega sin cambios al JSONL.

## Pruebas

`adapter/tests/test_worker_reproceso.py`, `adapter/tests/test_worker_markdown.py`
y `adapter/tests/test_shadow_core_client.py` simulan este contrato.
