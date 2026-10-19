# SEQ-001 — Ciclo de vida de un item de cola

## Objetivo

Detallar técnicamente la secuencia real de llamadas que ejecuta `adapter/app/worker.py::_process_item` para procesar un item de la cola OCR de Normatividad — extraída directamente del código (no diseñada a priori).

## Requisitos / análisis relacionados

- RN-001 a RN-004 (reglas de negocio del worker, ver [reglas-negocio.md](../../reglas-negocio.md))

## Precondiciones

- Existe al menos un item disponible en la cola de Normatividad (`pull_next()` devuelve un item).

## Participantes

- Actor iniciador: bucle del worker (`_run_worker_loop`)
- Cliente/API externa: `normatividad_client` (Normatividad)
- Servicio/componente de dominio: `ocr_core_client` (HTTP hacia `ocr-core`)
- Persistencia: filesystem compartido (`OCR_SHARED_CACHE_DIR`, `_inbox/`)

> Sin base de datos propia — el estado real vive en la cola de Normatividad (fuera de este repo).

## Secuencia

```mermaid
sequenceDiagram
    participant Loop as worker._run_worker_loop
    participant Norm as normatividad_client
    participant FS as Filesystem compartido
    participant Core as ocr_core_client (→ ocr-core)
    participant Shadow as shadow_core_client (→ core-ocr)

    Loop->>Norm: pull_next()
    Norm-->>Loop: item (queue_id, payload)
    Loop->>Norm: mark_processing(queue_id)
    Norm-->>Loop: processing_payload

    alt sin artefactos soportados solicitados
        Loop->>Norm: skip(queue_id, reason="no_supported_artifacts_requested")
    else artefactos pdf/text solicitados
        opt no cacheado
            Loop->>Norm: download_source(queue_id, inbox_pdf)
            Norm-->>FS: escribe PDF en _inbox/
        end
        Loop->>Core: submit_job(pdf, options, artifacts_requested)
        Core-->>Loop: job_id
        opt OCR_SHADOW_ENABLED=true
            Loop->>Shadow: submit_job(mismo source.path, salidas privadas)
            Shadow-->>Loop: shadow_job_id o error aislado
        end
        Loop->>Core: wait_for_job(job_id) [polling GET /jobs/{id}]
        Core-->>Loop: job_result {status, artifacts}

        alt status == "blocked"
            Loop->>Norm: block(queue_id, reason)
        else status == "failed" con error de firma
            Loop->>Norm: block(queue_id, reason="signature_detected")
        else status == "done" y sin artefactos nuevos (ya era servible)
            Loop->>Norm: skip(queue_id)
        else status == "done" con artefactos
            Loop->>Norm: report_artifacts(queue_id, artifacts)
            Loop->>Norm: complete(queue_id, shared_pdf_path, duration_ms)
        end
    end
```

## Flujos alternativos / errores relevantes

- **RN-001**: sin artefactos soportados solicitados → `skip` inmediato, sin descargar el PDF fuente.
- **RN-002**: si el PDF ya tenía texto útil (`skip` en preflight de `ocr-core`) y solo se pidió `pdf`, se reporta `skip` — no se publica un artefacto "nuevo".
- **RN-003**: si `ocr-core` reporta `failed` con mensaje de error de firma digital detectado **durante** el OCR, se reclasifica como `block` ante Normatividad en vez de `fail`.
- **RN-004**: artefactos ya cacheados (`has_pdf`/`has_text` en `true` y archivo existente) no se vuelven a pedir a `ocr-core`.
- **RN-007**: un rechazo o fallo del core shadow solo se registra; el flujo
  oficial continúa y es el único que reporta estados o artefactos.
- Error de descarga del PDF fuente (`QueueSourceUnavailableError`): se reporta `fail(queue_id, ...)`.

## Postcondiciones

- El item de cola queda en un estado terminal ante Normatividad: `completed`/`skipped`/`blocked`/`failed`.
- Artefactos (si se generaron) quedan escritos en `OCR_SHARED_CACHE_DIR`.

## Consistencia arquitectónica

Los participantes corresponden a los módulos documentados en [arquitectura.md](../../arquitectura/arquitectura.md): `adapter/app/worker.py`, cliente HTTP hacia `ocr-core` (motor OCR externo, ver `SEQ-001` de ese repositorio para el detalle interno del procesamiento).
