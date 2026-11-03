# ADR-0011: Extraction design

- **Status:** Accepted
- **Date:** 2026-11-02
- **Related decisions:** 07 (Pipeline Flow), 09 (Logging), 10 (Exceptions),
  14 (Extensibility)

## Context

The Supplier Product pipeline reads one source per supplier, configured in
YAML. Today every source is a CSV file; APIs and FTP servers will follow.
Adding a source type must not change validation, transformation or loading,
and one broken supplier must not hide the others.

## Decision

1. **Stage layout.** Each stage package exposes its work through a
   `stage.py` function; the pipeline's `service.py` composes the stages
   (ADR-0004). The extraction package holds the contract (`base.py`), one
   module per source type, `factory.py` and `stage.py`.
2. **Contract.** An `Extractor` has one method, `extract()`, returning an
   `ExtractionResult` (supplier, source description, columns found, records).
   Extractors do input and structure only: no business interpretation.
3. **Raw records.** A `RawRecord` holds text values keyed by trimmed,
   lower-case column names, the source line number, and an optional
   `problem` for rows that are structurally wrong (for example, the wrong
   number of fields). Values are never trimmed or converted here.
4. **No schema checks in extraction.** The extractor reports the columns it
   found. Checking required columns is validation (`SchemaValidationError`).
5. **Errors.**
   - A source that cannot be read (file missing, permission denied, network
     failure) raises `SourceUnavailableError`, which is retryable; a late
     delivery or a briefly unavailable share can fix itself.
   - Malformed content (undecodable bytes, duplicate column names, broken
     quoting, oversized fields, unknown encoding) raises `ExtractionError`,
     which is not retryable.
   - Ragged rows are data, not exceptions: they are flagged on the record.
6. **Factory and registry.** `create_extractor` picks the extractor from
   `source.type`. New source types call `register_extractor`; nothing
   existing changes (Decision 14). An unknown type raises
   `UnsupportedSourceError`.
7. **Memory.** A file is read fully into memory. Catalogs are expected to
   stay below roughly 100,000 rows. Streaming is deferred until a source needs it.
8. **Isolation and retry.** Suppliers are extracted independently. Retryable
   errors are retried with the policy from the pipeline configuration. A
   supplier that still fails is reported and the others continue; the run
   ends with a failure status.
9. **Logging.** The stage logs, with the run context, the start, one line per
   supplier (rows and columns) and the end. A failure is logged once, at the
   stage (ADR-0007).

## Consequences

### Positive
- New source types are additive.
- Reject reports can point at the exact source line.
- One failing supplier does not stop the others.

### Negative / trade-offs
- Whole-file reads limit file size.
- Retrying a missing local file costs a few seconds of waiting.

### Follow-ups
- The extraction stage and its retry configuration.
