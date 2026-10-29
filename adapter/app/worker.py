"""
OCR Worker — consumidor activo de la cola de Normatividad.

Flujo por iteracion:
  1. pull_next()              -> pide el siguiente trabajo a Normatividad
  2. 204 -> esperar y reintentar
  3. Trabajo disponible:
       a. mark_processing()     -> notifica inicio
       b. download_source()     -> descarga PDF original al inbox compartido
       c. ocr_core_client.submit_job() + wait_for_job()
                                 -> ocr-core corre preflight + OCR + genera
                                    artefactos, escribiendolos directo en el
                                    storage compartido (POST /jobs, ver
                                    ocr-core/api.md)
       d. interpretar preflight.decision y job.status, reportar a
          Normatividad (report_artifacts / skip / block / complete)
  4. Cualquier error          -> fail() + esperar

Este worker NO importa el motor OCR. Todo el procesamiento vive en ocr-core,
un servicio HTTP separado (ver OCR_CORE_URL). Este adaptador solo conoce el
dominio Normatividad: como leer la cola, que decisiones de negocio tomar
segun el resultado, y como reportar de vuelta.

Variables de entorno relevantes:
  NORMATIVIDAD_BASE_URL             URL base de Normatividad (ej. http://munis:8000)
  NORMATIVIDAD_OCR_TOKEN            Bearer token para autenticar contra Normatividad
  OCR_CORE_URL                      URL interna de ocr-core (ej. http://ocr-core:8000)
  OCR_WORKER_NAME                   Nombre descriptivo del worker (logs)
  OCR_WORKER_CONCURRENCY            Cantidad de consumidores paralelos dentro del servicio (default: 1)
  OCR_POLL_INTERVAL_SECONDS         Segundos a esperar si la cola esta vacia (default: 10)
  OCR_WORKER_ENABLED                "false" para deshabilitar sin borrar el contenedor (default: true)
  OCR_CALLBACK_TIMEOUT_SECONDS      Timeout HTTP para callbacks a Normatividad (default: 30)
  OCR_DOWNLOAD_TIMEOUT_SECONDS      Timeout HTTP para descarga del PDF fuente (default: 120)
  OCR_WORKER_MAX_CONSECUTIVE_ERRORS Detener el worker tras N errores consecutivos (default: 20)
  OCR_SHARED_CACHE_DIR              Raiz de storage compartido con ocr-core (default: /nfs-cache)
  OCR_CORE_JOB_TIMEOUT_SECONDS      Timeout esperando a que un job de ocr-core termine (default: 1800)
  OCR_SHADOW_ENABLED                Duplica jobs al core candidato (default: false)
  OCR_SHADOW_CORE_URL               URL interna del core candidato
  OCR_SHADOW_OUTPUT_ROOT            Raiz privada de resultados para revision
"""

import logging
import hashlib
import json
import multiprocessing as mp
import os
import signal
import sys
import time
import uuid
from pathlib import Path
from typing import Any

from app import normatividad_client
from app import ocr_core_client
from app import shadow_core_client

# ---------------------------------------------------------------------------
# Configuracion del worker
# ---------------------------------------------------------------------------

WORKER_NAME: str = os.getenv("OCR_WORKER_NAME", "normatividad-worker")
WORKER_CONCURRENCY: int = max(1, int(os.getenv("OCR_WORKER_CONCURRENCY", "1")))
POLL_INTERVAL: float = float(os.getenv("OCR_POLL_INTERVAL_SECONDS", "10"))
WORKER_ENABLED: bool = os.getenv("OCR_WORKER_ENABLED", "true").lower() not in (
    "0",
    "false",
    "no",
)
MAX_CONSECUTIVE_ERRORS: int = int(os.getenv("OCR_WORKER_MAX_CONSECUTIVE_ERRORS", "20"))

SHARED_CACHE_DIR = Path(os.getenv("OCR_SHARED_CACHE_DIR", "/nfs-cache"))
INBOX_DIR = SHARED_CACHE_DIR / "_inbox"


def _env_enabled(name: str, default: bool = False) -> bool:
    fallback = "true" if default else "false"
    return os.getenv(name, fallback).strip().lower() in {"1", "true", "yes"}


FORCE_REPROCESS_ENABLED = _env_enabled("OCR_FORCE_REPROCESS_ENABLED")
TELEMETRY_FORWARD_ENABLED = _env_enabled("OCR_TELEMETRY_FORWARD_ENABLED")
SOURCE_REUSE_ENABLED = _env_enabled("OCR_SOURCE_REUSE_ENABLED")
CORE_CAPABILITIES_REQUIRED = _env_enabled("OCR_CORE_CAPABILITIES_REQUIRED")
QUEUE_HEARTBEAT_ENABLED = _env_enabled("OCR_QUEUE_HEARTBEAT_ENABLED")
QUEUE_HEARTBEAT_SECONDS = max(10.0, float(os.getenv("OCR_QUEUE_HEARTBEAT_SECONDS", "60")))
# Quien encola decide qué artefactos pide; md exige un core que anuncie su esquema.
MARKDOWN_SCHEMA = "ocr.markdown.document.v1"
SUPPORTED_ARTIFACTS = {"pdf": True, "text": True, "md": True}

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=os.getenv("OCR_WORKER_LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
    stream=sys.stdout,
)
logger = logging.getLogger(WORKER_NAME)


def _submit_shadow_job(
    source_path: Path,
    *,
    queue_id: Any,
    needs_pdf: bool,
    needs_text: bool,
    worker_logger: logging.Logger,
) -> str | None:
    """Despacha una copia no autoritativa; nunca propaga errores al flujo oficial."""
    if not shadow_core_client.enabled():
        return None
    artifacts = {
        name
        for name, requested in {"pdf": needs_pdf, "text": needs_text}.items()
        if requested
    }
    if not artifacts:
        return None
    try:
        accepted = shadow_core_client.submit_job(
            source_path,
            queue_id=queue_id,
            artifacts=artifacts,
        )
    except Exception as exc:
        worker_logger.warning(
            "Shadow no aceptado queue_id=%s; el flujo oficial continua: %s",
            queue_id,
            exc,
        )
        return None

    shadow_job_id = str(accepted["job_id"])
    worker_logger.info(
        "Job shadow aceptado queue_id=%s | shadow_job_id=%s | reused=%s",
        queue_id,
        shadow_job_id,
        bool(accepted.get("idempotent_reuse")),
    )
    return shadow_job_id

# ---------------------------------------------------------------------------
# Senales de parada limpia
# ---------------------------------------------------------------------------

_stop_requested = False


def _handle_signal(signum, _frame):
    global _stop_requested
    logger.info("Senal %s recibida, deteniendo worker...", signum)
    _stop_requested = True


signal.signal(signal.SIGTERM, _handle_signal)
signal.signal(signal.SIGINT, _handle_signal)


def _worker_name_for_index(index: int) -> str:
    if WORKER_CONCURRENCY <= 1:
        return WORKER_NAME
    return f"{WORKER_NAME}-{index + 1}"


def _worker_logger(worker_name: str) -> logging.Logger:
    return logging.getLogger(worker_name)


# ---------------------------------------------------------------------------
# Procesamiento de un item de la cola
# ---------------------------------------------------------------------------


def _process_item(item: dict, worker_name: str, worker_logger: logging.Logger) -> None:
    """
    Procesa un item de la cola de Normatividad de principio a fin.

    Args:
        item: Diccionario retornado por pull_next(). Debe contener queue_id.
    """
    payload = item.get("data", item)
    queue_id = payload.get("queue_id") or payload.get("id")
    if not queue_id:
        raise ValueError(f"Item sin queue_id: {item}")

    worker_logger.info(
        "Iniciando procesamiento queue_id=%s | pull_next_meta=%s",
        queue_id,
        _safe_meta(payload),
    )

    capabilities = _required_capabilities(payload)
    core_meta = _validate_core_capabilities(capabilities)
    processing_response = normatividad_client.mark_processing(queue_id, worker_name=worker_name)
    processing_payload = processing_response.get("data", processing_response)

    processing_status = (
        processing_payload.get("status") if isinstance(processing_payload, dict) else None
    )
    if processing_status != "processing":
        raise RuntimeError(
            f"mark_processing no confirmo processing para queue_id={queue_id}: "
            f"status={processing_status}"
        )
    if isinstance(processing_payload, dict) and processing_payload.get("queue_id"):
        payload = processing_payload

    worker_logger.info(
        "queue_id=%s marcado processing | processing_meta=%s",
        queue_id,
        _safe_meta(processing_payload) if isinstance(processing_payload, dict) else processing_payload,
    )

    requested_artifacts = _requested_artifacts(payload)
    reprocess_artifacts = _reprocess_artifacts(payload)
    expected_artifacts = _expected_artifacts(payload)
    unsupported_artifacts = {
        name: True
        for name, requested in requested_artifacts.items()
        if requested and not SUPPORTED_ARTIFACTS.get(name, False)
    }
    planned_artifacts = {
        name: True
        for name, requested in requested_artifacts.items()
        if requested and SUPPORTED_ARTIFACTS.get(name, False)
    }

    if not planned_artifacts:
        worker_logger.info(
            "queue_id=%s omitido: la cola no solicita artefactos soportados | requested=%s",
            queue_id,
            requested_artifacts,
        )
        normatividad_client.skip(
            queue_id,
            message="Cola omitida: este worker no atiende los artefactos solicitados",
            reason_code="no_supported_artifacts_requested",
            duration_ms=0,
            preflight={
                "decision": "skip",
                "reason_code": "no_supported_artifacts_requested",
                "requested_artifacts": requested_artifacts,
                "unsupported_artifacts": unsupported_artifacts,
                "expected_artifacts": expected_artifacts,
            },
            processor=worker_name,
        )
        return

    start_time = time.monotonic()
    token = uuid.uuid4().hex[:12]
    # Carpeta única por item con el nombre real del documento: ocr-core deriva
    # de ese nombre el título del Markdown.
    inbox_pdf = (
        INBOX_DIR / f"normatividad_{queue_id}_{token}" / f"{_document_name(payload)}.pdf"
    )

    shared_pdf_path = _resolve_expected_artifact_path(payload, "pdf")
    shared_text_path = _resolve_expected_artifact_path(payload, "text")
    shared_md_path = _resolve_expected_artifact_path(payload, "md")
    pdf_cached = _artifact_cached(payload, "pdf", shared_pdf_path)
    text_cached = _artifact_cached(payload, "text", shared_text_path)
    md_cached = _artifact_cached(payload, "md", shared_md_path)

    force_pdf = bool(FORCE_REPROCESS_ENABLED and reprocess_artifacts.get("pdf"))
    force_text = bool(FORCE_REPROCESS_ENABLED and reprocess_artifacts.get("text"))
    force_md = bool(FORCE_REPROCESS_ENABLED and reprocess_artifacts.get("md"))
    needs_pdf = bool(planned_artifacts.get("pdf") and (force_pdf or not pdf_cached))
    needs_text = bool(planned_artifacts.get("text") and (force_text or not text_cached))
    needs_md = bool(planned_artifacts.get("md") and (force_md or not md_cached))

    produced_artifacts: dict[str, bool] = {}
    reportable_artifacts: dict[str, object] = {}
    preflight: dict | None = None
    job_result: dict | None = None

    try:
        if needs_pdf or needs_text or needs_md:
            normatividad_client.download_source(queue_id, inbox_pdf)
            worker_logger.info(
                "PDF descargado a inbox compartido queue_id=%s | %s (%d bytes)",
                queue_id, inbox_pdf, inbox_pdf.stat().st_size,
            )

            job_artifacts: dict[str, dict[str, Any]] = {}
            if needs_pdf:
                if shared_pdf_path is None:
                    raise RuntimeError(
                        "La cola solicita PDF pero artifacts.expected.pdf_path no fue provisto"
                    )
                job_artifacts["pdf"] = {
                    "path": str(shared_pdf_path),
                    "overwrite": force_pdf,
                }
            if needs_text:
                if shared_text_path is None:
                    raise RuntimeError(
                        "La cola solicita TEXT pero artifacts.expected.text_path no fue provisto"
                    )
                job_artifacts["text"] = {
                    "path": str(shared_text_path),
                    "overwrite": force_text,
                }
            if needs_md:
                if shared_md_path is None:
                    raise RuntimeError(
                        "La cola solicita MD pero artifacts.expected.md_path no fue provisto"
                    )
                job_artifacts["md"] = {
                    "path": str(shared_md_path),
                    "overwrite": force_md,
                }

            core_options = {
                "metadata": _text_artifact_metadata(
                    payload, shared_pdf_path, shared_text_path,
                    shared_md_path if needs_md else None,
                ),
            }
            execution_request = _execution_request(payload)
            if SOURCE_REUSE_ENABLED:
                core_options["pdf_on_skip"] = str(
                    execution_request.get("pdf_on_skip") or "reuse"
                )
            if TELEMETRY_FORWARD_ENABLED:
                core_options["telemetry"] = {
                    "level": str(
                        execution_request.get("telemetry_level") or "summary_and_pages"
                    )
                }

            job_id = ocr_core_client.submit_job(
                inbox_pdf,
                options=core_options,
                artifacts=job_artifacts,
                idempotency_key=_idempotency_key(payload, core_options),
            )
            worker_logger.info("Job enviado a ocr-core queue_id=%s | job_id=%s", queue_id, job_id)
            _submit_shadow_job(
                inbox_pdf,
                queue_id=queue_id,
                needs_pdf=needs_pdf,
                needs_text=needs_text,
                worker_logger=worker_logger,
            )
            heartbeat = None
            if QUEUE_HEARTBEAT_ENABLED:
                heartbeat = lambda: normatividad_client.heartbeat(
                    queue_id,
                    worker_name=worker_name,
                )
            job_result = ocr_core_client.wait_for_job(
                job_id,
                heartbeat=heartbeat,
                heartbeat_seconds=QUEUE_HEARTBEAT_SECONDS,
            )
            preflight = job_result.get("preflight")

            worker_logger.info(
                "Job de ocr-core resuelto queue_id=%s | job_id=%s | status=%s | preflight.decision=%s",
                queue_id, job_id, job_result["status"], (preflight or {}).get("decision"),
            )

            if job_result["status"] == "blocked":
                elapsed_ms = int((time.monotonic() - start_time) * 1000)
                normatividad_client.block(
                    queue_id,
                    message=(preflight or {}).get("message") or "Bloqueado por preflight",
                    reason_code=(preflight or {}).get("reason_code"),
                    duration_ms=elapsed_ms,
                    preflight=preflight,
                    processor=worker_name,
                    execution=job_result.get("execution") if TELEMETRY_FORWARD_ENABLED else None,
                    metrics=job_result.get("metrics") if TELEMETRY_FORWARD_ENABLED else None,
                    engine_response_json={"ocr_core_job": job_result},
                )
                worker_logger.info(
                    "queue_id=%s bloqueado por preflight | reason=%s",
                    queue_id, (preflight or {}).get("reason_code"),
                )
                return

            if job_result["status"] == "failed":
                error_msg = job_result.get("error") or "ocr-core job failed"
                if _looks_like_signature_error(error_msg):
                    elapsed_ms = int((time.monotonic() - start_time) * 1000)
                    fallback_preflight = {
                        **(preflight or {}),
                        "decision": "block",
                        "reason_code": "digital_signature_detected_during_ocr",
                        "message": "OCR bloqueado por firma digital detectada durante el procesamiento",
                    }
                    normatividad_client.block(
                        queue_id,
                        message=fallback_preflight["message"],
                        reason_code=fallback_preflight["reason_code"],
                        duration_ms=elapsed_ms,
                        preflight=fallback_preflight,
                        processor=worker_name,
                        execution=job_result.get("execution") if TELEMETRY_FORWARD_ENABLED else None,
                        metrics=job_result.get("metrics") if TELEMETRY_FORWARD_ENABLED else None,
                        engine_response_json={"ocr_core_job": job_result},
                    )
                    worker_logger.warning(
                        "queue_id=%s bloqueado por firma detectada durante OCR", queue_id,
                    )
                    return
                elapsed_ms = int((time.monotonic() - start_time) * 1000)
                normatividad_client.fail(
                    queue_id,
                    f"ocr-core job {job_id} failed: {error_msg}",
                    duration_ms=elapsed_ms,
                    processor=worker_name,
                    response_payload_json={"ocr_core_job_id": job_id},
                    engine_response_json={"ocr_core_job": job_result},
                    execution=job_result.get("execution") if TELEMETRY_FORWARD_ENABLED else None,
                    metrics=job_result.get("metrics") if TELEMETRY_FORWARD_ENABLED else None,
                )
                return

            # status == "done": preflight.decision fue "skip" (texto nativo
            # util) o "process" (se corrio OCR). En ambos casos ocr-core ya
            # escribio los artefactos solicitados en el destino indicado.
            decision = (preflight or {}).get("decision")
            artifacts_info = job_result.get("artifacts") or {}
            reused_pdf = bool(
                needs_pdf and (artifacts_info.get("pdf") or {}).get("reused_source")
            )
            if decision == "skip" and not needs_text and not needs_md and not reused_pdf:
                # Regla de negocio historica: si solo se pidio PDF y el
                # documento ya tenia texto util, no hay nada nuevo que
                # aportar - se reporta como skip, no como artefacto producido.
                elapsed_ms = int((time.monotonic() - start_time) * 1000)
                normatividad_client.skip(
                    queue_id,
                    message=(preflight or {}).get("message") or "PDF con texto util, no requiere OCR",
                    reason_code=(preflight or {}).get("reason_code") or "useful_text_present",
                    duration_ms=elapsed_ms,
                    preflight=preflight,
                    processor=worker_name,
                    execution=job_result.get("execution") if TELEMETRY_FORWARD_ENABLED else None,
                    metrics=job_result.get("metrics") if TELEMETRY_FORWARD_ENABLED else None,
                    engine_response_json={"ocr_core_job": job_result},
                )
                worker_logger.info(
                    "queue_id=%s omitido: ya tenia texto util y solo se pidio PDF", queue_id,
                )
                return

            if needs_pdf and (artifacts_info.get("pdf") or {}).get("written"):
                produced_artifacts["pdf"] = True
                pdf_cached = True
            if needs_text and (artifacts_info.get("text") or {}).get("written"):
                produced_artifacts["text"] = True
                text_cached = True
            if needs_md and (artifacts_info.get("md") or {}).get("written"):
                produced_artifacts["md"] = True
                md_cached = True
            if reused_pdf:
                reportable_artifacts["pdf"] = {
                    "available": True,
                    "origin": "source_reused",
                    "written": False,
                    "reused_source": True,
                }

        # Si Normatividad envio execution_request, un artefacto servido desde cache se informa como no escrito
        # para que Normatividad no lo registre como una version nueva (plan 1.4.1.5).
        reprocess_request = bool(_execution_request(payload))
        for name, cached in (("pdf", pdf_cached), ("text", text_cached), ("md", md_cached)):
            if not requested_artifacts.get(name) or not cached or name in reportable_artifacts:
                continue
            if reprocess_request and not produced_artifacts.get(name):
                reportable_artifacts[name] = {
                    "available": True,
                    "origin": "generated",
                    "written": False,
                }
            else:
                reportable_artifacts[name] = True

        elapsed_ms = int((time.monotonic() - start_time) * 1000)
        response_payload = {
            "requested_artifacts": requested_artifacts,
            "planned_artifacts": planned_artifacts,
            "unsupported_artifacts": unsupported_artifacts,
            "produced_artifacts": produced_artifacts,
            "reprocessed_artifacts": {
                "pdf": bool(force_pdf and produced_artifacts.get("pdf")),
                "text": bool(force_text and produced_artifacts.get("text")),
                "md": bool(force_md and produced_artifacts.get("md")),
            },
            "reported_artifacts": reportable_artifacts,
            "expected_artifacts": expected_artifacts,
            "storage": {
                "shared_cache_dir": str(SHARED_CACHE_DIR),
                "resolved_pdf_path": str(shared_pdf_path) if shared_pdf_path else None,
                "resolved_text_path": str(shared_text_path) if shared_text_path else None,
                "resolved_md_path": str(shared_md_path) if shared_md_path else None,
            },
            "preflight": preflight,
            "ocr_core_job_id": job_result.get("job_id") if job_result else None,
            "ocr_core_meta": core_meta,
        }
        engine_response = {
            "ocr_core_job": job_result,
            "source": payload.get("source") or {},
            "document": payload.get("document") or {},
            "artifacts": payload.get("artifacts") or {},
            "ocr_flags": _ocr_artifact_flags(payload),
            "preflight": preflight,
        }

        if expected_artifacts:
            if reportable_artifacts.get("pdf") and shared_pdf_path is None:
                raise RuntimeError(
                    "La cola reporta pdf pero artifacts.expected.pdf_path no fue provisto"
                )
            if reportable_artifacts.get("text") and shared_text_path is None:
                raise RuntimeError(
                    "La cola reporta text pero artifacts.expected.text_path no fue provisto"
                )
            if reportable_artifacts.get("md") and shared_md_path is None:
                raise RuntimeError(
                    "La cola reporta md pero artifacts.expected.md_path no fue provisto"
                )
            normatividad_client.report_artifacts(
                queue_id,
                processor=worker_name,
                duration_ms=elapsed_ms,
                finalize_queue=_should_finalize_queue(
                    planned_artifacts,
                    reportable_artifacts,
                    unsupported_artifacts,
                ),
                artifacts=reportable_artifacts,
                response_payload_json=response_payload,
                engine_response_json=engine_response,
                execution=job_result.get("execution") if job_result and TELEMETRY_FORWARD_ENABLED else None,
                metrics=job_result.get("metrics") if job_result and TELEMETRY_FORWARD_ENABLED else None,
            )
            worker_logger.info(
                "Item queue_id=%s reportado por /artifacts | artifacts=%s",
                queue_id, reportable_artifacts,
            )
        elif produced_artifacts.get("pdf") and shared_pdf_path is not None:
            normatividad_client.complete(queue_id, shared_pdf_path, duration_ms=elapsed_ms)
            worker_logger.info(
                "Item queue_id=%s completado por flujo legacy multipart", queue_id,
            )
        else:
            raise RuntimeError(
                "No hay artifacts.expected para reportar y no se produjo un PDF para fallback legacy"
            )
    except normatividad_client.QueueSourceUnavailableError as exc:
        elapsed_ms = int((time.monotonic() - start_time) * 1000)
        worker_logger.warning(
            "queue_id=%s sin archivo fuente disponible: %s", queue_id, exc.message,
        )
        normatividad_client.fail(
            queue_id,
            exc.message,
            duration_ms=elapsed_ms,
            processor=worker_name,
        )

    finally:
        _cleanup(inbox_pdf)
        try:
            inbox_pdf.parent.rmdir()
        except OSError:
            pass


def _document_name(payload: dict) -> str:
    """Nombre del documento sin extensión, apto como nombre de archivo."""
    queue = payload.get("queue") if isinstance(payload.get("queue"), dict) else {}
    regulation_file = (
        queue.get("regulation_file")
        if isinstance(queue.get("regulation_file"), dict)
        else {}
    )
    raw = str(regulation_file.get("file_name") or "").replace("\\", "/")
    name = Path(raw.rsplit("/", 1)[-1]).stem
    name = "".join(ch for ch in name if ch.isprintable()).strip(" .")[:120]
    return name or f"normatividad_{payload.get('queue_id') or payload.get('id')}"


def _safe_meta(item: dict) -> str:
    meta = {k: item[k] for k in ("queue_id", "id", "status", "regulation_file_id", "lease_expires_at") if k in item}
    artifacts = item.get("artifacts")
    if isinstance(artifacts, dict):
        requested = artifacts.get("requested")
        expected = artifacts.get("expected")
        if requested is not None:
            meta["requested_artifacts"] = requested
        if isinstance(expected, dict) and "dir" in expected:
            meta["artifacts_dir"] = expected["dir"]
    return str(meta)


def _requested_artifacts(payload: dict) -> dict[str, bool]:
    artifacts = payload.get("artifacts")
    requested = artifacts.get("requested") if isinstance(artifacts, dict) else None
    if not isinstance(requested, dict):
        return {"pdf": True, "text": False, "md": False}
    return {
        "pdf": bool(requested.get("pdf")),
        "text": bool(requested.get("text")),
        "md": bool(requested.get("md")),
    }


def _execution_request(payload: dict) -> dict:
    value = payload.get("execution_request")
    return value if isinstance(value, dict) else {}


def _reprocess_artifacts(payload: dict) -> dict[str, bool]:
    value = _execution_request(payload).get("reprocess_artifacts")
    if not isinstance(value, dict):
        return {"pdf": False, "text": False, "md": False}
    return {name: bool(value.get(name)) for name in ("pdf", "text", "md")}


def _idempotency_key(payload: dict, options: dict[str, Any]) -> str:
    source = payload.get("source") if isinstance(payload.get("source"), dict) else {}
    queue = payload.get("queue") if isinstance(payload.get("queue"), dict) else {}
    attempt = _execution_request(payload).get("attempt", queue.get("attempts", 0))
    fingerprint_payload = {
        "requested": _requested_artifacts(payload),
        "reprocess": _reprocess_artifacts(payload),
        "options": options,
    }
    fingerprint = hashlib.sha256(
        json.dumps(
            fingerprint_payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
    ).hexdigest()[:32]
    return f"{payload.get('queue_id') or payload.get('id')}:{attempt}:{source.get('md5') or 'unknown'}:{fingerprint}"


class CoreCapabilityError(RuntimeError):
    """El core activo no publica una capacidad que exigen los flags encendidos.

    Es un error de configuracion del despliegue, no del documento: nunca se reporta
    como fallo del item.
    """


def _required_capabilities(payload: dict) -> set[str]:
    required = set()
    if SOURCE_REUSE_ENABLED:
        required.add("pdf_on_skip_reuse")
    if TELEMETRY_FORWARD_ENABLED:
        required.add("telemetry_schema")
        required.add("execution_provenance")
    if _requested_artifacts(payload)["md"]:
        required.add("artifact_schemas.md")
    return required


def _capability_present(capabilities: dict, name: str) -> bool:
    if name == "artifact_schemas.md":
        schemas = capabilities.get("artifact_schemas")
        return isinstance(schemas, dict) and schemas.get("md") == MARKDOWN_SCHEMA
    return bool(capabilities.get(name))


def _validate_core_capabilities(required: set[str]) -> dict:
    if not required and not CORE_CAPABILITIES_REQUIRED:
        return {}
    meta = ocr_core_client.get_meta()
    capabilities = meta.get("capabilities") if isinstance(meta, dict) else {}
    capabilities = capabilities if isinstance(capabilities, dict) else {}
    missing = sorted(name for name in required if not _capability_present(capabilities, name))
    if missing:
        raise CoreCapabilityError(f"ocr-core no publica capacidades requeridas: {missing}")
    logger.info(
        "Capacidades ocr-core verificadas | release=%s version=%s capabilities=%s",
        meta.get("release_id"),
        meta.get("version"),
        sorted(name for name, enabled in capabilities.items() if enabled),
    )
    return meta


def _expected_artifacts(payload: dict) -> dict:
    artifacts = payload.get("artifacts")
    expected = artifacts.get("expected") if isinstance(artifacts, dict) else None
    return expected if isinstance(expected, dict) else {}


def _ocr_artifact_flags(payload: dict) -> dict[str, bool | None]:
    candidates = []
    for key in ("ocr", "ocr_record", "file_ocr"):
        value = payload.get(key)
        if isinstance(value, dict):
            candidates.append(value)
    queue_payload = payload.get("queue")
    if isinstance(queue_payload, dict):
        for key in ("ocr", "ocr_record", "file_ocr"):
            value = queue_payload.get(key)
            if isinstance(value, dict):
                candidates.append(value)
    candidates.append(payload)
    for candidate in candidates:
        flags = {}
        found = False
        for name in ("pdf", "text", "md"):
            key = f"has_{name}"
            if key in candidate:
                flags[name] = bool(candidate.get(key))
                found = True
            else:
                flags[name] = None
        if found:
            return flags
    return {"pdf": None, "text": None, "md": None}


def _artifact_cached(payload: dict, artifact: str, resolved_path: Path | None) -> bool:
    flags = _ocr_artifact_flags(payload)
    has_flag = flags.get(artifact)
    if resolved_path is None:
        return bool(has_flag)
    if has_flag is False:
        return False
    if has_flag is True:
        return resolved_path.exists()
    return False


def _resolve_expected_artifact_path(payload: dict, artifact: str) -> Path | None:
    expected = _expected_artifacts(payload)
    raw = expected.get(f"{artifact}_path")
    if not raw:
        return None
    relative = Path(str(raw))
    if relative.is_absolute():
        raise RuntimeError(
            f"expected {artifact}_path debe ser relativo al cache compartido: {raw}"
        )
    candidate = (SHARED_CACHE_DIR / relative).resolve()
    shared_root = SHARED_CACHE_DIR.resolve()
    try:
        candidate.relative_to(shared_root)
    except ValueError as exc:
        raise RuntimeError(
            f"expected {artifact}_path fuera del cache compartido: {raw}"
        ) from exc
    return candidate


def _text_artifact_metadata(
    payload: dict,
    pdf_path: Path | None,
    text_path: Path | None,
    md_path: Path | None = None,
) -> dict[str, Any]:
    """
    Arma el objeto `metadata` que viaja como passthrough opaco dentro de
    options.metadata en POST /jobs (ver ocr-core/docs/documentacion-tecnica/datos/diccionario/TextDocument.md).
    ocr-core
    no le da ningun significado a este dict; solo lo copia dentro del
    artefacto text.
    """
    queue = payload.get("queue") if isinstance(payload.get("queue"), dict) else {}
    regulation_file = (
        queue.get("regulation_file")
        if isinstance(queue.get("regulation_file"), dict)
        else {}
    )
    regulation = (
        regulation_file.get("regulation")
        if isinstance(regulation_file.get("regulation"), dict)
        else {}
    )
    document = payload.get("document") if isinstance(payload.get("document"), dict) else {}
    source = payload.get("source") if isinstance(payload.get("source"), dict) else {}

    regulation_file_id = (
        payload.get("regulation_file_id")
        or queue.get("regulation_file_id")
        or regulation_file.get("id")
    )
    regulation_id = (
        document.get("regulation_id")
        or regulation_file.get("file_idregulation")
        or regulation.get("id")
    )
    source_md5 = (
        payload.get("source_md5")
        or queue.get("source_md5")
        or source.get("md5")
        or regulation_file.get("file_md5")
    )

    metadata = {
        "regulation_file_id": regulation_file_id,
        "regulation_id": regulation_id,
        "source_md5": source_md5,
        "pdf_path": _shared_cache_relative_path(pdf_path),
        "text_path": _shared_cache_relative_path(text_path),
        "source_path": source.get("path") or queue.get("source_path"),
        "file_name": regulation_file.get("file_name"),
        "file_size": regulation_file.get("file_size") or source.get("size"),
        "reg_num": document.get("reg_num") or regulation.get("reg_num"),
        "reg_year": document.get("reg_year") or regulation.get("reg_year"),
        "reg_date": regulation.get("reg_date"),
        "reg_title": regulation.get("reg_title"),
        "reg_description": regulation.get("reg_description"),
        "regulations_tipo": document.get("regulations_tipo") or regulation.get("regulations_tipo"),
        "regulations_tipos_sigla_id": regulation.get("regulations_tipos_sigla_id"),
        "regulation_type_id": document.get("regulations_tipo") or regulation.get("regulations_tipo"),
        "regulation_type_sigla_id": regulation.get("regulations_tipos_sigla_id"),
    }
    # Solo los jobs que piden Markdown llevan su ruta: el JSONL y la clave de
    # idempotencia de los jobs pdf/text no cambian.
    if md_path is not None:
        metadata["md_path"] = _shared_cache_relative_path(md_path)
    return metadata


def _shared_cache_relative_path(path: Path | None) -> str | None:
    if path is None:
        return None
    try:
        return str(path.resolve().relative_to(SHARED_CACHE_DIR.resolve()))
    except ValueError:
        return str(path)


def _should_finalize_queue(
    planned_artifacts: dict[str, bool],
    reportable_artifacts: dict[str, bool],
    unsupported_artifacts: dict[str, bool],
) -> bool:
    if unsupported_artifacts:
        return False
    for artifact, planned in planned_artifacts.items():
        if planned and not reportable_artifacts.get(artifact, False):
            return False
    return True


def _looks_like_signature_error(text: str) -> bool:
    lowered = text.lower()
    return "digitalsignatureerror" in lowered or "digital signature" in lowered


def _cleanup(*paths: Path) -> None:
    for p in paths:
        try:
            if p and p.exists():
                p.unlink()
                logger.debug("Limpiado: %s", p)
        except Exception as exc:
            logger.warning("No se pudo limpiar %s: %s", p, exc)


# ---------------------------------------------------------------------------
# Loop principal
# ---------------------------------------------------------------------------


def _run_worker_loop(worker_name: str) -> None:
    worker_logger = _worker_logger(worker_name)

    if not WORKER_ENABLED:
        worker_logger.info("OCR_WORKER_ENABLED=false -> worker deshabilitado, saliendo.")
        return

    if not normatividad_client.NORMATIVIDAD_BASE_URL:
        worker_logger.critical(
            "NORMATIVIDAD_BASE_URL no esta configurado. El worker no puede iniciar."
        )
        sys.exit(1)

    if not normatividad_client.NORMATIVIDAD_OCR_TOKEN:
        worker_logger.warning(
            "NORMATIVIDAD_OCR_TOKEN esta vacio. Las peticiones a Normatividad probablemente fallaran."
        )

    if not ocr_core_client.OCR_CORE_URL:
        worker_logger.critical(
            "OCR_CORE_URL no esta configurado. El worker no puede iniciar."
        )
        sys.exit(1)

    worker_logger.info(
        "Worker '%s' iniciado | NORMATIVIDAD_BASE_URL=%s | OCR_CORE_URL=%s | poll_interval=%.1fs",
        worker_name,
        normatividad_client.NORMATIVIDAD_BASE_URL,
        ocr_core_client.OCR_CORE_URL,
        POLL_INTERVAL,
    )

    INBOX_DIR.mkdir(parents=True, exist_ok=True)

    consecutive_errors = 0

    while not _stop_requested:
        try:
            # Se valida antes de tomar un item: con un core sin capacidades el worker
            # no consume la cola (cuenta como error consecutivo y termina deteniendose).
            _validate_core_capabilities(_required_capabilities({}))
            item = normatividad_client.pull_next(worker_name=worker_name)

            if item is None:
                worker_logger.debug("Cola vacia, esperando %.1fs...", POLL_INTERVAL)
                _interruptible_sleep(POLL_INTERVAL)
                consecutive_errors = 0
                continue

            consecutive_errors = 0
            payload = item.get("data", item)
            queue_id = payload.get("queue_id") or payload.get("id")

            item_start = time.monotonic()
            try:
                _process_item(item, worker_name, worker_logger)
            except CoreCapabilityError as exc:
                # El item queda leased y vuelve a pending cuando vence su lease.
                worker_logger.critical("queue_id=%s no procesado: %s", queue_id, exc)
                _interruptible_sleep(POLL_INTERVAL)
            except Exception as exc:
                worker_logger.exception("Error procesando queue_id=%s: %s", queue_id, exc)
                elapsed_ms = int((time.monotonic() - item_start) * 1000)
                try:
                    normatividad_client.fail(
                        queue_id,
                        str(exc),
                        duration_ms=elapsed_ms,
                        processor=worker_name,
                    )
                except Exception as fail_exc:
                    worker_logger.error(
                        "No se pudo reportar fallo a Normatividad (queue_id=%s): %s",
                        queue_id, fail_exc,
                    )
                _interruptible_sleep(POLL_INTERVAL)

        except Exception as poll_exc:
            consecutive_errors += 1
            worker_logger.error(
                "Error en pull_next (error %d/%d): %s",
                consecutive_errors, MAX_CONSECUTIVE_ERRORS, poll_exc,
            )
            if consecutive_errors >= MAX_CONSECUTIVE_ERRORS:
                worker_logger.critical(
                    "Se alcanzo el limite de %d errores consecutivos. Deteniendo worker.",
                    MAX_CONSECUTIVE_ERRORS,
                )
                sys.exit(1)

            wait = min(POLL_INTERVAL * (2 ** min(consecutive_errors - 1, 4)), POLL_INTERVAL * 5)
            worker_logger.info("Esperando %.1fs antes de reintentar...", wait)
            _interruptible_sleep(wait)

    worker_logger.info("Worker '%s' detenido limpiamente.", worker_name)


def process_single_item(
    item: dict[str, Any],
    worker_name: str | None = None,
    *,
    raise_errors: bool = True,
) -> None:
    """
    Procesa un item ya obtenido previamente, sin hacer polling continuo.
    Util para depuracion uno por uno.
    """
    effective_worker_name = (worker_name or WORKER_NAME).strip() or WORKER_NAME
    worker_logger = _worker_logger(effective_worker_name)
    INBOX_DIR.mkdir(parents=True, exist_ok=True)

    payload = item.get("data", item)
    queue_id = payload.get("queue_id") or payload.get("id")
    item_start = time.monotonic()

    try:
        _process_item(item, effective_worker_name, worker_logger)
    except CoreCapabilityError as exc:
        worker_logger.critical("queue_id=%s no procesado: %s", queue_id, exc)
        if raise_errors:
            raise
    except Exception as exc:
        worker_logger.exception("Error procesando queue_id=%s: %s", queue_id, exc)
        elapsed_ms = int((time.monotonic() - item_start) * 1000)
        try:
            normatividad_client.fail(
                queue_id,
                str(exc),
                duration_ms=elapsed_ms,
                processor=effective_worker_name,
            )
        except Exception as fail_exc:
            worker_logger.error(
                "No se pudo reportar fallo a Normatividad (queue_id=%s): %s",
                queue_id, fail_exc,
            )
        if raise_errors:
            raise


def run_worker_once(worker_name: str | None = None) -> bool:
    """
    Hace un solo pull-next y procesa como maximo un item, luego sale.

    Returns:
        True si encontro y proceso un item, False si la cola estaba vacia.
    """
    effective_worker_name = (worker_name or WORKER_NAME).strip() or WORKER_NAME
    worker_logger = _worker_logger(effective_worker_name)

    if not WORKER_ENABLED:
        worker_logger.info("OCR_WORKER_ENABLED=false -> worker deshabilitado, saliendo.")
        return False

    if not normatividad_client.NORMATIVIDAD_BASE_URL:
        worker_logger.critical(
            "NORMATIVIDAD_BASE_URL no esta configurado. El worker no puede iniciar."
        )
        sys.exit(1)

    if not ocr_core_client.OCR_CORE_URL:
        worker_logger.critical(
            "OCR_CORE_URL no esta configurado. El worker no puede iniciar."
        )
        sys.exit(1)

    worker_logger.info(
        "Worker once '%s' iniciado | NORMATIVIDAD_BASE_URL=%s | OCR_CORE_URL=%s",
        effective_worker_name,
        normatividad_client.NORMATIVIDAD_BASE_URL,
        ocr_core_client.OCR_CORE_URL,
    )

    INBOX_DIR.mkdir(parents=True, exist_ok=True)

    _validate_core_capabilities(_required_capabilities({}))
    item = normatividad_client.pull_next(worker_name=effective_worker_name)
    if item is None:
        worker_logger.info("Cola vacia: no se encontro item para procesar.")
        return False

    process_single_item(item, effective_worker_name)
    worker_logger.info("Worker once '%s' termino tras procesar un item.", effective_worker_name)
    return True


def _run_worker_process(index: int) -> None:
    global _stop_requested
    _stop_requested = False
    signal.signal(signal.SIGTERM, _handle_signal)
    signal.signal(signal.SIGINT, _handle_signal)
    _run_worker_loop(_worker_name_for_index(index))


def _terminate_children(children: list[mp.Process]) -> None:
    for proc in children:
        if proc.is_alive():
            proc.terminate()


def run_worker() -> None:
    if WORKER_CONCURRENCY <= 1:
        _run_worker_loop(WORKER_NAME)
        return

    logger.info(
        "Supervisor iniciando %d consumidores para la misma cola OCR",
        WORKER_CONCURRENCY,
    )
    children: list[mp.Process] = []
    for index in range(WORKER_CONCURRENCY):
        proc = mp.Process(
            target=_run_worker_process,
            args=(index,),
            name=_worker_name_for_index(index),
        )
        proc.start()
        children.append(proc)
        logger.info("Consumidor %s iniciado con pid=%s", proc.name, proc.pid)

    exit_code = 0
    try:
        while children:
            for proc in list(children):
                proc.join(timeout=0.5)
                if proc.is_alive():
                    continue
                children.remove(proc)
                if _stop_requested:
                    continue
                logger.error(
                    "Consumidor %s termino inesperadamente con exitcode=%s",
                    proc.name, proc.exitcode,
                )
                exit_code = proc.exitcode or 1
                _terminate_children(children)
                children = []
                break
            if _stop_requested:
                _terminate_children(children)
                break
    finally:
        for proc in children:
            proc.join(timeout=5)

    if _stop_requested:
        logger.info("Supervisor detenido limpiamente.")
        return
    if exit_code:
        sys.exit(exit_code)


def _interruptible_sleep(seconds: float) -> None:
    deadline = time.monotonic() + seconds
    while not _stop_requested and time.monotonic() < deadline:
        time.sleep(min(1.0, deadline - time.monotonic()))
