# Manual de instalación y configuración

## Datos generales
- **Software:** normatividad-services
- **Versión:** 0.1.0 (ver `../proyecto.yml`)
- **Descripción:** Integración entre la cola OCR de Normatividad y
  `ocr-core`: `adapter/` (consumo de cola) y `search/` (búsqueda documental).

## Requisitos de hardware
Ninguno especial — este repo no ejecuta OCR, sin necesidad de GPU. Los
recursos reales los consume `ocr-core` (repo aparte).

## Requisitos de software
- Docker + Docker Compose.
- Red Docker externa `grh_network` (compartida con `ocr-core`).
- El mismo volumen que usa `ocr-core` para `OCR_SHARED_CACHE_DIR` — ver la
  nota en `../../docker-compose.yml` sobre el nombre real del volumen
  `external`.

## Instalación paso a paso

```bash
cp .env.example .env
docker compose up --build
```

Indexar una vez manualmente:

```bash
docker compose run --rm ocr-search-indexer python3 -m app.search_indexer --once
```

Buscar:

```bash
curl 'http://localhost:18020/search?q=liquidacion&year=2021'
```

Ver el contrato completo de `/search` en el `api.md` de `ocr-core`, sección
"API de búsqueda" — se preserva ahí como fuente normativa única.

### Depuración manual del worker

```bash
python worker_main.py pull-next
python worker_main.py once
python worker_main.py mark-processing <queue_id>
python worker_main.py download-source <queue_id> --output /tmp/test.pdf
```

## Configuración

| Variable | Default | Descripción |
|---|---|---|
| `NORMATIVIDAD_BASE_URL` | (obligatoria) | URL base de Normatividad |
| `NORMATIVIDAD_OCR_TOKEN` | (obligatoria) | Bearer token de autenticación |
| `OCR_CORE_URL` | (obligatoria) | URL interna de ocr-core, ej. `http://ocr-core:8000` |
| `OCR_CORE_JOB_TIMEOUT_SECONDS` | 1800 | Timeout esperando a que un job de ocr-core termine |
| `OCR_CORE_JOB_POLL_INTERVAL_SECONDS` | 2 | Intervalo de polling de `GET /jobs/{id}` |
| `OCR_CORE_META_TTL_SECONDS` | 60 | Vigencia local de las capacidades consultadas en `/meta` |
| `OCR_CORE_SUBMIT_MAX_RETRIES` | 2 | Reintentos de `POST /jobs`; solo se usan con clave idempotente |
| `OCR_FORCE_REPROCESS_ENABLED` | false | Respeta `reprocess_artifacts` y activa `overwrite` selectivo |
| `OCR_TELEMETRY_FORWARD_ENABLED` | false | Solicita y reenvía procedencia y métricas del core |
| `OCR_SOURCE_REUSE_ENABLED` | false | Usa `pdf_on_skip=reuse` si el core publica la capacidad |
| `OCR_CORE_CAPABILITIES_REQUIRED` | false | Falla cerrado si faltan capacidades requeridas |
| `OCR_QUEUE_HEARTBEAT_ENABLED` | false | Renueva el lease de jobs largos contra Munis nuevo |
| `OCR_QUEUE_HEARTBEAT_SECONDS` | 60 | Intervalo entre renovaciones del lease |
| `OCR_SHADOW_ENABLED` | false | Habilita la duplicación no autoritativa hacia el core candidato |
| `OCR_SHADOW_CORE_URL` | `http://core-ocr:8000` | URL interna del core candidato |
| `OCR_SHADOW_OUTPUT_ROOT` | `/shadow-cache/review` | Raíz privada usada en los destinos del candidato; nunca debe apuntar al NFS |
| `OCR_SHADOW_SUBMIT_TIMEOUT_SECONDS` | 30 | Timeout exclusivo para que el candidato copie y acepte la fuente NFS |
| `OCR_SHARED_CACHE_DIR` | `/nfs-cache` | Raíz de storage compartido con ocr-core |
| `OCR_WORKER_NAME` | `normatividad-worker-1` | Nombre del worker en logs |
| `OCR_WORKER_CONCURRENCY` | 1 | Consumidores paralelos dentro del mismo servicio |
| `OCR_POLL_INTERVAL_SECONDS` | 10 | Segundos entre polls si la cola está vacía |
| `OCR_WORKER_ENABLED` | true | `false` deshabilita sin borrar el contenedor |
| `OCR_CALLBACK_TIMEOUT_SECONDS` | 30 | Timeout HTTP para callbacks a Normatividad |
| `OCR_DOWNLOAD_TIMEOUT_SECONDS` | 120 | Timeout HTTP para descarga del PDF fuente |
| `OCR_WORKER_MAX_CONSECUTIVE_ERRORS` | 20 | Errores seguidos antes de detener el proceso |
| `OCR_WORKER_LOG_LEVEL` | INFO | Nivel de log del worker |
| `OPENSEARCH_URL` | `http://opensearch:9200` | URL del motor de búsqueda |
| `OPENSEARCH_INDEX` | `munis_ocr_pages` | Índice donde se cargan las páginas OCR |
| `SEARCH_INDEXER_POLL_INTERVAL_SECONDS` | 300 | Frecuencia de escaneo del indexador |
| `SEARCH_INDEXER_BATCH_SIZE` | 500 | Páginas por lote enviadas a OpenSearch |
| `SEARCH_INDEXER_LOG_LEVEL` | INFO | Nivel de log del indexador |

El core candidato debe montar el mismo NFS como `/nfs-cache:ro`. El adaptador
solo le entrega el job después de que el core oficial lo aceptó; cualquier
error del segundo envío se registra y no se propaga al ciclo oficial.

Pruebas unitarias del aislamiento shadow:

```bash
PYTHONPATH=adapter python3 -m unittest discover -s adapter/tests -v
```

## Buenas prácticas y recomendaciones
- No reiniciar `ocr-core` en caliente mientras `normatividad-worker` esté
  activo contra producción real — ver incidente documentado en
  `../../context.md`, sección "Operación sostenida real contra producción".
- Ver `../../TEST_OFICIAL_2_REPOS.md` (carpeta padre `new_ocr/`) para el
  procedimiento completo de encendido/apagado seguro en modo continuo.

## Contacto institucional
TODO — sin designación institucional formal registrada (ver `../proyecto.yml`,
`project.responsible_unit`).

## Licencia aplicable
Pendiente — ver `../proyecto.yml`, `licensing.workflow_state`, y el expediente completo en `../licenciamiento/`.
