# ADR-0004: Pipeline layout amendments

- **Status:** Accepted
- **Date:** 2026-10-26
- **Related decisions:** 02 (Pipeline Isolation), 03 (Shared Infrastructure),
  04 (Configuration first), 07 (Pipeline Flow), 14 (Extensibility)

## Context

Before the first pipeline is written, the layout needs one consistent
shape that every pipeline repeats.

## Decision

1. Every pipeline has the same package layout:

   ```
   agpp/pipelines/<name>/
   ├── __init__.py
   ├── config.py          # Pydantic model for this pipeline's YAML
   ├── models.py          # Pydantic models owned by this pipeline
   ├── extraction/
   ├── validation/
   ├── transformation/
   ├── loading/
   └── service.py         # single entry point: runs one lifecycle
   ```

2. Subpackage names follow the lifecycle (extract → validate → transform
   → load) and the exception modules of `agpp.shared.exceptions`.
3. **Pipeline YAML lives outside code**, in `config/pipelines/<name>.yaml`. Only its Pydantic model lives in the pipeline.
4. Each pipeline has exactly one `service.py`. It coordinates the stages;
   it contains no business rules itself.
5. `loading/` only maps pipeline models to warehouse rows. SQL, pooling
   and upsert mechanics live in `agpp.shared.database`.
6. Models belong to the pipeline that owns them. A model needed by two or
   more pipelines moves to `agpp.shared.models` (rule 5 of ADR-0001).
7. Scheduling and orchestration are not decided here; they
   are covered by a later ADR with the Airflow work.

## Consequences

### Positive
- A new pipeline is a copy of one known shape.
- Names are consistent across code, exceptions and documentation.

### Negative / trade-offs
- Some folders may stay thin for simple pipelines; consistency is worth it.
