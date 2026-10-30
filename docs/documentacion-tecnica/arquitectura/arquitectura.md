# Arquitectura

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

## Referencias

- Modelo de dominio de Normatividad (estados de cola, reglas de
  `enqueue()`, distincion entre rutas de storage): `../../../context.md`.
- Motor OCR consumido por HTTP: lo que este repo usa de `ocr-core` está en
  `../../contracts/ocr-core-http/README.md`.
- Verificacion contra produccion y procedimiento de operacion:
  `../../pruebas-validaciones/verificacion-componente.md` y
  `../../manuales/instalacion-configuracion.md`.
