# Reglas de negocio

Reglas funcionales de este repo. El detalle narrativo (el "por qué" detrás
de cada una) vive en `../../context.md` — esta tabla es el resumen
trazable, no lo duplica.

| ID | Regla | Fuente/justificación | Requisitos relacionados |
|---|---|---|---|
| RN-001 | Si la cola no solicita `pdf` ni `text`, se reporta `skip` sin descargar nada del PDF fuente. | `adapter/app/worker.py::_process_item`. Evita gastar ancho de banda/CPU en algo que nadie pidió. | Contrato de artefactos de Normatividad (`requested_artifacts`) |
| RN-002 | Si el PDF ya tiene texto útil (`preflight.decision == "skip"`) y **solo** se pidió `pdf` (no `text`), se reporta `skip` — no se publica el PDF como artefacto nuevo. | `adapter/app/worker.py`, comentario en `_process_item`. `ocr-core` no puede inferir esta regla porque es una decisión de negocio, no técnica: no hay nada "nuevo" que aportar si el documento ya es servible tal cual. | Ver `context.md`, sección "Reglas de negocio del worker que sobrevivieron..." |
| RN-003 | Si `ocr-core` reporta `status: failed` con un mensaje que parece error de firma digital detectada **durante** el OCR (no en el preflight inicial), se reclasifica como `block` ante Normatividad en vez de `fail`. | `adapter/app/worker.py::_looks_like_signature_error`. Un documento firmado digitalmente no debe reintentarse indefinidamente como si fuera un error transitorio. | — |
| RN-004 | Artefactos ya cacheados (`has_pdf`/`has_text` en `true` **y** archivo existente en el storage compartido) no se vuelven a pedir a `ocr-core`, salvo que Normatividad marque ese artefacto en `execution_request.reprocess_artifacts` y `OCR_FORCE_REPROCESS_ENABLED` esté activo. Si llega `execution_request`, lo servido desde cache se reporta con `written=false` para no registrarse como versión nueva. | `adapter/app/worker.py::_artifact_cached` y cálculo de `needs_*`. Evita trabajo accidental y permite regeneración explícita. | — |
| RN-005 | Al encolar (`RegulationFileOcrManager::enqueue()`, en Normatividad): si el archivo no es elegible y no se fuerza, se marca `skipped` sin crear item de cola. Si ya hay un item activo para ese archivo, se fusionan los artefactos pedidos en vez de crear uno nuevo. | Código de Normatividad (no de este repo) — documentado aquí porque el adaptador depende de este comportamiento. Ver `../../context.md`, sección "Reglas de negocio de `RegulationFileOcrManager::enqueue()`". | — |
| RN-006 | El esquema de búsqueda (`search/app/search_common.py`) indexa campos específicos de Normatividad (`regulation_file_id`, `reg_year`, etc.) en vez de un `metadata` genérico. | Decisión de diseño explícita, no una limitación técnica — ver `arquitectura/arquitectura.md`, sección "Decisión de diseño". | Se revisita si algún día se sirve a otra plataforma. |
| RN-007 | El despacho shadow es de mejor esfuerzo: reutiliza la fuente NFS, escribe solo en el volumen privado del candidato y ningún fallo o resultado suyo modifica estados, callbacks ni artefactos oficiales. | `adapter/app/worker.py::_submit_shadow_job` y `adapter/app/shadow_core_client.py`. | Piloto comparativo no autoritativo. |
| RN-008 | Un preflight `skip` con `pdf_on_skip=reuse` reporta un artefacto lógico `source_reused`; nunca presenta una copia del PDF fuente como archivo generado. | Flags/capacidades de reuse en `adapter/app/worker.py`. | El core y Munis deben anunciar/aceptar el contrato antes de activarlo. |
| RN-009 | La clave idempotente combina cola, intento, MD5 de fuente y hash canónico de solicitud/reproceso/opciones. | `adapter/app/worker.py::_idempotency_key`. | Permite reintentar HTTP sin duplicar un job. |
| RN-010 | Un worker solo procesa y reporta mientras conserva la propiedad del lease; los jobs largos renuevan el lease cuando el heartbeat está activo. | `mark_processing`, heartbeat y callbacks con `processor`. | La recuperación de `processing` se activa únicamente junto con heartbeat. |

## Gaps reales

No existe un listado formal de requisitos funcionales más allá de estas
reglas ya implementadas — nunca se hizo un levantamiento de requisitos
previo al desarrollo (se construyó de forma incremental, documentado en
`../../context.md`). Esta tabla es el conjunto verificable hoy contra el
código real.
