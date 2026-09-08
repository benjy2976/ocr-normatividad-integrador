# Verificación del componente

> Sin tests automatizados. La validación real se hizo en operación sostenida contra producción, no como suite de pruebas formal.

## Verificación realizada

- Operación sostenida contra producción real (Normatividad) documentada en `../../context.md`, sección "Operación sostenida real contra producción (2026-09-07)".
- Corrida de verificación completa entre `ocr-core` y `normatividad-services`: ver `../../../TEST_OFICIAL_2_REPOS.md` (carpeta padre `new_ocr/`, compartido entre ambos repos).
- Incidente real documentado y resuelto: colisión por reinicio de `ocr-core` con el worker activo (`queue_id=198379` → reencolado manualmente como `198380`, completado `done`).

## Pendiente

- Formalizar casos de prueba mínimos, especialmente para las reglas de negocio RN-001 a RN-006 (ver [reglas-negocio.md](../documentacion-tecnica/reglas-negocio.md)).
