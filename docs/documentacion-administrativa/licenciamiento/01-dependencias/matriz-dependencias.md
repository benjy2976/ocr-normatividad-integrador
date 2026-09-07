# Matriz de dependencias y licencias — normatividad-services

> Componentes: `adapter/` (worker que consume la cola de Munis y llama a ocr-core) y `search/` (indexación/búsqueda en OpenSearch). Datos extraídos de `adapter/requirements.txt` y `search/requirements.txt`.

| Componente | Capa | Versión | Directa | Forma de integración | Licencia de origen | Compatibilidad con licencia elegida | Observaciones |
|---|---|---|---|---|---|---|---|
| requests | adapter | 2.32.3 | Sí | library | Apache-2.0 | PENDIENTE | Único dependency directo del adapter. |
| fastapi | search | 0.115.0 | Sí | library | MIT | PENDIENTE | — |
| uvicorn | search | 0.30.6 | Sí | library | BSD-3-Clause | PENDIENTE | — |
| pydantic | search | 2.8.2 | Sí | library | MIT | PENDIENTE | — |
| opensearch-py | search | 2.7.1 | Sí | library | Apache-2.0 | PENDIENTE | — |

## Hallazgo principal

Sin dependencias con copyleft fuerte ni cláusula de red. Todo el conjunto es permisivo (MIT/BSD/Apache-2.0). El punto sensible de este repositorio **no es de licenciamiento de dependencias sino de datos**: `docs/proyecto.yml` ya registra `data.personal_data: true` (evidencia real: un resultado de búsqueda expuso nombre y circunstancia de licencia por maternidad de una persona). Ese hallazgo pertenece a la fase de seguridad/datos, no a esta matriz, pero se deja anotado aquí porque puede condicionar la decisión institucional de licenciamiento del proyecto como conjunto (p. ej. si se evalúa publicar el código como software público, el dato personal expuesto en resultados no debe confundirse con el código fuente en sí).

Al ser `normatividad-services` un `utility_component` sin distribución externa, la evaluación de licencia es de menor criticidad que en `ocr-core`.
