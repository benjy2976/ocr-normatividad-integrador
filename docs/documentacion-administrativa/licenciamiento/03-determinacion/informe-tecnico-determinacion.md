# Informe técnico para la determinación del modelo y licencia aplicable

> **Estado:** BORRADOR
> **Proyecto:** normatividad-services
> **Versión evaluada:** 0.1.0
> **Fecha:** 2026-09-07
> **Responsable técnico:** Walther Aguirre Tello

## 1. Base legal y documental

- Directiva/lineamientos aplicables: Directiva N°02.S5.DI.SGMTD–V1.0 (perfil `generic`).
- Matriz comparativa de referencia utilizada: [catalogo-referencia.md](../02-evaluacion/catalogo-referencia.md) → `modelo-matriz-comparativa-sgd.md` (modelo interno del SGD, **no** el Anexo N.° 05 oficial).
- Matriz de dependencias: [matriz-dependencias.yml](../01-dependencias/matriz-dependencias.yml) (estado: `draft`).
- Matriz de evaluación del proyecto: [matriz-evaluacion-proyecto.yml](../02-evaluacion/matriz-evaluacion-proyecto.yml) / [.md](../02-evaluacion/matriz-evaluacion-proyecto.md) (estado: `draft`).
- Evidencia de titularidad/derechos: no reunida.
- Revisión legal, si ya existe: no existe.

## 2. Antecedentes

`normatividad-services` es un `utility_component` (reclasificado 2026-09-08): no es una solución independiente, sino el adaptador que consume la cola OCR de Munis y orquesta llamadas a `ocr-core`, más el módulo de búsqueda sobre resultados indexados en OpenSearch. Sus 5 dependencias directas (`requests`, `fastapi`, `uvicorn`, `pydantic`, `opensearch-py`) son todas permisivas (MIT/BSD-3/Apache-2.0), sin ningún componente con copyleft.

## 3. Objetivo del informe

Dejar constancia de que, a diferencia de `ocr-core`, este repositorio **no presenta un conflicto de licenciamiento propio** que requiera resolución técnica o legal urgente, y que su determinación final está deliberadamente subordinada a la de `ocr-core`.

## 4. Marco conceptual

Ver [informe-tecnico-determinacion.md de ocr-core](../../../../ocr-core/docs/documentacion-administrativa/licenciamiento/03-determinacion/informe-tecnico-determinacion.md) — mismos conceptos, no se repiten aquí.

## 5. Análisis y selección de licencia

### 5.1 Alternativas evaluadas

MIT, Apache-2.0 y privada institucional (ver matriz de evaluación referenciada). Las tres resultan `suitable` o `suitable_with_conditions`, sin ninguna marcada `not_suitable`.

### 5.2 Compatibilidad con dependencias

- Estado de la matriz de dependencias: `draft`, 5 componentes, todos permisivos.
- Conflictos o condicionantes: ninguno.
- Elementos que requieren revisión legal: ninguno urgente por licenciamiento de dependencias. El punto sensible del repositorio es de **datos personales** (`data.personal_data: true`), no de licencias de software — corresponde a la fase de seguridad, no a esta.

### 5.3 Recomendación técnica

- **Régimen recomendado:** privada institucional (por defecto, dado que es `utility_component` sin vocación de reutilización externa), o alineado con lo que se determine para `ocr-core`.
- **Licencia recomendada (SPDX):** no aplica de forma estricta si se opta por régimen privado; si se prefiere alinear con `ocr-core`, dependerá de lo que allí se determine.
- **Motivos:** sin conflicto técnico propio; la decisión relevante ya se está resolviendo en `ocr-core`.
- **Condiciones:** esta recomendación **queda en espera** de la determinación de `ocr-core` (ver `decision-institucional.md` de ese repositorio). No se recomienda cerrar esta antes que aquella.

> Este apartado expresa una **recomendación técnica**, no la decisión institucional definitiva.

## 6. Justificación técnica e institucional

Al no ser solución independiente, la coherencia con `ocr-core` pesa más que cualquier otro criterio: ambos repos forman una única cadena de valor operativa (Munis → normatividad-services → ocr-core). No tiene sentido institucional fijar la licencia de este repo antes que la del motor del que depende funcionalmente.

## 7. Alcance del informe

Cubre solo la situación de licenciamiento de dependencias de software de este repositorio. **No cubre** el tratamiento de los datos personales que puedan aparecer en los documentos indexados — eso pertenece a la fase de seguridad/datos, ya marcada como urgente en `proyecto.yml` (`data.personal_data: true`).

## 8. Conclusiones

Sin conflicto de licenciamiento propio. La determinación formal de este repositorio queda subordinada a la de `ocr-core`.

## 9. Recomendaciones

1. No avanzar la decisión institucional de este repo hasta que exista una decisión institucional documentada para `ocr-core`.
2. Priorizar, en cambio, la documentación de seguridad de datos personales de este repositorio (más urgente aquí que el licenciamiento).

## 10. Anexos / evidencias

- Matriz comparativa de referencia: [catalogo-referencia.md](../02-evaluacion/catalogo-referencia.md)
- Matriz de evaluación del proyecto: [matriz-evaluacion-proyecto.md](../02-evaluacion/matriz-evaluacion-proyecto.md)
- Matriz de dependencias: [matriz-dependencias.md](../01-dependencias/matriz-dependencias.md)
- Texto de licencia candidata: no aplica aún
- Otros: ninguno
