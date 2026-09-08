# Reglas de negocio

Reglas funcionales de este repo. El detalle narrativo (el "por qué" detrás
de cada una) vive en `../../context.md` — esta tabla es el resumen
trazable, no lo duplica.

| ID | Regla | Fuente/justificación | Requisitos relacionados |
|---|---|---|---|
| RN-001 | Si la cola no solicita `pdf` ni `text`, se reporta `skip` sin descargar nada del PDF fuente. | `adapter/app/worker.py::_process_item`. Evita gastar ancho de banda/CPU en algo que nadie pidió. | Contrato de artefactos de Normatividad (`requested_artifacts`) |
| RN-002 | Si el PDF ya tiene texto útil (`preflight.decision == "skip"`) y **solo** se pidió `pdf` (no `text`), se reporta `skip` — no se publica el PDF como artefacto nuevo. | `adapter/app/worker.py`, comentario en `_process_item`. `ocr-core` no puede inferir esta regla porque es una decisión de negocio, no técnica: no hay nada "nuevo" que aportar si el documento ya es servible tal cual. | Ver `context.md`, sección "Reglas de negocio del worker que sobrevivieron..." |
| RN-003 | Si `ocr-core` reporta `status: failed` con un mensaje que parece error de firma digital detectada **durante** el OCR (no en el preflight inicial), se reclasifica como `block` ante Normatividad en vez de `fail`. | `adapter/app/worker.py::_looks_like_signature_error`. Un documento firmado digitalmente no debe reintentarse indefinidamente como si fuera un error transitorio. | — |
| RN-004 | Artefactos ya cacheados (`has_pdf`/`has_text` en `true` **y** archivo existente en el storage compartido) no se vuelven a pedir a `ocr-core`. | `adapter/app/worker.py::_artifact_cached`. Evita reprocesar documentos que ya tienen resultado vigente. | — |
| RN-005 | Al encolar (`RegulationFileOcrManager::enqueue()`, en Normatividad): si el archivo no es elegible y no se fuerza, se marca `skipped` sin crear item de cola. Si ya hay un item activo para ese archivo, se fusionan los artefactos pedidos en vez de crear uno nuevo. | Código de Normatividad (no de este repo) — documentado aquí porque el adaptador depende de este comportamiento. Ver `../../context.md`, sección "Reglas de negocio de `RegulationFileOcrManager::enqueue()`". | — |
| RN-006 | El esquema de búsqueda (`search/app/search_common.py`) indexa campos específicos de Normatividad (`regulation_file_id`, `reg_year`, etc.) en vez de un `metadata` genérico. | Decisión de diseño explícita, no una limitación técnica — ver `arquitectura/arquitectura.md`, sección "Decisión de diseño". | Se revisita si algún día se sirve a otra plataforma. |

## Gaps reales

No existe un listado formal de requisitos funcionales más allá de estas
reglas ya implementadas — nunca se hizo un levantamiento de requisitos
previo al desarrollo (se construyó de forma incremental, documentado en
`../../context.md`). `docs/documentacion-tecnica/reglas-negocio.md` queda
pendiente de creación; esta tabla de reglas de negocio es lo único
verificable hoy contra el código real.
