CREATE VIEW operational.quality_latest AS
SELECT DISTINCT ON (check_name)
    check_name,
    status,
    value,
    warn_threshold,
    fail_threshold,
    comparison,
    message,
    run_id,
    checked_at
FROM operational.quality_check_results
ORDER BY check_name, checked_at DESC, result_id DESC;
