# Matriz de evaluación de licencias candidatas — normatividad-services

> Contraparte legible de `matriz-evaluacion-proyecto.yml` (fuente de verdad). Estado: `draft`.

## Requisitos del proyecto

### Obligatorios
- Ser compatible con las licencias de sus dependencias directas (todas permisivas: MIT/BSD-3/Apache-2.0, ver [matriz-dependencias.yml](../01-dependencias/matriz-dependencias.yml)).
- No exponer ni comprometer los datos personales que pueden aparecer en los documentos indexados (`data.personal_data: true` en `proyecto.yml`).

### Deseables
- Mantener consistencia con la licencia que finalmente se determine para `ocr-core`, dado que ambos repos forman parte de la misma cadena de valor.

### Preguntas para revisión legal
- ¿Una eventual publicación del código fuente de este repo (sin datos, solo código) tendría alguna restricción dado que procesa/indexa documentos con datos personales, aunque esos datos no viven en el repositorio de código?

## Evaluación

| Criterio | Requisito del proyecto | A: MIT | B: Apache-2.0 | C: Privada institucional |
|---|---|---|---|---|
| Modificación | — | Sí | Sí | Restringida |
| Redistribución | — | Sí | Sí | No, uso interno |
| Preservar avisos/licencia | — | Sí | Sí + NOTICE | No aplica |
| Copyleft | — | No | No | No |
| Uso en red / SaaS | — | Sin restricción | Sin restricción | Sin restricción (uso interno) |
| Integración con software propietario | — | Sí, cualquiera | Sí, cualquiera | Sí |
| Compatibilidad con dependencias | **Obligatorio** | Compatible | Compatible | Compatible |
| Revisión legal | — | Pendiente (bajo riesgo) | Pendiente (bajo riesgo) | Pendiente (bajo riesgo) |
| Resultado | | **suitable** | **suitable** | **suitable_with_conditions** |

## Recomendación técnica

- **Licencia recomendada (interina, no es determinación):** Privada institucional, o alinear con la licencia final de `ocr-core` si se opta por Apache-2.0/MIT.
- **Justificación:** sin dependencias con copyleft, la decisión aquí es de bajo riesgo técnico. Al ser un `utility_component` sin vocación de reutilización externa (no es solución independiente, solo complementa Munis), mantenerlo privado institucional es razonable — salvo que se prefiera consistencia con la licencia de `ocr-core` por ser parte de la misma cadena de valor.
- **Riesgos/condiciones:** ninguno técnico; depende de la decisión final de `ocr-core`.
- **Puntos que requieren revisión legal:** ninguno urgente (`requires_legal_review: false`), a diferencia de `ocr-core`.
