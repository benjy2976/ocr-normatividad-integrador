# Ficha del componente

- Nombre: normatividad-services
- Versión: 0.1.0 (ver `../proyecto.yml`)
- Descripción/finalidad: Componente que conecta la cola OCR de Normatividad con `ocr-core`: consume trabajo de la cola, lo manda a procesar vía HTTP, reporta el resultado, e indexa los artefactos para búsqueda. **No es una solución independiente** — apoya y complementa el proceso de digitalización de normas de Normatividad. Sin Normatividad no tiene ningún propósito propio.
- Responsable/mantenedor: TODO — sin designación institucional formal registrada (ver `../proyecto.yml`, `project.responsible_unit`/`technical_owner`).
- Modalidad de desarrollo: internal — desarrollado directamente sobre infraestructura de GORE Huánuco.
