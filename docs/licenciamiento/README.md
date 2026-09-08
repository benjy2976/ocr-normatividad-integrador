# Licenciamiento técnico vivo

Este bloque no es un expediente administrativo. Su función es mantener visibles los riesgos de licenciamiento mientras el software evoluciona.

```text
docs/licenciamiento/
├── README.md
├── 01-dependencias/
│   ├── matriz-dependencias.yml
│   └── matriz-dependencias.md
├── 02-evaluacion/
│   ├── matriz-evaluacion-proyecto.yml
│   ├── matriz-evaluacion-proyecto.md
│   └── catalogo-referencia.md
└── 03-determinacion/
    └── informe-tecnico-determinacion.md
```

## Estado actual

- **Licencia determinada:** ninguna todavía — decisión deliberadamente pendiente (sin conflicto técnico que la fuerce).
- **Salud de dependencias:** `ok` (5 componentes, todos permisivos, 0 incompatibles).
- **Referencia externa:** `ocr-core` (misma cadena de valor) ya determinó `free_open`/AGPL-3.0-only el 2026-09-08.

Cuando cambie una dependencia, sincronizar la matriz (`sync_dependencies.py`, ejecutado por separado en `adapter/` y `search/` — el escáner no es recursivo), identificar la licencia, ejecutar cribado de compatibilidad (`check_license_compatibility.py`).

No se crean por defecto archivos separados de revisión legal, decisión institucional o verificación administrativa.
