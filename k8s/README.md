# k8s — normatividad-services

Manifiestos de Kubernetes para este repo, adaptados de los del monorepo
original (`ocr-service/base/`). Cubre lo que le corresponde a este repo
tras el split: el worker que consume la cola de Normatividad, y todo el
stack de busqueda (OpenSearch + indexer + API).

## Que cambio respecto al manifiesto original

- **El worker ya no es el `ocr-worker` monolitico** (imagen
  `ryuk89/ocr-service:*` que tambien contenia el motor OCR completo). Es
  `normatividad-worker`, imagen liviana `<registro>/normatividad-worker:latest`
  construida desde `adapter/` — sin Tesseract, OCRmyPDF, OpenCV ni modelos
  YOLO. Llama a `ocr-core` por HTTP (`OCR_CORE_URL`), no importa nada de
  su codigo.
- **Sin GPU ni `initContainer` de seed-models** en el worker — confirmado
  que nunca los necesito (ver `../context.md`, seccion GPU). El seed de
  modelos ahora vive en el deployment de `ocr-core` en su propio repo.
- `ocr-search-api` y `ocr-search-indexer` usan `<registro>/ocr-search:latest`
  (construida desde `search/`) en vez de la imagen monolitica.
- El `Secret` se renombro de `ocr-service-secret` (con `MUNIS_BASE_URL`)
  a `normatividad-services-secret` (con `NORMATIVIDAD_BASE_URL`) —
  terminologia Munis -> Normatividad, igual que en el resto del split.

## Dependencia cruzada con `ocr-core`

`normatividad-worker` y `ocr-search-indexer` referencian el PVC
`ocr-shared-cache` **por nombre** (`claimName: ocr-shared-cache`), pero
ese PVC lo crea el repo `ocr-core` (`storage/01-pvc-shared-cache.yaml`).
Ambos repos deben desplegarse en el **mismo namespace** (`ocr-service`).
Si se aplica este repo antes que `ocr-core`, los pods que necesitan ese
PVC quedan en `Pending` hasta que aparezca — no es un error, solo orden.

De igual manera, `OCR_CORE_URL: http://ocr-core:8000` (en
`02-configmap-worker.yaml`) asume que el `Service` `ocr-core`
ya existe en el mismo namespace.

## Uso

```bash
# Reemplazar <registro> en 04-deployment-worker.yaml, 06-deployment-search-api.yaml
# y 07-deployment-search-indexer.yaml antes de aplicar.
# Copiar 01-secret.example.yaml a un Secret real (no versionar el token real).
kubectl apply -k k8s/
```

Pendiente, no resuelto en este split: el namespace `ocr-service` lo
declaran tanto este repo como `ocr-core` — aplicar ambos es idempotente,
pero valdria la pena decidir cual de los dos "posee" el namespace de
verdad (o moverlo a un tercer manifiesto compartido fuera de ambos repos).
