# 0001. El Markdown se atiende cuando la cola lo pide, sin interruptor

- **Estado:** vigente
- **Fecha:** 2026-10-29
- **Decidió:** Walther Aguirre

## Contexto

Al incorporar el artefacto `md` de `ocr-core` (0.5.0, beta) se propuso una
variable de entorno para habilitarlo en el integrador.

## Decisión

- El integrador atiende `md` siempre que la cola lo pida. Lo decide quien
  encola (Normatividad), no una configuración del integrador.
- Antes de marcar un ítem que pide `md`, el worker exige que el core anuncie
  `ocr.markdown.document.v1` en `GET /meta`. Si no lo anuncia, se detiene sin
  tocar la cola.

## Alternativas descartadas

- **Un interruptor en el integrador:** duplicaría una decisión que ya toma
  Normatividad y permitiría ignorar en silencio lo que la cola pide.

## Consecuencias

- Si el core vuelve a una versión sin Markdown (por ejemplo, un rollback a
  0.4.0), los ítems que piden `md` quedan pendientes en lugar de cerrarse sin
  el artefacto.
- Regla vigente: RN-011 de `../reglas-negocio.md`.

## Evidencia

- Commit `d58951b`.
- `adapter/tests/test_worker_markdown.py`
  (`test_core_without_markdown_schema_stops_before_touching_the_queue`).
