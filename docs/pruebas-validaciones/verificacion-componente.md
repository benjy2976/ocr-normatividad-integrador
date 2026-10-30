# Verificación del componente

> El comportamiento se valida por operación sostenida contra producción y por
> pruebas unitarias en `adapter/tests/`: `test_worker_reproceso.py`
> (RN-004 y RN-008 a RN-010), `test_worker_markdown.py` (RN-011),
> `test_shadow_core_client.py` (RN-007), `test_logging.py` y
> `test_documentation_independence.py` (la documentación no depende de planes).

## Verificación realizada

- Operación sostenida contra producción real (Normatividad) documentada en `../../context.md`, sección "Operación sostenida real contra producción (2026-09-07)".
- Verificación de punta a punta contra producción real (2026-09-04): un ítem (`queue_id=198322`, `regulation_file_id=122850`) recorrió `pull-next`, `processing`, la descarga de la fuente, el OCR en el core y el callback hasta `status=done`, con el PDF y el JSONL escritos en el NFS compartido. El procedimiento vigente está en `../manuales/instalacion-configuracion.md`, "Operación contra producción real".
- Incidente real documentado y resuelto: colisión por reinicio de `ocr-core` con el worker activo (`queue_id=198379` → reencolado manualmente como `198380`, completado `done`).
- `adapter/tests/test_shadow_core_client.py`: contrato `POST /jobs`, destinos
  fuera del NFS, shadow deshabilitado por defecto y contención de errores.

## Pendiente

- Formalizar casos de prueba mínimos para RN-001 a RN-006; RN-007 ya tiene
  cobertura unitaria inicial (ver [reglas-negocio.md](../documentacion-tecnica/reglas-negocio.md)).
