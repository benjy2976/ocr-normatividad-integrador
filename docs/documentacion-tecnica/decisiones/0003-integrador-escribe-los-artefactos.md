# 0003. El integrador subirá el PDF y escribirá los artefactos en el NFS

- **Estado:** aceptada, sin implementar
- **Fecha:** 2026-10-29
- **Decidió:** Walther Aguirre

> **Todavía no está implementada.** Hoy el integrador deja el PDF en
> `/nfs-cache/_inbox/`, usa `POST /jobs` por ruta, el core escribe los
> artefactos en el NFS, no se envía ningún token y un PDF de más de 256 MiB
> termina en `fail`.

## Contexto

Hoy el integrador deja el PDF fuente en `/nfs-cache/_inbox/` y le pasa a
`ocr-core` rutas del NFS: el core lee de ahí y escribe los artefactos oficiales
(`POST /jobs` por ruta). Se decidió que el core deje de acceder al
almacenamiento de sus consumidores y solo reciba y devuelva bytes. Del lado del
integrador, eso implica asumir la escritura en el NFS.

## Decisión

- El integrador descargará la fuente a un temporal local y la subirá con
  `POST /jobs/upload`, **por partes** (nunca con `files=` de `requests`, que
  arma el cuerpo completo en memoria).
- Descargará cada artefacto con `GET /jobs/{id}/artifacts/{nombre}`, también por
  partes, y lo escribirá en su ruta `artifacts.expected.*` de forma **atómica**:
  un temporal en la misma carpeta, `fsync` y `os.replace`.
- Decidirá si sobrescribe según RN-004 y el reproceso forzado, y borrará el
  trabajo en el core (`DELETE /jobs/{id}`) después de escribir.
- Si los artefactos del core ya expiraron (`expired: true` o `404`), volverá a
  enviar el trabajo con una `idempotency_key` nueva.
- El usuario y el modo de los archivos se toman del `.env` (por ejemplo
  `OCR_WORKER_UID`, `OCR_WORKER_GID` y `OCR_ARTIFACT_FILE_MODE`), con valores
  por defecto que reproducen lo actual. El usuario con que el consumidor final
  lee los archivos no forma parte del código.
- El límite de tamaño lo define el core. El integrador lo compara antes de
  subir (con `max_upload_bytes` de `/meta` o con el `413` del core) y reporta
  el ítem como **`block`** con `reason_code=source_exceeds_core_limit`, para
  poder encolarlo de nuevo cuando el límite suba.
- El integrador enviará `Authorization: Bearer ${OCR_CORE_TOKEN}` y verificará
  su `client_id` en `/meta` antes de tomar ítems. El core 0.5.1 ignora el
  encabezado, así que puede enviarse antes de que el core lo exija.

## Alternativas descartadas

- **Mantener el modo por ruta:** deja al core con acceso a documentos de
  producción y con capacidad de sobrescribir artefactos oficiales.

## Consecuencias

- Las rutas `artifacts.expected.*`, los callbacks, RN-001 a RN-011 y el
  indexador `search/` no cambian.
- El PDF fuente deja de pasar por el inbox del NFS.
- Validación prevista: comparar el mismo conjunto de PDF por ruta y por subida
  (mismo JSONL y Markdown, misma capa de texto, mismo dueño y modo) antes de
  desplegar. Después, ítems reales con `once`.
- Hasta que se implemente, un PDF que supera el límite del core termina en
  `fail` (ver los gaps del `AGENTS.md`).

## Evidencia

- `docs/contracts/ocr-core-http/README.md` (contrato vigente, por ruta).
