# Contrato de la API de búsqueda (`search/`)

`ocr-search-api` expone la búsqueda documental sobre el índice OpenSearch que
alimenta `ocr-search-indexer` a partir de los JSONL del OCR. Este documento
describe `search/app/search_api.py` tal como funciona hoy. El índice es,
deliberadamente, específico de Normatividad (RN-006).

> **Datos personales.** Los resultados devuelven texto de documentos reales,
> que puede incluir datos personales. La API no tiene autenticación propia; el
> tratamiento formal es un gap abierto
> (`../../documentacion-tecnica/seguridad/seguridad.md`).

- **Servicio:** `ocr-search-api`, publicado en el host en el puerto `18020`.
- **Índice:** `OPENSEARCH_INDEX` (por defecto `munis_ocr_pages`), con un
  documento por página.

## `GET /health`

```json
{"status": "ok", "opensearch": true, "index": "munis_ocr_pages"}
```

## `GET /search`

### Parámetros

| Parámetro | Tipo y límites | Efecto |
|---|---|---|
| `q` | texto | Busca con `operator: and` en `text` (peso 4), `reg_title` (3), `reg_description` (2) y `file_name`. Sin `q`, la respuesta lista documentos (`mode: "list"`) |
| `page`, `per_page` | `page ≥ 1`, `1 ≤ per_page ≤ 100` | Paginación por página. `page` tiene prioridad sobre `offset` |
| `limit`, `offset` | `1 ≤ limit ≤ 100`, `offset ≥ 0` | Paginación por desplazamiento. El tamaño de página es `per_page`, si no `limit`, si no 10 |
| `sort` o `sort_by` | ver "Orden" | Por defecto, `-score` si hay `q` y `-reg_date` si no |
| `regulation_file_id`, `regulation_id`, `year`, `tipo`, `regulation_type_id`, `sigla_id`, `regulation_type_sigla_id` | enteros | Filtros exactos. `year` filtra `reg_year`, `tipo` filtra `regulations_tipo`, y `sigla_id` es un alias de `regulation_type_sigla_id` |
| `group_by` | `regulation` (por defecto), `file`, `page`, `document` | Agrupa los resultados. `document` equivale a `file` |
| `matched_files_limit` | 1 a 50 (por defecto 10) | Con `group_by=regulation`, cuántos archivos coincidentes por norma |
| `matched_pages_limit` | 1 a 20 (por defecto 5) | Cuántas páginas coincidentes por archivo |
| `highlight_fragment_size` | 80 a 500 (por defecto 180) | Tamaño de cada fragmento resaltado de `text` |
| `highlight_fragments` | 1 a 5 (por defecto 3) | Cantidad de fragmentos |

### Orden

Valores aceptados: `-score`, `score`, `-reg_date`, `reg_date`, `-reg_year`,
`reg_year`, `-reg_num` y `reg_num` (el `-` indica descendente). Alias:
`relevance` y `score_desc` (`-score`), `date` y `date_desc` (`-reg_date`),
`date_asc`, `year_desc`, `year_asc`, `num_desc` y `num_asc`. Cualquier otro
valor responde `422`. Los desempates son, en orden: puntaje, `reg_date`,
`regulation_id`, `regulation_file_id` y `page`.

### Respuesta

```json
{
  "mode": "search",
  "query": "liquidacion",
  "group_by": "regulation",
  "sort": "-score",
  "highlight_fragment_size": 180,
  "highlight_fragments": 3,
  "total": 12,
  "total_page_matches": 57,
  "limit": 10, "offset": 0, "per_page": 10,
  "current_page": 1, "last_page": 2,
  "from": 1, "to": 10, "next_page": 2, "prev_page": null,
  "pagination": {"total": 12, "per_page": 10, "current_page": 1, "last_page": 2,
                 "from": 1, "to": 10, "next_page": 2, "prev_page": null},
  "results": ["..."]
}
```

- `total` cuenta normas distintas con `group_by=regulation`, archivos
  distintos con `file`, y páginas con `page`. `total_page_matches` siempre
  cuenta páginas.
- **Cada resultado** trae `regulation_file_id`, `regulation_id`,
  `source_md5`, `page`, `page_count`, `text_path`, `pdf_path`, `source_path`,
  `file_name`, `reg_num`, `reg_year`, `reg_date`, `reg_title`,
  `reg_description`, `regulations_tipo`, `regulations_tipos_sigla_id`,
  `regulation_type_id`, `regulation_type_sigla_id`, `text_source_kind`,
  `score` y `highlight`.
- Con `group_by=regulation`, se agrega `matched_files`: una lista de archivos
  (`regulation_file_id`, `file_name`, `pdf_path`, `text_path`, `source_path`,
  `score`), cada uno con hasta `matched_pages_limit` elementos en
  `matched_pages` (`page`, `char_count`, `word_count`, `score`, `highlight`).
- Con `group_by=file`, se agrega `matched_pages` directamente.
- `highlight` usa `<mark>` y `</mark>`. Con `q`, también resalta `reg_title` y
  `reg_description`.

### Ejemplo

```bash
curl 'http://localhost:18020/search?q=liquidacion&year=2021&group_by=file&per_page=5'
```
