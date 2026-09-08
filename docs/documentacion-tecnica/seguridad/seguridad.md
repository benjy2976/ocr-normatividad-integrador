# Seguridad

> **Prioritario en este repo**, a diferencia de `ocr-core`: `docs/proyecto.yml` registra `data.personal_data: true`, con evidencia real (una prueba de búsqueda devolvió un documento con nombre y circunstancia personal de una persona — permiso por lactancia materna). Los documentos de Normatividad pueden contener datos personales.

## Estado conocido

- Sin documento formal de seguridad ni de protección de datos previo a este registro.
- El índice de OpenSearch (`search/`) persiste texto extraído de documentos, incluyendo posibles datos personales incidentales al contenido de la norma/expediente.
- Autenticación entre `adapter/` y Normatividad: token Bearer (`NORMATIVIDAD_OCR_TOKEN`) — ver [instalacion-configuracion.md](../../manuales/instalacion-configuracion.md).
- Sin control de acceso propio en la API de búsqueda (`search/` expone `GET /search` sin autenticación adicional documentada).

## Pendiente (urgente)

- Evaluar si el índice de OpenSearch requiere control de acceso adicional dado el hallazgo de datos personales.
- Definir tratamiento (anonimización, restricción de acceso, retención) para resultados de búsqueda que expongan datos personales incidentales.
- Formalizar esta sección en línea con la Directiva N°02.S5.DI.SGMTD y cualquier normativa de protección de datos personales aplicable a GORE Huánuco.
