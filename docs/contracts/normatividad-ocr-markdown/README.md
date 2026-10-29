# Contrato Normatividad OCR: artefacto Markdown (`md`)

Instrucciones para que Normatividad (`munis`) solicite, reciba y registre el
artefacto Markdown que produce `ocr-core` desde la versión `0.5.0`.
`fixtures.json` congela los ejemplos de este documento; debe existir con la
misma huella SHA-256 en `munis` y en `ocr-normatividad-integrador`, igual que
`normatividad-ocr-reproceso`.

## 1. Qué es y qué no cambia

- `md` es un tercer artefacto OCR, junto a `pdf` (PDF buscable) y `text`
  (JSONL). Es una versión **estructurada y legible** del documento: un bloque
  de encabezado técnico, una sección por página, párrafos y tablas con
  cuadrícula visible. Su esquema es `ocr.markdown.document.v1`.
- Está en **beta**. El JSONL sigue siendo el texto canónico completo y el que
  consume el buscador; el Markdown es una vista derivada.
- Es **opcional y aditivo**: solo se genera si la cola lo pide. Los items que
  no piden `md` se procesan exactamente como hoy.
- El integrador ya está desplegado con soporte de `md`, y el core `0.5.0` lo
  anuncia en `/meta`. No hay ningún interruptor que activar: lo decide
  Normatividad al encolar.

## 2. Cambios que debe implementar Normatividad

### 2.1. Persistencia

Por cada archivo OCR vigente (`regulation_file_ocrs`) hace falta guardar, igual
que hoy para PDF y texto:

- si el Markdown está disponible (equivalente a `has_pdf`/`has_text`);
- su ruta relativa en el disco `ocr_cache` (`PATH_DESTINO_OCR`).

Los nombres de columnas los decide Normatividad; el integrador solo lee el
indicador `has_md` en el payload (sección 2.3).

### 2.2. Encolado (`RegulationFileOcrManager::enqueue()`)

- Aceptar `md` entre los artefactos que se pueden solicitar y guardarlo en
  `requested_artifacts_json` como `{"pdf": …, "text": …, "md": true}`.
- `resolveMissingArtifacts` debe considerar `md` como faltante cuando no esté
  disponible, igual que `pdf` y `text`.
- Al fusionar con un item activo (`resolveActiveQueueContext`), unir también
  `md`.
- En reprocesos con `execution_request`, `requested_artifacts.md` y
  `reprocess_artifacts.md` ya existen en el contrato
  `normatividad-ocr-reproceso`; solo hay que llenarlos.

### 2.3. Payload que recibe el worker (`pull-next` y `processing`)

Cuando un item pide `md`, el payload debe traer:

| Campo | Obligatorio | Descripción |
|---|---|---|
| `artifacts.requested.md` | sí | `true` |
| `artifacts.expected.md_path` | **sí** | Ruta **relativa** al disco `ocr_cache`, con el mismo patrón que los otros artefactos: misma carpeta y mismo nombre base (MD5), extensión `.md`. Ejemplo: `2026/116343/df20df76c1e9579aa376c92955a05525.md` |
| `has_md` | recomendado | `true` si ya existe un Markdown vigente; en el mismo lugar donde hoy se envían `has_pdf`/`has_text` |

Reglas de la ruta: no puede ser absoluta ni salir del disco `ocr_cache`
(`..`). Si un item pide `md` sin `md_path`, el worker lo reporta como **fallido**
con el mensaje `La cola solicita MD pero artifacts.expected.md_path no fue
provisto`.

### 2.4. Callback `POST /api/ocr/normatividad/queue/{id}/artifacts`

El cuerpo trae `md` dentro de `artifacts`, con la misma forma que `pdf` y
`text`:

- `true`: el Markdown está disponible en `md_path`;
- o un descriptor `{"available": true, "origin": "generated", "written": …}`
  cuando el item trae `execution_request`. `written: false` significa que se
  sirvió el Markdown ya vigente: Normatividad conserva la versión activa en
  lugar de registrar otra (misma regla que hoy para `pdf` y `text`).

Normatividad debe:

1. aceptar la clave `md` (hoy probablemente la rechaza o la ignora);
2. verificar que el archivo exista en `ocr_cache` en `md_path`, como ya hace con
   el JSONL;
3. registrar la ruta y marcar el Markdown como disponible.

`finalize_queue` llega en `false` si algún artefacto pedido no quedó
disponible, por ejemplo si el core no escribió el Markdown. En ese caso el
item no debe cerrarse como exitoso.

`response_payload_json` incluye ahora `produced_artifacts.md`,
`reprocessed_artifacts.md` y `storage.resolved_md_path`, útiles para auditoría.

### 2.5. Mostrar o descargar el Markdown (opcional)

Si Normatividad expone el archivo a usuarios: es texto UTF-8 con saltos de
línea LF; el tipo de contenido es `text/markdown; charset=utf-8`. No contiene
HTML ejecutable: las tablas son tablas Markdown estándar (GFM).

## 3. Título dentro del Markdown

La primera línea del cuerpo es `# título`. Hoy el título es el `file_name` del
archivo (`queue.regulation_file.file_name`, sin extensión), por ejemplo
`# 212000003462026`.

Está planificado (ocr-core `0.5.1`) que Normatividad envíe el título ya
compuesto con su propia lógica —título de la norma, tomo, adenda u otros datos,
separados por guion— y que el integrador lo reenvíe al core. El campo previsto
es `document.markdown_title`; **no es obligatorio todavía** y se confirmará al
implementar esa versión. El nombre del archivo `.md` no depende del título.

## 4. Comportamiento del worker (para referencia)

| Situación | Resultado |
|---|---|
| El item no pide `md` | Igual que hoy |
| Pide `md` con `md_path` y no hay Markdown vigente | El core lo genera; callback con `md` |
| Pide `md` y `has_md` es `true` con archivo existente | No se vuelve a generar; callback con `md` |
| `reprocess_artifacts.md` en `true` | Se regenera y sobrescribe el archivo |
| Documento con texto nativo que pide `md` | Se genera desde el texto nativo; no se omite |
| Pide `md` sin `md_path` | Item fallido con mensaje explícito |
| El core activo no anuncia `md` (rollback a `0.4.0`) | El worker se detiene **antes** de marcar el item; queda pendiente |
| El core no escribe el Markdown | Callback sin `md` y `finalize_queue: false` |

## 5. Pruebas en Normatividad

1. Encolar un archivo conocido con `md` (por ejemplo con `artisan tinker` y
   `force=true`, como en las pruebas actuales), con `pdf`, `text` y `md`.
2. Comprobar en `regulation_file_ocr_queues.response_payload_json` que
   `produced_artifacts.md` sea `true` y que `storage.resolved_md_path`
   corresponda a la ruta esperada.
3. Verificar que el archivo exista en `ocr_cache` y que su primera parte sea el
   encabezado `schema: "ocr.markdown.document.v1"`.
4. Comprobar que Normatividad registró el Markdown como disponible.
5. Encolar de nuevo el mismo archivo pidiendo solo `md` sin forzar: debe
   resolverse sin regenerarlo (`has_md` en `true`).
6. Encolar un item que no pida `md` y confirmar que nada cambia respecto de hoy.

## 6. Lista de aceptación

- [ ] Persistencia de disponibilidad y ruta del Markdown.
- [ ] `enqueue()` acepta, calcula como faltante y fusiona `md`.
- [ ] Payload con `artifacts.requested.md`, `artifacts.expected.md_path` y
      `has_md`.
- [ ] `/artifacts` acepta `md`, verifica el archivo y lo registra.
- [ ] Un item con `finalize_queue: false` no se cierra como exitoso.
- [ ] Pruebas de la sección 5 aprobadas en un entorno de prueba.
- [ ] Copia de `fixtures.json` con la misma huella SHA-256 en `munis`.
