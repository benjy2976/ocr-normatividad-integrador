# normatividad-services

Todo lo que conecta la cola OCR de Normatividad con `ocr-core`:
consumo de la cola, orquestacion del OCR via HTTP, y busqueda documental
sobre los resultados. Un solo repo porque ambas partes comparten el mismo
acoplamiento de dominio (Normatividad) y la misma dependencia de
infraestructura (el cache compartido con `ocr-core`) — separarlas en dos
repos no aportaba aislamiento real, solo overhead de mantenimiento.

Repo nuevo, sin historia heredada. Reemplaza los repos `normatividad-ocr-adapter`
y `ocr-search` (creados primero por separado, luego fusionados aqui).

No es una solucion independiente — es un componente utilitario que apoya
el proceso de digitalizacion de Normatividad (ver `docs/proyecto.yml`,
`project.kind: utility_component`). Sin Normatividad no tiene ningun proposito
propio.

Ver `context.md` para el modelo de dominio de Normatividad (estados de
cola, reglas de `enqueue()`, la distincion entre las rutas de storage que
Normatividad usa, y las lecciones de seguridad al probar contra produccion real)
y `TEST_OFICIAL_2_REPOS.md` en la carpeta padre para la corrida de
verificacion completa.

## Estructura

```
adapter/     consumidor de la cola OCR de Normatividad
  app/normatividad_client.py   cliente HTTP hacia Normatividad
  app/ocr_core_client.py        cliente HTTP hacia ocr-core (POST /jobs)
  app/shadow_core_client.py     duplicacion aislada hacia el core candidato
  app/worker.py                 orquestacion: pull-next -> ocr-core -> report
search/      busqueda documental sobre los artefactos que produce ocr-core
  app/search_api.py             API HTTP (GET /search)
  app/search_indexer.py         indexador continuo (lee .jsonl -> OpenSearch)
  app/search_common.py          schema de indexacion, acoplado a Normatividad
```

Cada subcarpeta tiene su propio `Dockerfile` — son servicios/imagenes
distintas dentro del mismo repo, no comparten runtime.

## Documentacion

- `docs/proyecto/ficha-proyecto.md` y `docs/documentacion-tecnica/ficha-tecnica-componente.md` — ficha tecnica del componente (molde `utility_component`).
- `docs/documentacion-tecnica/reglas-negocio.md` — reglas de negocio trazables.
- `docs/documentacion-tecnica/arquitectura/arquitectura.md` — diagrama de flujo y decision del
  esquema de busqueda.
- `docs/manuales/instalacion-configuracion.md` — instalacion, uso y
  variables de entorno.
- `context.md` — modelo de dominio de Normatividad.
- `docs/proyecto.yml` — metadata del proyecto (perfil, etapa, licenciamiento).

Este repo esta migrando su documentacion a la estructura de la skill
`documentar-auditar-software` (perfil `generic`). Ver `docs/proyecto.yml`
para el estado de la migracion.

## Reglas de negocio

Ver `docs/documentacion-tecnica/reglas-negocio.md` — tabla trazable de las
reglas preservadas del worker histórico (skip/block/cache) más las de
`enqueue()` en Normatividad de las que este repo depende.

El fan-out shadow está apagado por defecto. Cuando se habilita, envía el mismo
`source.path` del NFS al core candidato, remapea las salidas a su volumen
privado y nunca usa ese resultado para modificar la cola ni la caché oficial.
