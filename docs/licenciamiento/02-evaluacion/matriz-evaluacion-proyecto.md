# Matriz de evaluación de licencias candidatas — normatividad-services

> Contraparte legible de `matriz-evaluacion-proyecto.yml` (fuente de verdad). Estado: **final** (evaluación cerrada). Régimen: **sin determinar** (decisión deliberadamente pendiente, no bloqueada por conflicto técnico).

## Requisitos del proyecto

### Obligatorios
- Ser compatible con las licencias de sus dependencias directas (todas permisivas: MIT/BSD-3/Apache-2.0, ver [matriz-dependencias.yml](../01-dependencias/matriz-dependencias.yml)).
- No exponer ni comprometer los datos personales que pueden aparecer en los documentos indexados (`data.personal_data: true` en `proyecto.yml`).

### Deseables
- Mantener consistencia con la licencia determinada para `ocr-core` (**AGPL-3.0-only, `free_open`, 2026-09-08**), dado que ambos repos forman parte de la misma cadena de valor.

## Evaluación

| Criterio | A: MIT | B: Apache-2.0 | C: Privada institucional |
|---|---|---|---|
| Ajuste técnico | Favorable | Favorable | Favorable |
| Ajuste funcional | Favorable | Favorable | Condicional |
| Compatibilidad con dependencias | Compatible | Compatible | Compatible |
| Ajuste SPP | Favorable | Favorable | No aplica |
| **Conclusión** | Apta | Apta | Apta con condiciones |

## Recomendación

- **Régimen seleccionado:** ninguno todavía — decisión deliberadamente pendiente.
- **Justificación:** sin dependencias con copyleft, la decisión aquí es de bajo riesgo técnico. Al ser un `utility_component` sin vocación de reutilización externa, "privada institucional" sigue siendo razonable por defecto, o alinear con `ocr-core` si se prefiere consistencia de la cadena de valor completa. No hay urgencia técnica que fuerce cerrar esta decisión ahora.
- **Cuestión sin resolver:** decisión propia de régimen aún no tomada — depende de una preferencia de consistencia con `ocr-core`, no de un conflicto técnico real.
