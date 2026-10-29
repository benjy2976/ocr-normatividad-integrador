# 0002. El título del Markdown lo compone Normatividad

- **Estado:** vigente
- **Fecha:** 2026-10-29
- **Decidió:** Walther Aguirre

## Contexto

Desde 0.5.1, `ocr-core` acepta `options.document_title` para la línea
`# título` del Markdown. El core es genérico y no debe interpretar datos de
Normatividad. Antes de eso, el título salía del nombre del PDF temporal, y una
corrección provisional usó el `file_name` del documento.

## Decisión

- El título lo compone Normatividad con su propia lógica (título de la norma,
  tomo, adenda u otros datos) y lo envía en `document.markdown_title`. Es un
  campo definido por este proyecto en el contrato `normatividad-ocr-markdown`.
- El integrador lo reenvía como `options.document_title`, solo en los trabajos
  que piden `md`: en una sola línea y recortado a 500 caracteres.
- Si no llega, el integrador compone un fallback con datos que el payload ya
  trae: `{id de la norma} - {id del archivo} - {reg_title}`, omitiendo las
  partes vacías. No se le piden más datos a Normatividad.
- El PDF temporal usa un nombre técnico (`normatividad_{queue_id}_{token}.pdf`),
  porque el título viaja explícito.

## Alternativas descartadas

- **Que el core derive el título de datos de Normatividad:** acoplaría el core
  a un dominio.
- **Pedir a Normatividad campos adicionales para el fallback:** agrega trabajo
  externo sin necesidad.
- **Usar el `file_name` como título:** era una corrección provisional; un nombre
  de archivo rara vez es un buen título.

## Consecuencias

- Los trabajos sin `md` no envían título.
- Regla vigente: RN-011 de `../reglas-negocio.md`.

## Evidencia

- Commits `3f1c2c7` (corrección provisional) y `dddf723`.
- `adapter/tests/test_worker_markdown.py` (pruebas de título y fallback).
- `docs/contracts/normatividad-ocr-markdown/README.md`, sección 3.
