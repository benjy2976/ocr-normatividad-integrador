# Contrato compartido Normatividad OCR: reproceso y trazabilidad

`schema.json` describe los campos aditivos que habilitan el reproceso real y la
trazabilidad de ejecuciones; `fixtures.json` congela ejemplos compatibles. Los tres
archivos deben existir, con la misma huella SHA-256, en `munis`, `ocr-lab` y
`ocr-normatividad-integrador`.

La funcionalidad se reconoce por la presencia del bloque `execution_request` en el
item de cola; no hay numero de version de contrato. Sin ese bloque se conserva el
comportamiento basico (`queue_basic`, `callback_boolean`).

Reglas semanticas:

- `requested_artifacts` expresa lo que el consumidor necesita;
- `reprocess_artifacts` expresa que artefactos deben ejecutarse aunque ya esten activos;
- `produced_artifacts` expresa archivos escritos por el job actual;
- un descriptor `source_reused` satisface PDF sin escribir una copia en cache;
- con `execution_request`, un artefacto servido desde cache (no forzado, ya vigente) se
  informa como `{"origin": "generated", "written": false}`: satisface la solicitud y
  Normatividad conserva la version activa en lugar de registrar otra; sin el bloque se
  mantiene el booleano `true`;
- `active` es estado persistente de Normatividad, no sinonimo de `produced`;
- la huella idempotente usa cola, intento, MD5 de fuente y hash canonico de
  solicitud/reproceso/opciones;
- telemetria analitica no contiene el texto reconocido completo y su respuesta
  queda limitada a 524288 bytes por defecto.

Los defaults compatibles son `pdf_on_skip=copy` y `telemetry.level=none`. Los
identificadores `ocr.execution.v1` y `ocr.telemetry.document.v1` no versionan esta
funcionalidad: identifican el formato de los datos guardados por ejecucion.
