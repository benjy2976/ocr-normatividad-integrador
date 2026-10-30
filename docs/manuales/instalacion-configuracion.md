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

## Operación contra producción real

La cola es de producción (Normatividad, GORE Huánuco) y los documentos pueden
contener datos personales. Antes de cualquier prueba, leer las reglas de
seguridad operativa del `AGENTS.md`.

### Prueba de un solo ítem

Se usa `once`, que procesa como máximo un ítem y termina. Nunca se prueba con
el bucle continuo.

```bash
# 1. Detener el bucle si está activo, para no tener dos consumidores
docker compose stop normatividad-worker

# 2. Confirmar que el core responde y que hay una sola instancia con ese alias
docker run --rm --network grh_network curlimages/curl:latest -sS \
  http://core-ocr:8000/health -w " HTTP %{http_code}\n"
docker ps --filter network=grh_network

# 3. Procesar un ítem con el mismo entorno, red y volumen NFS del servicio
docker compose run --rm normatividad-worker python3 worker_main.py once
echo "salida: $?"   # 0: procesó un ítem; 2: la cola estaba vacía
```

`OCR_CORE_URL` (en el `.env`) debe apuntar al alias del core en `grh_network`,
y el volumen montado en `/nfs-cache` debe ser el mismo que usa el core
(`ocr-core_ocr_nfs_cache`). Si hay más de un contenedor con ese alias, el
resultado no es confiable.

### Operación continua

```bash
docker compose up -d                          # worker, OpenSearch, API e indexador
docker compose logs -f normatividad-worker    # seguir el procesamiento
docker compose stop normatividad-worker       # detener el consumo de la cola
```

- `OCR_WORKER_CONCURRENCY` controla cuántos ítems se atienden a la vez.
  Un backlog grande alarga el tiempo de procesamiento, pero no genera una
  ráfaga de carga.
- En los primeros segundos, `ocr-search-indexer` puede registrar errores de
  conexión contra OpenSearch mientras este arranca. `restart: unless-stopped`
  lo recupera solo.
- **Antes de reiniciar o recrear el core, detener el worker.** Si el core se
  reinicia a mitad de un trabajo, el reintento choca con sus propios artefactos
  (`overwrite=false`) y el ítem termina en `failed` (incidente del 2026-09-07
  en `../../context.md`).
- Si el host cae a mitad de un ítem, Normatividad lo libera solo al vencer el
  lease (`lease_seconds: 900`).

### Prueba contra una instancia local de Normatividad

Para no tocar producción, se puede apuntar a una instancia local restaurada (por
ejemplo `NORMATIVIDAD_BASE_URL=http://gp_webserver`):

1. **Rutas:** el core y el integrador deben montar como `/nfs-cache` la misma
   ruta que usa el `PATH_DESTINO_OCR` de esa instancia. Si no coinciden,
   `POST /artifacts` responde `422` (ver "Dos rutas de storage" en
   `../../context.md`). Al volver a producción, se restaura el volumen NFS real
   en los dos.
2. **Fuente:** copiar el PDF a la ruta que espera `Storage::disk('ftp_destino')`
   (columna `file_ruta` de `regulation_files`), para que `GET /source` lo
   encuentre.
3. **Encolar** sin la UI, forzando:

   ```bash
   docker exec <contenedor_app> php artisan tinker --execute="
   \$file = \App\Models\Normatividad\RegulationFile::findOrFail(<id>);
   \$manager = app(\App\Services\Normatividad\Ocr\RegulationFileOcrManager::class);
   \$manager->enqueue(\$file, 'manual_test', null, true, ['pdf' => true, 'text' => true]);
   "
   ```

### Errores esperables

| Síntoma | Causa probable |
|---|---|
| `POST /artifacts` responde `422` "No existe el artefacto esperado…" | El `/nfs-cache` del core y del integrador no es la ruta que usa `PATH_DESTINO_OCR` en Normatividad |
| El integrador no resuelve el core o recibe respuestas de otro | El core está apagado, o hay más de un contenedor con el mismo alias en `grh_network` |
| `pull-next` responde `204` y `once` sale con `2` | Cola vacía; no es un error |
| `NORMATIVIDAD_BASE_URL no esta configurado` | Variable vacía o mal escrita en el `.env` |

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
| `OCR_WORKER_LOG_MAX_SIZE` | `10m` | Tamaño máximo de cada archivo de log del worker antes de rotar |
| `OCR_WORKER_LOG_MAX_FILE` | 5 | Archivos de log conservados; al rotar se elimina el más antiguo |
| `OCR_SHADOW_ENABLED` | false | Habilita la duplicación no autoritativa hacia el core candidato |
| `OCR_SHADOW_CORE_URL` | `http://core-ocr:8000` | URL interna del core candidato |
| `OCR_SHADOW_OUTPUT_ROOT` | `/shadow-cache/review` | Raíz privada usada en los destinos del candidato; nunca debe apuntar al NFS |
| `OCR_SHADOW_SUBMIT_TIMEOUT_SECONDS` | 30 | Timeout exclusivo para que el candidato copie y acepte la fuente NFS |
| `OCR_SHARED_CACHE_DIR` | `/nfs-cache` | Raíz de storage compartido con ocr-core |
| `OCR_WORKER_NAME` | `normatividad-worker-1` | Nombre del worker en logs |
| `OCR_WORKER_CONCURRENCY` | 1 | Consumidores paralelos dentro del mismo servicio |
| `OCR_POLL_INTERVAL_SECONDS` | 10 | Segundos entre polls si la cola está vacía |
| `OCR_WORKER_ENABLED` | true | `false` deshabilita sin borrar el contenedor |
| `OCR_WORKER_RESTART_POLICY` | `unless-stopped` | Política Docker del worker; usar `no` junto con `OCR_WORKER_ENABLED=false` para impedir el autoarranque |
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
- Ver "Operación contra producción real" para la prueba de un solo ítem y el
  encendido y apagado del modo continuo.

## Contacto institucional
TODO — sin designación institucional formal registrada (ver `../proyecto.yml`,
`project.responsible_unit`).

## Licencia aplicable
Pendiente — ver `../proyecto.yml`, `licensing.workflow_state`, y el expediente completo en `../licenciamiento/`.
