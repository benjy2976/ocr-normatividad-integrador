# Verificación del componente

> La mayor parte del comportamiento histórico sigue validada por operación
> sostenida. El aislamiento del fan-out shadow cuenta con pruebas unitarias.

## Verificación realizada

- Operación sostenida contra producción real (Normatividad) documentada en `../../context.md`, sección "Operación sostenida real contra producción (2026-09-07)".
- Corrida de verificación completa entre `ocr-core` y `normatividad-services`: ver `../../../TEST_OFICIAL_2_REPOS.md` (carpeta padre `new_ocr/`, compartido entre ambos repos).
- Incidente real documentado y resuelto: colisión por reinicio de `ocr-core` con el worker activo (`queue_id=198379` → reencolado manualmente como `198380`, completado `done`).
- `adapter/tests/test_shadow_core_client.py`: contrato `POST /jobs`, destinos
  fuera del NFS, shadow deshabilitado por defecto y contención de errores.

## Pendiente

- Formalizar casos de prueba mínimos para RN-001 a RN-006; RN-007 ya tiene
  cobertura unitaria inicial (ver [reglas-negocio.md](../documentacion-tecnica/reglas-negocio.md)).
