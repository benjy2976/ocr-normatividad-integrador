"""
Cliente HTTP hacia ocr-core (POST /jobs, GET /jobs/{id}).

Reemplaza el import in-process de app.ocr_pipeline que tenia el worker
historico. El adaptador no conoce nada del motor OCR mas alla de este
contrato HTTP — ver ocr-core/api.md, seccion "POST /jobs".
"""

import os
import time
import threading
from pathlib import Path
from collections.abc import Callable
from typing import Any

import requests

OCR_CORE_URL: str = os.getenv("OCR_CORE_URL", "").rstrip("/")
OCR_CORE_HTTP_TIMEOUT_SECONDS: float = float(os.getenv("OCR_CORE_HTTP_TIMEOUT_SECONDS", "30"))
OCR_CORE_JOB_POLL_INTERVAL_SECONDS: float = float(os.getenv("OCR_CORE_JOB_POLL_INTERVAL_SECONDS", "2"))
OCR_CORE_JOB_TIMEOUT_SECONDS: float = float(os.getenv("OCR_CORE_JOB_TIMEOUT_SECONDS", "1800"))
OCR_CORE_META_TTL_SECONDS: float = float(os.getenv("OCR_CORE_META_TTL_SECONDS", "60"))
OCR_CORE_SUBMIT_MAX_RETRIES: int = max(0, int(os.getenv("OCR_CORE_SUBMIT_MAX_RETRIES", "2")))
_meta_lock = threading.Lock()
_meta_cache: tuple[float, dict[str, Any]] | None = None


class OcrCoreJobTimeoutError(RuntimeError):
    def __init__(self, job_id: str, timeout_seconds: float):
        self.job_id = job_id
        super().__init__(f"job {job_id} no termino dentro de {timeout_seconds:.0f}s")


def _url(path: str) -> str:
    if not OCR_CORE_URL:
        raise RuntimeError(
            "OCR_CORE_URL no esta configurado. Define la URL interna de "
            "ocr-core (ej. http://ocr-core:8000) antes de iniciar el worker."
        )
    return f"{OCR_CORE_URL}{path}"


def submit_job(
    source_path: Path,
    *,
    options: dict[str, Any] | None = None,
    artifacts: dict[str, dict[str, Any]],
    idempotency_key: str | None = None,
) -> str:
    """POST /jobs. Devuelve job_id. No bloquea esperando el resultado."""
    body = {
        "source": {"path": str(source_path)},
        "options": options or {},
        "artifacts": artifacts,
    }
    if idempotency_key:
        body["idempotency_key"] = idempotency_key
    attempts = 1 + (OCR_CORE_SUBMIT_MAX_RETRIES if idempotency_key else 0)
    for attempt in range(1, attempts + 1):
        try:
            resp = requests.post(
                _url("/jobs"),
                json=body,
                timeout=OCR_CORE_HTTP_TIMEOUT_SECONDS,
            )
            resp.raise_for_status()
            return resp.json()["job_id"]
        except requests.RequestException as exc:
            status = getattr(getattr(exc, "response", None), "status_code", None)
            # Un 4xx es un rechazo definitivo del contrato: reintentarlo no cambia nada.
            if attempt >= attempts or (status is not None and status < 500):
                raise
            time.sleep(min(2 ** (attempt - 1), 5))
    raise RuntimeError("unreachable")


def get_meta(*, force: bool = False) -> dict[str, Any]:
    global _meta_cache
    now = time.monotonic()
    with _meta_lock:
        if not force and _meta_cache and now - _meta_cache[0] < OCR_CORE_META_TTL_SECONDS:
            return dict(_meta_cache[1])
    resp = requests.get(_url("/meta"), timeout=OCR_CORE_HTTP_TIMEOUT_SECONDS)
    resp.raise_for_status()
    payload = resp.json()
    with _meta_lock:
        _meta_cache = (now, dict(payload))
    return payload


def get_job(job_id: str) -> dict:
    """GET /jobs/{id}. Una sola consulta, sin esperar."""
    resp = requests.get(_url(f"/jobs/{job_id}"), timeout=OCR_CORE_HTTP_TIMEOUT_SECONDS)
    resp.raise_for_status()
    return resp.json()


def wait_for_job(
    job_id: str,
    *,
    heartbeat: Callable[[], None] | None = None,
    heartbeat_seconds: float = 60,
) -> dict:
    """
    Hace polling de GET /jobs/{id} hasta que status salga de
    queued/processing. Lanza OcrCoreJobTimeoutError si se excede
    OCR_CORE_JOB_TIMEOUT_SECONDS (default 30 min, PDFs muy grandes pueden
    necesitar subirlo).
    """
    deadline = time.monotonic() + OCR_CORE_JOB_TIMEOUT_SECONDS
    next_heartbeat = time.monotonic() + heartbeat_seconds
    while True:
        data = get_job(job_id)
        if data["status"] not in ("queued", "processing"):
            return data
        if heartbeat is not None and time.monotonic() >= next_heartbeat:
            heartbeat()
            next_heartbeat = time.monotonic() + heartbeat_seconds
        if time.monotonic() > deadline:
            raise OcrCoreJobTimeoutError(job_id, OCR_CORE_JOB_TIMEOUT_SECONDS)
        time.sleep(OCR_CORE_JOB_POLL_INTERVAL_SECONDS)
