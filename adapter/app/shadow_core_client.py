"""Cliente aislado para duplicar jobs hacia el core candidato.

Usa el mismo contrato ``POST /jobs`` que el core oficial, pero remapea los
artefactos a un volumen privado. No consulta ni modifica Normatividad.
"""

from __future__ import annotations

import hashlib
import os
import re
from pathlib import Path, PurePosixPath
from typing import Any

import requests


OCR_SHADOW_ENABLED: bool = os.getenv("OCR_SHADOW_ENABLED", "false").lower() in {
    "1",
    "true",
    "yes",
}
OCR_SHADOW_CORE_URL: str = os.getenv("OCR_SHADOW_CORE_URL", "").rstrip("/")
OCR_SHADOW_OUTPUT_ROOT: str = os.getenv(
    "OCR_SHADOW_OUTPUT_ROOT", "/shadow-cache/review"
).rstrip("/")
OCR_SHADOW_SUBMIT_TIMEOUT_SECONDS: float = float(
    os.getenv("OCR_SHADOW_SUBMIT_TIMEOUT_SECONDS", "30")
)


def enabled() -> bool:
    return OCR_SHADOW_ENABLED


def _review_root() -> PurePosixPath:
    root = PurePosixPath(OCR_SHADOW_OUTPUT_ROOT)
    if not root.is_absolute() or not root.is_relative_to(PurePosixPath("/shadow-cache")):
        raise ValueError(
            "OCR_SHADOW_OUTPUT_ROOT debe ser una ruta absoluta dentro de /shadow-cache"
        )
    return root


def _queue_component(queue_id: Any) -> str:
    raw = str(queue_id)
    normalized = re.sub(r"[^A-Za-z0-9._-]+", "-", raw).strip("-._")[:48]
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:10]
    return f"queue-{normalized or 'item'}-{digest}"


def _idempotency_key(queue_id: Any) -> str:
    digest = hashlib.sha256(str(queue_id).encode("utf-8")).hexdigest()
    return f"normatividad-shadow-{digest}"


def build_request(
    source_path: Path,
    *,
    queue_id: Any,
    artifacts: set[str],
) -> dict[str, Any]:
    unsupported = artifacts - {"pdf", "text"}
    if unsupported:
        raise ValueError(f"artefactos shadow no soportados: {sorted(unsupported)}")
    if not artifacts:
        raise ValueError("el job shadow requiere al menos un artefacto")

    review_dir = _review_root() / _queue_component(queue_id)
    suffixes = {"pdf": "document.pdf", "text": "text.jsonl"}
    artifact_specs = {
        name: {
            "path": str(review_dir / suffixes[name]),
            "overwrite": True,
        }
        for name in sorted(artifacts)
    }
    return {
        "source": {"path": str(source_path)},
        "options": {
            "metadata": {
                "integration_mode": "production-shadow",
                "normatividad_queue_id": str(queue_id),
                "review_dir": str(review_dir),
            }
        },
        "artifacts": artifact_specs,
        "idempotency_key": _idempotency_key(queue_id),
    }


def submit_job(
    source_path: Path,
    *,
    queue_id: Any,
    artifacts: set[str],
) -> dict[str, Any]:
    if not OCR_SHADOW_CORE_URL:
        raise RuntimeError("OCR_SHADOW_CORE_URL no esta configurado")
    body = build_request(source_path, queue_id=queue_id, artifacts=artifacts)
    response = requests.post(
        f"{OCR_SHADOW_CORE_URL}/jobs",
        json=body,
        timeout=OCR_SHADOW_SUBMIT_TIMEOUT_SECONDS,
    )
    response.raise_for_status()
    result = response.json()
    if not result.get("job_id"):
        raise RuntimeError("core shadow acepto la solicitud sin devolver job_id")
    return result


__all__ = ["build_request", "enabled", "submit_job"]
