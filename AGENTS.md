# AGENTS.md — normatividad-services

> Todas las rutas de este archivo son internas a este repo. No se
> referencian documentos de otros repos ni de la carpeta padre salvo
> autorización expresa del usuario.

## Qué es este repo

Conecta la cola OCR real de **Normatividad** (sistema de gestión documental
del Gobierno Regional de Huánuco — GORE Huánuco, producción en
`https://proyectos.regionhuanuco.gob.pe`, corre en Kubernetes) con el motor
OCR (`ocr-core`, consumido por HTTP, fuera de este repo). No ejecuta OCR:
sin Tesseract, OCRmyPDF, OpenCV ni modelos propios.

Dos servicios independientes, cada uno con su propio `Dockerfile`:

- **`adapter/`** — consume la cola de Normatividad, manda el trabajo a
  `ocr-core` vía HTTP, reporta el resultado. Ver
  `docs/documentacion-tecnica/arquitectura/arquitectura.md` para el flujo
  completo y `docs/documentacion-tecnica/diseno/secuencias/SEQ-001-ciclo-vida-item-cola.md`
  para la secuencia exacta que ejecuta `adapter/app/worker.py::_process_item`.
- **`search/`** — indexa los artefactos que produce `ocr-core` en
  OpenSearch y expone `GET /search`. Esquema acoplado a Normatividad
  a propósito (ver "Decisión de diseño" en `arquitectura.md`).

No es una solución independiente: sin Normatividad no tiene propósito
propio (`docs/proyecto.yml`, `project.kind: utility_component`).

## Mapa de documentación (leer según la tarea)

| Si vas a... | Leer |
|---|---|
| Entender el dominio de Normatividad (estados de cola, reglas de `enqueue()`, las dos rutas de storage que se confunden, seguridad operativa al probar contra producción real) | `context.md` |
| Tocar `adapter/app/worker.py` o cualquier decisión de negocio | `docs/documentacion-tecnica/reglas-negocio.md` (RN-001 a RN-006, trazables contra código) |
| Entender el flujo end-to-end de un item de cola | `docs/documentacion-tecnica/diseno/secuencias/SEQ-001-ciclo-vida-item-cola.md` (diagrama de secuencia) |
| Ver arquitectura general y la decisión de esquema de búsqueda | `docs/documentacion-tecnica/arquitectura/arquitectura.md` |
| Instalar, configurar o ver variables de entorno | `docs/manuales/instalacion-configuracion.md` |
| Desplegar o tocar Kubernetes | `k8s/README.md` (dependencia cruzada de PVC/namespace) |
| Evaluar riesgo de datos personales / seguridad | `docs/documentacion-tecnica/seguridad/seguridad.md` — **gap real y urgente** |
| Ver qué se validó y cómo (no hay tests automatizados) | `docs/pruebas-validaciones/verificacion-componente.md` |
| Ver metadata de gobierno del proyecto (versión, etapa, licenciamiento) | `docs/proyecto.yml` |
| Ver el índice completo con estado de cada artefacto | `docs/README.md` |

## Reglas de negocio (resumen — detalle en `reglas-negocio.md`)

- **RN-001**: sin `pdf`, `text` ni `md` solicitados → `skip` inmediato, sin
  descargar el PDF fuente.
- **RN-002**: si el PDF ya tiene texto útil y solo se pidió `pdf` → `skip`,
  no se publica artefacto nuevo. `ocr-core` no puede inferir esto — es
  decisión de negocio, no técnica.
- **RN-003**: `failed` de `ocr-core` con mensaje de firma digital detectada
  **durante** el OCR → se reclasifica como `block` ante Normatividad, no
  `fail` (no reintentar indefinidamente algo que nunca va a pasar).
- **RN-004**: artefactos ya cacheados (`has_pdf`/`has_text` + archivo
  existente) no se vuelven a pedir a `ocr-core`.
- **RN-005**: `enqueue()` en Normatividad (código externo, pero este repo
  depende de su comportamiento) — no elegible sin forzar → `skipped`; item
  activo existente → fusiona artefactos pedidos en vez de duplicar.
- **RN-006**: el esquema de búsqueda indexa campos específicos de
  Normatividad a propósito, no un `metadata` genérico.
- **RN-007**: el fan-out shadow es no autoritativo y de mejor esfuerzo; usa el
  NFS solo como entrada, escribe en el volumen privado del candidato y nunca
  altera callbacks, estados ni artefactos oficiales.
- **RN-008**: `md` (Markdown de `ocr-core`, beta) se atiende cuando la cola lo
  pide, sin interruptor; exige que `/meta` anuncie `ocr.markdown.document.v1`,
  se escribe en `artifacts.expected.md_path` y, si el core no lo escribe, la
  cola no se cierra.

## Reglas de seguridad operativa — este repo puede tocar producción real

No es un entorno de prueba: la cola real es de una entidad de gobierno
regional, con datos que pueden ser personales (ver sección siguiente).
Checklist antes de correr esto contra la cola real:

1. Confirmar que el `ocr-worker` de Kubernetes está escalado a `0/0` — si
   no, dos consumidores compiten por la misma cola.
2. Un solo item primero (`worker_main.py once`), nunca el loop continuo
   (`docker compose up`), en una primera prueba o después de un cambio.
3. `PATH_DESTINO` (de donde Normatividad sirve el PDF fuente) y
   `PATH_DESTINO_OCR`/`OCR_SHARED_CACHE_DIR` (de donde verifica que el
   artefacto ya existe) **no son la misma ruta** — confundirlas produce un
   `422` real aunque el OCR haya corrido bien. Ver `context.md`, sección
   "Dos rutas de storage que NO son lo mismo".
4. No reiniciar `ocr-core` en caliente mientras `normatividad-worker` esté
   activo contra producción real — interrumpe un job a medio reportar y
   puede chocar con `overwrite=false` en `POST /jobs`. Apagar el worker
   primero. (Incidente real documentado en `context.md`.)
5. Cualquier acción que toque la cola real (forzar reprocesamiento, cambiar
   `status`, escalar el worker de K8s) requiere confirmación explícita del
   usuario antes de ejecutar.

## Datos personales — bloqueante conocido

`docs/proyecto.yml` registra `data.personal_data: true` con evidencia real:
una búsqueda devolvió un documento con nombre y circunstancia personal de
una persona. Sin tratamiento formal definido todavía (ver
`docs/documentacion-tecnica/seguridad/seguridad.md`). Tratar cualquier
resultado de `search/` o log que contenga texto extraído como
potencialmente sensible.

## Kubernetes — dependencia cruzada de orden de despliegue

`normatividad-worker` y `ocr-search-indexer` referencian el PVC
`ocr-shared-cache` por nombre, pero ese PVC lo crea `ocr-core` (repo
externo). Ambos deben desplegarse en el mismo namespace (`ocr-service`). Si
se aplica este repo antes, los pods quedan en `Pending` — no es error, es
orden. Detalle en `k8s/README.md`.

## Gaps conocidos del repo

- Cobertura automatizada todavía parcial: RN-007 tiene pruebas unitarias; las
  reglas históricas RN-001 a RN-006 siguen respaldadas principalmente por
  operación sostenida (`docs/pruebas-validaciones/verificacion-componente.md`).
- Seguridad de datos personales sin tratamiento formal (ver arriba) —
  bloqueante más urgente que licenciamiento en este repo.
- No hay cliente para `GET /api/ocr/normatividad/queue/summary` en
  `adapter/app/normatividad_client.py` todavía (mejora de observabilidad
  pendiente, no implementada) — ver `context.md`.
- Titularidad institucional preliminar, sin designación formal
  (`docs/documentacion-administrativa/titularidad/titularidad.md`).

## Planes de trabajo y bitácoras

Política obligatoria desde el 2026-10-29. Los planes son herramientas
transitorias para llegar a un objetivo. **No son documentación** y no se
versionan.

### Dónde viven

- **Plan que afecta solo a este repo:** `planes/<AAAA-MM>-<slug>/`, dentro del
  repo e ignorado por git (`/planes/` en `.gitignore`).
- **Plan que afecta a varios repos:**
  `/home/administrador/new_ocr/planes/<AAAA-MM>-<slug>/`, fuera de todo repo.
  Es una excepción autorizada por el usuario a la regla de no referenciar rutas
  externas.
- Cada carpeta contiene `plan.md`, `bitacora.md` y, si hace falta, `anexos/`
  (ensayos, simuladores, datos de prueba).
- El respaldo y la eliminación de los planes son responsabilidad del usuario.
  Los agentes no borran planes.

### Independencia de la documentación

- **La documentación versionada nunca depende de un plan.** Ningún archivo
  versionado (documentos, código, comentarios, README, `AGENTS.md`) cita un
  plan ni la carpeta `planes/`. Un plan puede citar documentos; al revés,
  nunca.
- Un clon del repo **sin planes** debe bastar para conocer el estado del
  proyecto: qué es, cómo es hoy, por qué es así, qué se comprobó, qué cambió en
  cada versión y qué falta.
- **Un agente solo lee el plan que el usuario le pidió ejecutar o reanudar.**
  No recorre ni busca en otros planes, ni los usa como fuente de
  documentación.
- **Transición (2026-10):** algunos planes antiguos siguen versionados en
  `docs/` mientras se retiran. No se toman como documentación vigente.

### Cosecha

En cada puerta de fase y al cerrar el plan, el agente propone y el usuario
aprueba pasar lo durable a la documentación versionada:

| Qué deja el plan | Dónde va |
|---|---|
| Decisiones, con su contexto y las alternativas descartadas | Registro de decisiones del repo |
| Hechos sobre cómo es hoy el sistema | Documentos vigentes y gaps conocidos |
| Trabajo pendiente que todavía no tiene pasos | Iniciativas del repo |
| Lecciones operativas | Reglas de este `AGENTS.md` o runbooks |
| Cambios de una versión | Notas de release |

Un hecho sobre el sistema actual o una decisión nunca viven solo en un plan.

### Bitácora (`bitacora.md`)

Sirve para que cualquier agente pueda reanudar el trabajo si la sesión se
corta.

- **Estructura:** una cabecera **Estado actual**, que se reescribe en cada
  cambio (plan, fase, último paso cerrado, paso en curso, siguiente paso y lo
  que espera una decisión o autorización del usuario), y un **registro**
  cronológico al que solo se agregan entradas al final.
- **Entrada:** fecha y hora con zona, tipo, paso, agente (herramienta y
  modelo), repo o directorio, acción, resultado con evidencia breve (commit,
  imagen, `queue_id`, archivo) y cómo deshacerla.
- **Tipos:** `ACCIÓN` (sin efectos externos); `INICIO` y luego `FIN` o
  `FALLO`, alrededor de toda acción con efectos (commit, tag, Docker, `.env`,
  despliegue, cola real); `DECISIÓN` (del usuario); `REANUDA` (un agente
  retoma el plan); y `NOTA`. Un `INICIO` sin cierre indica que la acción pudo
  quedar a medias.
- **Nunca se registran** tokens, contraseñas, contenido de documentos ni datos
  personales. Se identifican por referencia (`queue_id`, hash, ruta).
- **Al reanudar:** leer el plan y su bitácora, verificar el estado real
  (`git status`/`git log`, `docker ps`, archivos) antes de seguir y, ante un
  `INICIO` sin cierre, comprobar qué pasó antes de reintentar.
- **Autorizaciones:** quedan registradas como contexto, pero no se
  transfieren. Una acción autorizada en una sesión anterior que no llegó a
  ejecutarse se vuelve a confirmar con el usuario.
- **Un solo agente a la vez por plan.**

```markdown
# Bitácora: <nombre del plan>

## Estado actual
- **Plan:** `plan.md` · **Fase:** … · **Último paso cerrado:** …
- **Paso en curso:** … · **Siguiente paso:** …
- **Espera al usuario:** … · **Actualizado:** <AAAA-MM-DD HH:MM ±zona> por <agente>

## Registro

### <AAAA-MM-DD HH:MM ±zona> · <TIPO> · paso <#>
- **Agente:** … · **Dónde:** …
- **Acción:** … · **Resultado:** … · **Deshacer:** …
```

## Control de versiones

**Ningún agente ejecuta `git commit`, `git push` ni `git tag` sin
autorización expresa del usuario para ese commit puntual.** Proponer el
mensaje de commit está siempre permitido, de oficio o a pedido, sin que eso
implique autorización para ejecutarlo. Una autorización cubre exactamente
el commit autorizado — no autoriza el siguiente, ni cubre volver a ejecutar
una versión modificada del mensaje sin mostrarla de nuevo primero.

Convención de mensajes (formalizada a partir del historial real de este
repo, no inventada):

```
<resumen en imperativo, español, ~50-72 caracteres, sin punto final>

<cuerpo opcional: qué cambió y por qué, en prosa>
```

- Sin prefijo de tipo/scope (nada de `feat:`/`fix(module):`).
- El cuerpo es obligatorio solo cuando el resumen no basta para entender el
  cambio.
- Sin trailers salvo que el usuario pida uno explícitamente para un commit
  puntual.

## Pendiente de definir juntos

- [ ] Reglas de estilo/lint específicas si se agregan tests.
