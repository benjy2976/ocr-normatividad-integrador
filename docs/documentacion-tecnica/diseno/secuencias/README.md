# Diagramas de secuencia

No exigibles para `utility_component`, pero adoptados como buena práctica. Documentados por flujo relevante, extrapolados del código real.

| ID | Flujo | Participantes clave | Documento |
|---|---|---|---|
| SEQ-001 | Ciclo de vida de un item de cola (`adapter/`) | `worker._process_item`, `normatividad_client`, `ocr_core_client` | `SEQ-001-ciclo-vida-item-cola.md` |

> Este único flujo cubre el camino crítico real del adapter. El indexador de búsqueda (`search/`) es un proceso batch simple (lee JSONL, escribe en OpenSearch) que no justifica un diagrama de secuencia propio.
