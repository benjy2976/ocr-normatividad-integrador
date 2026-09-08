# Matriz de dependencias y licencias — normatividad-services

> Vista legible de `matriz-dependencias.yml` (fuente de verdad, schema 2.0). Componentes: `adapter/` (worker que consume la cola de Normatividad y llama a ocr-core) y `search/` (indexación/búsqueda en OpenSearch). Salud: **ok** — 0 incompatibles, 0 conflictos potenciales.

| Componente | Ecosistema | Versión | Directa | Integración | Licencia | Compatibilidad | Observaciones |
|---|---|---|---|---|---|---|---|
| requests | python | 2.32.3 | Sí | library | Apache-2.0 | compatible | Único dependency directo del adapter. |
| fastapi | python | 0.115.0 | Sí | library | MIT | compatible | — |
| uvicorn | python | 0.30.6 | Sí | library | BSD-3-Clause | compatible | — |
| pydantic | python | 2.8.2 | Sí | library | MIT | compatible | — |
| opensearch-py | python | 2.7.1 | Sí | library | Apache-2.0 | compatible | — |

## Hallazgo principal

Sin dependencias con copyleft fuerte ni cláusula de red. Todo el conjunto es permisivo (MIT/BSD/Apache-2.0), compatible con cualquier régimen que se determine para el proyecto. El punto sensible de este repositorio **no es de licenciamiento de dependencias sino de datos**: `docs/proyecto.yml` registra `data.personal_data: true` (evidencia real de exposición en resultados de búsqueda) — corresponde a la fase de seguridad, no a esta matriz.
