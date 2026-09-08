# Informe técnico de determinación de licencia — normatividad-services

> **Estado:** FINAL (análisis) — **determinación:** PENDIENTE (por elección, no por bloqueo)
> **Proyecto:** normatividad-services
> **Versión evaluada:** 0.1.0
> **Fecha:** 2026-09-08
> **Responsable técnico/equipo:** Walther Aguirre Tello

## 1. Base documental

- Matriz/catálogo comparativo considerado: [catalogo-referencia.md](../02-evaluacion/catalogo-referencia.md) → `modelo-matriz-comparativa-sgd.md`.
- Matriz de dependencias: [../01-dependencias/matriz-dependencias.yml](../01-dependencias/matriz-dependencias.yml).
- Matriz de evaluación: [../02-evaluacion/matriz-evaluacion-proyecto.yml](../02-evaluacion/matriz-evaluacion-proyecto.yml).
- Referencia externa relevante: determinación de `ocr-core` — `free_open`, `AGPL-3.0-only`, decidida 2026-09-08.

## 2. Antecedentes y contexto

`normatividad-services` es un `utility_component` (no una solución independiente): consume la cola OCR de Normatividad, orquesta llamadas HTTP a `ocr-core`, e indexa resultados en OpenSearch. Sus 5 dependencias directas son todas permisivas (MIT/BSD-3/Apache-2.0), sin ningún componente con copyleft.

## 3. Objetivo

Documentar el análisis técnico de licenciamiento de este componente y dejar constancia explícita de que su determinación queda pendiente por decisión, no por conflicto técnico.

## 4. Análisis de alternativas

Se evaluaron tres alternativas (detalle en la matriz de evaluación): MIT, Apache-2.0, y licencia privada institucional. Las tres resultan aptas — ninguna descartada por incompatibilidad.

## 5. Compatibilidad con dependencias

- Estado de la matriz: `final`, salud `ok` — 5 componentes, 0 incompatibles.
- Dependencias condicionantes: ninguna.
- Incompatibilidades detectadas: ninguna.
- Licencias desconocidas/requieren revisión: ninguna.

## 6. Consideraciones técnicas, funcionales y legales

### 6.1 Técnicas
Sin conflicto técnico: cualquiera de las tres candidatas es viable sin refactor.

### 6.2 Funcionales / de distribución
Corre exclusivamente dentro de la infraestructura de GORE Huánuco, sin distribución externa. Al ser `utility_component` sin vocación de reutilización por terceros, un régimen privado sigue siendo razonable por defecto.

### 6.3 Consideraciones legales identificadas
Ninguna urgente por licenciamiento de software. El hallazgo sensible de este repositorio es de **datos personales** (`data.personal_data: true`, evidencia real de exposición en resultados de búsqueda) — tratado en `docs/documentacion-tecnica/seguridad/seguridad.md`, no aquí.

## 7. Determinación técnica

- **Régimen seleccionado:** ninguno todavía.
- **Licencia seleccionada:** no aplica por ahora.
- **Motivo de la no-determinación:** decisión de bajo riesgo, deliberadamente diferida — no hay conflicto técnico que la fuerce. Puede resolverse alineando con `ocr-core` (ya determinado como `free_open`/AGPL-3.0-only) o manteniendo un régimen privado institucional por defecto, dado que este componente no tiene vocación de reutilización externa.

## 8. Conclusiones

Sin conflicto de licenciamiento propio. La determinación de este repositorio sigue abierta por elección — a diferencia de `ocr-core`, no hay urgencia técnica ni legal que la fuerce.

## 9. Recomendaciones para implementación

- No aplica todavía — pendiente de que se tome la decisión de régimen.
- Cuando se decida, re-ejecutar `sync_dependencies.py` para confirmar que la matriz sigue reflejando el estado real de las dependencias.
