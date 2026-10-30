# Documentación del proyecto

> Índice vivo de la documentación. Actualizar junto con los artefactos del proyecto.

## Estado general

- Proyecto: ocr-normatividad-integrador (antes `normatividad-services`)
- Versión: 0.1.0 (sin tags de versión)
- En producción: sí, contra la cola real de Normatividad desde el 2026-10-29
- Perfil: generic
- Tipo: utility_component (no es solución independiente — complementa el proceso OCR de Normatividad)
- Hito/etapa: development (sin `gorehco_hito` formal; perfil `generic`)

| Familia | Estado | Observación |
|---|---|---|
| Proyecto | OK | Ficha del componente completa. |
| Manuales | OK | Instalación/configuración completa. |
| Documentación técnica | PARCIAL | Ficha técnica, arquitectura y reglas de negocio completas; seguridad es gap real y **urgente** (`data.personal_data: true`). |
| Pruebas y validaciones | PARCIAL | Pruebas unitarias (`adapter/tests/`) y verificación real contra producción; sin plan de pruebas formal. |
| Documentación administrativa | PARCIAL | Licenciamiento con expediente completo (sin conflicto, en espera de `ocr-core`); titularidad preliminar; opera en producción desde el 2026-10-29, sin acta formal de puesta en producción. |

## Artefactos y exigibilidad (utility_component)

| Artefacto | Ruta | Estado | Observación |
|---|---|---|---|
| Índice | `docs/README.md` | OK | — |
| Ficha del componente | `proyecto/ficha-proyecto.md` | OK | — |
| Ficha técnica del componente | `documentacion-tecnica/ficha-tecnica-componente.md` | OK | — |
| Arquitectura | `documentacion-tecnica/arquitectura/arquitectura.md` | OK | — |
| Reglas de negocio | `documentacion-tecnica/reglas-negocio.md` | OK | RN-001 a RN-011, trazables contra código real. |
| Registro de decisiones | `documentacion-tecnica/decisiones/` | OK | El porqué de las reglas y del diseño; índice en su `README.md`. |
| Diagrama de secuencia | `documentacion-tecnica/diseno/secuencias/` | OK | No exigible para `utility_component`; adoptado igual (SEQ-001, extrapolado de `adapter/app/worker.py`). |
| Seguridad | `documentacion-tecnica/seguridad/seguridad.md` | GAP REAL — URGENTE | `personal_data: true` con evidencia real; sin tratamiento formal aún. |
| Instalación/configuración | `manuales/instalacion-configuracion.md` | OK | — |
| Verificación del componente | `pruebas-validaciones/verificacion-componente.md` | OK | Operación real contra producción y pruebas unitarias. |
| Contratos | `contracts/` | OK | Con Normatividad: `normatividad-ocr-reproceso` y `normatividad-ocr-markdown`. Con el core: `ocr-core-http`. API propia: `search-api`. |
| Licenciamiento | `licenciamiento/` | EN PROGRESO | Sin conflicto propio; determinación en espera de `ocr-core`. |
| Titularidad | `documentacion-administrativa/titularidad/titularidad.md` | PARCIAL | Preliminar; sin designación institucional formal. |

## Bloqueantes

- Seguridad de datos personales: hallazgo real de datos personales expuestos en resultados de búsqueda, sin tratamiento formal definido — más urgente que el licenciamiento en este repositorio.

## No verificables

- Ninguno identificado por ahora.
