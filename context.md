# Contexto de decision: normatividad-services

## Que es Normatividad

Sistema de gestion documental del Gobierno Regional de Huanuco (GORE
Huanuco). Normatividad administra normas (resoluciones, ordenanzas, actas,
etc.) y su OCR. Produccion real vive en
`https://proyectos.regionhuanuco.gob.pe`, corre en Kubernetes (fuera del
alcance de este repo).

Este repo es la capa que conecta esa cola con `ocr-core`: consume trabajo,
lo manda a procesar, reporta el resultado. No conoce el motor OCR mas alla
de su contrato HTTP (`POST /jobs`).

## Modelo de datos de la cola (schema `normatividad`, Postgres)

Dos tablas relevantes:

- `regulation_files`: un archivo fisico por norma/tomo. Columnas clave:
  `file_ruta` (ruta relativa dentro del disco `ftp_destino`), `file_tomo`,
  `file_nro_tipo`, `file_md5`.
- `regulation_file_ocr_queues`: una fila por intento de OCR encolado.
  Columnas clave: `regulation_file_id`, `status`, `trigger_type`,
  `requested_artifacts_json`, `response_payload_json` (aqui queda el
  payload completo que reporta el worker, util para debug).

Catalogo de `status` en `regulation_file_ocr_queues`:

```
0 = pending | 1 = leased | 2 = processing | 3 = done
4 = failed  | 5 = obsolete | 6 = cancelled | 7 = skipped | 8 = blocked
```

Catalogo de `status` en `regulation_file_ocrs` (el registro "vigente" por
archivo, no por intento):

```
0 = not_requested | 1 = eligible | 2 = queued | 3 = processing
4 = done | 5 = failed | 6 = obsolete | 7 = skipped | 8 = blocked
```

## Reglas de negocio de `RegulationFileOcrManager::enqueue()`

No es un simple insert. La logica real (en el codigo de Normatividad, no en este
repo):

1. Evalua elegibilidad (`eligibilityService->evaluate($file)`) — si no es
   elegible y no se fuerza (`force=true`), marca `skipped` y sale.
2. Calcula que artefactos faltan (`resolveMissingArtifacts`) salvo que se
   fuerce, en cuyo caso encola exactamente lo pedido.
3. Si ya hay un item activo en cola para ese archivo, fusiona los
   artefactos pedidos en vez de crear uno nuevo (`resolveActiveQueueContext`).
4. Solo si hay algo nuevo que pedir, crea la fila de cola.

Para pruebas manuales (ver "Prueba contra una instancia local de
Normatividad" en `docs/manuales/instalacion-configuracion.md`), se usa
`force=true` explicito via `artisan tinker` — evita depender de la UI y
reprocesa aunque el archivo ya tenga OCR previo.

## Autenticacion del servicio OCR (`OcrServiceAuth`)

Middleware propio de Normatividad (`app/Http/Middleware/OcrServiceAuth.php`):
acepta **IP permitida** (`config('ocr.allowed_ips')`) **o** bearer token
(`config('ocr.service_token')`) — no ambos. Si ninguno matchea, `403`, no
`404`. Si alguna vez un endpoint de `/api/ocr/normatividad/*` devuelve
`404` en vez de `403`/`401`, el problema es de ruteo (nginx/PHP-FPM), no
de autenticacion — ya nos paso una vez con una instancia de backup donde
`/api/*` completo estaba roto por un conflicto con otro servicio corriendo
en el mismo host.

## Dos rutas de storage que NO son lo mismo

Descubierto investigando un `422` real durante las pruebas:

- `PATH_DESTINO` (disco `ftp_destino` en `config/filesystems.php` de
  Normatividad) — de donde Normatividad **sirve** el PDF fuente cuando el worker hace
  `GET /queue/{id}/source`. En produccion, el archivo fuente real vive en
  un tercer servidor (ver siguiente seccion), no necesariamente en el
  mismo NFS que usa `ocr-core`.
- `PATH_DESTINO_OCR` (disco `ocr_cache`) — de donde Normatividad **verifica** que
  el artefacto OCR ya existe, al recibir `POST /queue/{id}/artifacts`.
  Este es el que tiene que coincidir exactamente con
  `OCR_SHARED_CACHE_DIR` de `ocr-core`, o `report_artifacts` falla con
  `422 "No existe el artefacto esperado..."` aunque el OCR haya corrido
  perfecto.

En Kubernetes, esta confusion tenia una version mas grave: el deployment
de `ocr-api` real **no montaba el PVC `ocr-shared-cache`** — solo lo
montaban `ocr-worker` y `ocr-search-indexer`. Se corrigio (ver historial
de `ocr-core/docs/documentacion-tecnica/arquitectura/arquitectura.md`), pero el despliegue a K8s quedo pausado por
decision del operador.

## El origen real de los documentos: tres servidores, no uno

Investigando la infraestructura real se identificaron tres IPs con roles
distintos, faciles de confundir:

| IP | Rol |
|---|---|
| `10.0.0.102` | Cache de artefactos OCR (exports NFS: `ocr`, `datos_siaf`, `minio`) |
| `10.0.0.103` | Datos completos de Normatividad — el archivo fuente real (carpeta `regulations/` con miles de PDFs). Tambien es `FTP_HOST_ORIGEN` en `config/filesystems.php` de Normatividad (disco `origen`, driver FTP) |
| `proyectos.regionhuanuco.gob.pe` | Produccion real, HTTP publico |

Para una instancia de Normatividad de **prueba/backup** local, `PATH_DESTINO`
suele apuntar a disco local (no a ninguno de estos servidores) — hay que
copiar el PDF manualmente a la ruta esperada para poder descargarlo via
`GET /source`. Ver "Prueba contra una instancia local de Normatividad" en
`docs/manuales/instalacion-configuracion.md`.

## Seguridad operativa al probar contra produccion real

Checklist usado (y que funciono) la primera vez que se probo este repo
contra produccion. Las reglas vigentes estan en el `AGENTS.md`: desde el
2026-10-19 el punto 1 ya no se verifica en cada prueba.

1. Confirmar que el `ocr-worker` de Kubernetes esta escalado a `0/0` —
   evita que dos consumidores compitan por la misma cola.
2. Verificar que `ocr-api` de Kubernetes es `ClusterIP` sin `Ingress` —
   no hay forma de que una URL mal escrita desde Docker termine ahi por
   accidente.
3. Un solo item (`worker_main.py once`), nunca el loop continuo, para la
   primera prueba.
4. Backstop natural: `lease_seconds: 900` en la configuracion de
   Normatividad — si algo falla a medio proceso sin reportar `fail`
   explicito, el item se libera solo a los 15 minutos.

Con ese checklist se corrio un item real de produccion
(`queue_id=198322`, `regulation_file_id=122850`) de punta a punta sin
incidentes el 2026-09-04 (resumen en
`docs/pruebas-validaciones/verificacion-componente.md`).

## Reglas de negocio del worker que sobrevivieron la migracion a HTTP

El worker viejo (dentro del monorepo, import in-process del motor) tenia
decisiones de negocio mezcladas con la ejecucion del OCR. Al migrar a
llamar `ocr-core` por HTTP, esas decisiones se preservaron explicitamente
en `adapter/app/worker.py` (no viven en `ocr-core`, que es generico):

- Si la cola no pide `pdf` ni `text`, se reporta `skip` sin descargar nada.
- Si el PDF ya tiene texto util y **solo** se pidio `pdf` (no `text`), se
  reporta `skip` — no hay artefacto nuevo que aportar. Esta regla no la
  puede inferir `ocr-core` porque es una decision de negocio, no tecnica.
- Si `ocr-core` reporta `status: failed` con un mensaje que parece error
  de firma digital detectada durante el OCR (no en el preflight inicial),
  se reclasifica como `block` en vez de `fail` ante Normatividad.
- Artefactos ya cacheados (`has_pdf`/`has_text` true + archivo existente
  en el storage compartido) no se vuelven a pedir a `ocr-core`.

## Operacion sostenida real contra produccion (2026-09-07)

Se encendio el stack completo (`normatividad-worker` + `opensearch` +
`ocr-search-api` + `ocr-search-indexer`) contra Normatividad real
(`https://proyectos.regionhuanuco.gob.pe`), con el `ocr-worker` de K8s
confirmado en `0/0`. Funciono como reemplazo de facto del worker de K8s
durante varias horas, procesando items reales de forma continua sin
intervencion. Los comandos vigentes estan en
`docs/manuales/instalacion-configuracion.md`, "Operación contra producción
real".

**Incidente real:** reiniciar `ocr-core` (en su propio repo) para aplicar
un fix mientras `normatividad-worker` seguia activo contra produccion
interrumpio un job a medio reportar — el reintento automatico choco con
sus propios artefactos ya escritos (`overwrite=false` en `POST /jobs`) y
el item termino en `status: failed` tras agotar reintentos. Se resolvio
re-encolando manualmente desde la UI de Normatividad. Leccion: apagar
`normatividad-worker` **antes** de reiniciar `ocr-core` en caliente
cuando ambos estan activos contra produccion real.

## Endpoint `GET /api/ocr/normatividad/queue/summary` (agregado 2026-09-07)

Normatividad no exponia ninguna forma de conocer el tamano real de la cola con
el token de servicio (`ocr.service`) — solo via `app/normatividad/ocr/summary`,
que requiere sesion web. Se agrego un endpoint nuevo en Normatividad
(`OcrServiceController::queueSummary()`), protegido por el mismo
middleware `ocr.service`, que devuelve **solo agregados** (conteo por
estado + fecha del pendiente mas antiguo, sin datos individuales de
expediente). Ya esta implementado y desplegado en produccion real —
confirmado con una llamada real (`pending: 0` en el momento de la prueba).

**Pendiente en este repo:** todavia no hay un cliente para este endpoint
en `adapter/app/normatividad_client.py` ni se usa desde el worker (por
ejemplo, para loguear el tamano de la cola al arrancar o antes de encender
el modo continuo). Es la siguiente mejora natural de observabilidad, no
implementada todavia.

Tambien se evaluo (no implementado) un endpoint `queue/requeue/{regulationFile}`
para reencolar manualmente sin necesitar sesion web — surgio del mismo
incidente de arriba, cuando no hubo forma de reencolar el item fallido
mas que pidiendole al operador que lo hiciera desde la UI.

## Esquema de busqueda acoplado a Normatividad (decision vigente)

`search/app/search_common.py` indexa campos especificos del dominio
(`regulation_file_id`, `reg_year`, `reg_title`, etc.) en vez de un
`metadata: {}` generico. Es coherente con que todo este repo sea "la
integracion con Normatividad" — si algun dia se necesita indexar
documentos de otra plataforma, ese es el momento de extraer `search/` a
un repo propio y generalizar el esquema, no antes.
