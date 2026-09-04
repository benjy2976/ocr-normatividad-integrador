# normatividad-services

Todo lo que conecta la cola OCR de Normatividad (Munis) con `ocr-core`:
consumo de la cola, orquestacion del OCR via HTTP, y busqueda documental
sobre los resultados. Un solo repo porque ambas partes comparten el mismo
acoplamiento de dominio (Normatividad) y la misma dependencia de
infraestructura (el cache compartido con `ocr-core`) — separarlas en dos
repos no aportaba aislamiento real, solo overhead de mantenimiento.

Repo nuevo, sin historia heredada. Reemplaza los repos `normatividad-ocr-adapter`
y `ocr-search` (creados primero por separado, luego fusionados aqui).

Ver `context.md` para el modelo de dominio de Normatividad (estados de
cola, reglas de `enqueue()`, la distincion entre las rutas de storage que
Munis usa, y las lecciones de seguridad al probar contra produccion real)
y `TEST_OFICIAL_2_REPOS.md` en la carpeta padre para la corrida de
verificacion completa.

## Estructura

```
adapter/     consumidor de la cola OCR de Normatividad
  app/normatividad_client.py   cliente HTTP hacia Munis
  app/ocr_core_client.py        cliente HTTP hacia ocr-core (POST /jobs)
  app/worker.py                 orquestacion: pull-next -> ocr-core -> report
search/      busqueda documental sobre los artefactos que produce ocr-core
  app/search_api.py             API HTTP (GET /search)
  app/search_indexer.py         indexador continuo (lee .jsonl -> OpenSearch)
  app/search_common.py          schema de indexacion, acoplado a Normatividad
```

Cada subcarpeta tiene su propio `Dockerfile` — son servicios/imagenes
distintas dentro del mismo repo, no comparten runtime.

## Arquitectura

```
normatividad-worker (adapter/)
  -> pull-next / mark-processing (Normatividad)
  -> download-source (Normatividad) -> {OCR_SHARED_CACHE_DIR}/_inbox/*.pdf
  -> POST /jobs (ocr-core)          -> ocr-core corre preflight + OCR
  -> GET /jobs/{id} (polling)       -> ocr-core escribe pdf/text directo
                                        en {OCR_SHARED_CACHE_DIR}
  -> report_artifacts / skip / block / fail (Normatividad)

ocr-search-indexer (search/)
  -> lee {OCR_SHARED_CACHE_DIR}/**/*.jsonl
  -> indexa en OpenSearch
ocr-search-api (search/)
  -> GET /search sobre ese indice
```

Este repo **no ejecuta OCR** en ninguna de sus dos partes — no tiene
Tesseract, OCRmyPDF, OpenCV ni modelos YOLO. Todo el motor vive en
`ocr-core`, consumido por HTTP. `OCR_SHARED_CACHE_DIR` debe ser el mismo
volumen montado en `ocr-core` y en ambos servicios de aqui.

## Decision de diseno: esquema de busqueda acoplado a Normatividad

`search/app/search_common.py` indexa campos especificos de Normatividad
(`regulation_file_id`, `regulation_id`, `reg_year`, `reg_title`, etc.),
tomados del `metadata` opaco que trae cada artefacto `text`. Es intencional
y coherente con que este repo entero sea "la integracion con Normatividad" —
si en el futuro se necesita indexar documentos de otra plataforma, ese es
el momento de extraer `search/` a un repo propio y generalizar el esquema
(`metadata: {}` passthrough, nuevo schema versionado).

## Variables de entorno

| Variable | Default | Descripcion |
|---|---|---|
| `NORMATIVIDAD_BASE_URL` | (obligatoria) | URL base de Normatividad |
| `NORMATIVIDAD_OCR_TOKEN` | (obligatoria) | Bearer token de autenticacion |
| `OCR_CORE_URL` | (obligatoria) | URL interna de ocr-core, ej. `http://ocr-core:8000` |
| `OCR_CORE_JOB_TIMEOUT_SECONDS` | 1800 | Timeout esperando a que un job de ocr-core termine |
| `OCR_CORE_JOB_POLL_INTERVAL_SECONDS` | 2 | Intervalo de polling de `GET /jobs/{id}` |
| `OCR_SHARED_CACHE_DIR` | `/nfs-cache` | Raiz de storage compartido con ocr-core |
| `OCR_WORKER_NAME` | `normatividad-worker-1` | Nombre del worker en logs |
| `OCR_WORKER_CONCURRENCY` | 1 | Consumidores paralelos dentro del mismo servicio |
| `OCR_POLL_INTERVAL_SECONDS` | 10 | Segundos entre polls si la cola esta vacia |
| `OCR_WORKER_ENABLED` | true | `false` deshabilita sin borrar el contenedor |
| `OCR_CALLBACK_TIMEOUT_SECONDS` | 30 | Timeout HTTP para callbacks a Normatividad |
| `OCR_DOWNLOAD_TIMEOUT_SECONDS` | 120 | Timeout HTTP para descarga del PDF fuente |
| `OCR_WORKER_MAX_CONSECUTIVE_ERRORS` | 20 | Errores seguidos antes de detener el proceso |
| `OCR_WORKER_LOG_LEVEL` | INFO | Nivel de log del worker |
| `OPENSEARCH_URL` | `http://opensearch:9200` | URL del motor de busqueda |
| `OPENSEARCH_INDEX` | `munis_ocr_pages` | Indice donde se cargan las paginas OCR |
| `SEARCH_INDEXER_POLL_INTERVAL_SECONDS` | 300 | Frecuencia de escaneo del indexador |
| `SEARCH_INDEXER_BATCH_SIZE` | 500 | Paginas por lote enviadas a OpenSearch |
| `SEARCH_INDEXER_LOG_LEVEL` | INFO | Nivel de log del indexador |

## Uso

```bash
cp .env.example .env
docker compose up --build
```

Requiere la red Docker externa `grh_network` (compartida con `ocr-core`) y
el mismo volumen que usa `ocr-core` para `OCR_SHARED_CACHE_DIR` — ver la
nota en `docker-compose.yml` sobre el nombre real del volumen `external`.

Indexar una vez manualmente:

```bash
docker compose run --rm ocr-search-indexer python3 -m app.search_indexer --once
```

Buscar:

```bash
curl 'http://localhost:18020/search?q=liquidacion&year=2021'
```

Ver el contrato completo de `/search` en el `api.md` de `ocr-core`, seccion
"API de busqueda" — se preserva ahi como fuente normativa unica.

## Depuracion manual del worker

```bash
python worker_main.py pull-next
python worker_main.py once
python worker_main.py mark-processing <queue_id>
python worker_main.py download-source <queue_id> --output /tmp/test.pdf
```

## Reglas de negocio preservadas del worker historico

- Si la cola no solicita `pdf` ni `text`, se reporta `skip` sin descargar nada.
- Si el PDF ya tiene texto util y **solo** se pidio `pdf` (no `text`), se
  reporta `skip` — no hay nada nuevo que aportar.
- Si `ocr-core` detecta firma digital durante el OCR (no en el preflight
  inicial), se reporta `block` en vez de `fail`.
- Artefactos ya cacheados (`has_pdf`/`has_text` + archivo existente en el
  storage compartido) no se vuelven a pedir a `ocr-core`.
