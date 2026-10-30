# Ficha técnica del componente utilitario

- Nombre: ocr-normatividad-integrador (antes `normatividad-services`)
- Versión: 0.1.0 (ver `../proyecto.yml`)
- Descripción/finalidad: Componente que conecta la cola OCR de Normatividad con `ocr-core`: consume trabajo de la cola, lo manda a procesar vía HTTP, reporta el resultado, e indexa los artefactos para búsqueda.
- Lenguaje y versión: Python 3.12
- Entorno de ejecución: Docker (2 imágenes: `adapter/`, `search/`) + OpenSearch 2.15
- Dependencias: `adapter/requirements.txt` (solo `requests`), `search/requirements.txt` (`fastapi`, `uvicorn`, `pydantic`, `opensearch-py`) — ver [matriz-dependencias.md](../licenciamiento/01-dependencias/matriz-dependencias.md)
- Instrucciones de uso/ejecución/integración: ver [instalacion-configuracion.md](../manuales/instalacion-configuracion.md) (instalación, configuración, comandos de operación) y [arquitectura.md](arquitectura/arquitectura.md) (flujo completo de integración con Normatividad y `ocr-core`)
- Responsable/mantenedor: TODO — sin designación institucional formal registrada (ver `../proyecto.yml`, `project.responsible_unit`/`technical_owner`)
- Diccionario de datos: NO_APLICA — este componente no administra un modelo de datos propio; `adapter/` es cliente HTTP puro, `search/` mantiene un índice de OpenSearch (documentos de página, no relacional). El modelo de datos real del que depende (colas y estados de Normatividad) es externo — ver `../../context.md`, sección "Modelo de datos de la cola", pendiente de formalizarse como diagrama de referencia.
