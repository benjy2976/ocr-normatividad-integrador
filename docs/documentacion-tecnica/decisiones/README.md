# Registro de decisiones

Cada archivo registra una decisión de este repo que alguien podría cuestionar
más adelante: qué se decidió, por qué, qué alternativas se descartaron y qué
consecuencias tiene. Las reglas de negocio vigentes están en
`../reglas-negocio.md`; aquí se registra el porqué de las que nacieron de una
decisión. Las decisiones de Walther Aguirre, responsable del proyecto, no las
reabre un agente por su cuenta.

## Reglas

- Un archivo por decisión: `NNNN-<slug>.md`, numerado en orden de registro.
- **No se editan** salvo para corregir erratas o cambiar el estado. Si el
  criterio cambia, se registra una decisión nueva y la anterior pasa a
  `reemplazada por NNNN`.
- **Estados:**
  - `vigente`: rige y el sistema ya la cumple;
  - `aceptada, sin implementar`: está decidida, pero el sistema **todavía no**
    la cumple. Lleva al principio un aviso con lo que hace hoy el sistema y
    remite a su iniciativa. Cuando se implementa, pasa a `vigente`;
  - `reemplazada por NNNN`;
  - `retirada`.
- La evidencia se cita por commit, prueba, contrato o documento vigente, nunca
  por un plan de trabajo.

## Formato

```markdown
# NNNN. <decisión en una frase>

- **Estado:** vigente
- **Fecha:** AAAA-MM-DD
- **Decidió:** <nombre>

## Contexto
## Decisión
## Alternativas descartadas
## Consecuencias
## Evidencia
```

## Índice

| # | Decisión | Estado | Fecha |
|---|---|---|---|
| [0001](0001-markdown-sin-interruptor.md) | El Markdown se atiende cuando la cola lo pide, sin interruptor | vigente | 2026-10-29 |
| [0002](0002-titulo-compuesto-por-normatividad.md) | El título del Markdown lo compone Normatividad | vigente | 2026-10-29 |
| [0003](0003-integrador-escribe-los-artefactos.md) | El integrador subirá el PDF y escribirá los artefactos en el NFS | aceptada, sin implementar | 2026-10-29 |
