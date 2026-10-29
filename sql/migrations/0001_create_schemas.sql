-- Operational and analytical storage have different purposes (ADR-0008).
CREATE SCHEMA IF NOT EXISTS operational;
COMMENT ON SCHEMA operational IS
    'Pipeline run history, rejected records, migration bookkeeping and staging data.';

CREATE SCHEMA IF NOT EXISTS warehouse;
COMMENT ON SCHEMA warehouse IS
    'Dimensional model (dim_* and fact_* tables) read by analytics.';
