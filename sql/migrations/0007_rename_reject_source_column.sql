-- Rejects are shared by every pipeline, so the key column is named after the concept,
-- not after a supplier (ADR-0017). A rename is acceptable before the first release;
-- on a live system this would be expand, migrate, contract.
ALTER TABLE operational.rejected_records RENAME COLUMN supplier_id TO source_id;
ALTER INDEX operational.rejected_records_supplier_idx RENAME TO rejected_records_source_idx;

COMMENT ON COLUMN operational.rejected_records.source_id IS
    'The unit the line came from: a supplier id or a file.';
