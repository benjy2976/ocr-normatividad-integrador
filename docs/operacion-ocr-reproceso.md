# Operación del integrador OCR: reproceso y trazabilidad

Estado: preparado localmente; todos los flags nuevos están apagados por
defecto. Este documento no autoriza encender el loop contra la cola real.

## Compatibilidad

- Core antiguo + flags apagados: se conserva el comportamiento básico actual.
- Core nuevo + flags apagados: defaults `copy`, sin telemetría.
- `OCR_SOURCE_REUSE_ENABLED=true`: exige `pdf_on_skip_reuse` en `/meta`.
- `md` (Markdown estructurado, beta) no tiene interruptor: se atiende cuando la
  cola lo pide. Exige que `/meta` anuncie
  `artifact_schemas.md=ocr.markdown.document.v1` (ocr-core 0.5.0+); con un core
  anterior el worker se detiene antes de marcar el item como `processing`. El
  Markdown se escribe en `artifacts.expected.md_path`, entra en la clave
  idempotente y se reporta como `md` en `/artifacts`.

## Requisitos para que Normatividad solicite `md`

Antes de encolar con `artifacts.requested.md=true`, Normatividad debe:

1. enviar `artifacts.expected.md_path` con el mismo patrón que los otros
   artefactos (`{año}/{id}/{md5}.md`); si falta, el item falla con un mensaje
   explícito;
2. aceptar `md` en el callback `/artifacts`, igual que `pdf` y `text` (booleano
   o descriptor `available/origin/written`), y registrar su ruta;
3. informar `has_md` en el payload para que un Markdown existente no se vuelva
   a solicitar.

El título visible dentro del Markdown es `document.markdown_title`, que el
integrador reenvía al core como `options.document_title` (ocr-core `0.5.1`+).
Sin ese dato usa `{id de la norma} - {id del archivo} - {reg_title}`; sin
ninguno, ocr-core usa el nombre del archivo recibido. El detalle está en
`contracts/normatividad-ocr-markdown/README.md`.
- `OCR_TELEMETRY_FORWARD_ENABLED=true`: exige esquema y procedencia en `/meta`.
  El bloque `execution` se reenvía sin reinterpretarlo, incluida la identidad
  de host/instancia, el motor y la configuración versionada del pipeline.
- `OCR_FORCE_REPROCESS_ENABLED=true`: solo ignora cache para los flags de
  `reprocess_artifacts` y envía `overwrite=true` únicamente para ellos.
- `OCR_QUEUE_HEARTBEAT_ENABLED=true`: renueva jobs largos; debe habilitarse
  antes que la recuperación de `processing` vencido en Munis.
- Independiente de los flags: si la cola trae `execution_request`, un
  artefacto servido desde cache se reporta como
  `{"available": true, "origin": "generated", "written": false}` para que Munis
  conserve la versión vigente; sin ese bloque se mantiene el booleano `true`.

## Orden de activación

1. desplegar Munis nuevo con flags apagados y ejecutar migraciones;
2. verificar el flujo actual con el stack vigente;
3. drenar y detener temporalmente este worker;
4. desplegar core 0.4.0 y comprobar `/ready` y `/meta`;
5. desplegar este integrador con todos los flags apagados;
6. validar un item controlado sin reproceso;
7. activar telemetría en canary;
8. activar reproceso real en canary;
9. activar source reuse en canary;
10. activar heartbeat y recién después recuperación de processing vencido.

## Rollback

Los flags se apagan en orden inverso. Antes de volver a un core anterior se
drena y detiene el worker. Munis conserva estructuras aditivas y acepta
callbacks booleanos. Nunca se reinicia el core mientras este worker mantenga
un job oficial activo.

## Validación local

```bash
python3 -m compileall -q adapter/app adapter/tests
PYTHONPATH=adapter python3 -m unittest discover -s adapter/tests -v
```

No usar `docker compose up` como prueba: esa orden inicia el consumo continuo
de la cola institucional.
