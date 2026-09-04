"""
Cliente HTTP hacia ocr-core (POST /jobs, GET /jobs/{id}).

Reemplaza el import in-process de app.ocr_pipeline que tenia el worker
historico. El adaptador no conoce nada del motor OCR mas alla de este
contrato HTTP — ver ocr-core/api.md, seccion "POST /jobs".
"""

import os
import time
from pathlib import Path
from typing import Any

import requests

OCR_CORE_URL: str = os.getenv("OCR_CORE_URL", "").rstrip("/")
OCR_CORE_HTTP_TIMEOUT_SECONDS: float = float(os.getenv("OCR_CORE_HTTP_TIMEOUT_SECONDS", "30"))
OCR_CORE_JOB_POLL_INTERVAL_SECONDS: float = float(os.getenv("OCR_CORE_JOB_POLL_INTERVAL_SECONDS", "2"))
OCR_CORE_JOB_TIMEOUT_SECONDS: float = float(os.getenv("OCR_CORE_JOB_TIMEOUT_SECONDS", "1800"))


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
) -> str:
    """POST /jobs. Devuelve job_id. No bloquea esperando el resultado."""
    body = {
        "source": {"path": str(source_path)},
        "options": options or {},
        "artifacts": artifacts,
    }
    resp = requests.post(_url("/jobs"), json=body, timeout=OCR_CORE_HTTP_TIMEOUT_SECONDS)
    resp.raise_for_status()
    return resp.json()["job_id"]


def get_job(job_id: str) -> dict:
    """GET /jobs/{id}. Una sola consulta, sin esperar."""
    resp = requests.get(_url(f"/jobs/{job_id}"), timeout=OCR_CORE_HTTP_TIMEOUT_SECONDS)
    resp.raise_for_status()
    return resp.json()


def wait_for_job(job_id: str) -> dict:
    """
    Hace polling de GET /jobs/{id} hasta que status salga de
    queued/processing. Lanza OcrCoreJobTimeoutError si se excede
    OCR_CORE_JOB_TIMEOUT_SECONDS (default 30 min, PDFs muy grandes pueden
    necesitar subirlo).
    """
    deadline = time.monotonic() + OCR_CORE_JOB_TIMEOUT_SECONDS
    while True:
        data = get_job(job_id)
        if data["status"] not in ("queued", "processing"):
            return data
        if time.monotonic() > deadline:
            raise OcrCoreJobTimeoutError(job_id, OCR_CORE_JOB_TIMEOUT_SECONDS)
        time.sleep(OCR_CORE_JOB_POLL_INTERVAL_SECONDS)
