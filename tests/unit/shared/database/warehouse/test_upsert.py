import pytest

from agpp.shared.database.warehouse.upsert import (
    UpsertResult,
    build_upsert_statement,
    check_rows,
)

COLUMNS = ["product_id", "name", "price"]


def _statement(**overrides: object) -> str:
    options: dict[str, object] = {
        "schema": "warehouse",
        "table": "dim_product",
        "columns": COLUMNS,
        "conflict_columns": ["product_id"],
    }
    options.update(overrides)
    return build_upsert_statement(**options).as_string()  # type: ignore[arg-type]


def test_statement_upserts_on_the_business_key() -> None:
    text = _statement()

    assert text.startswith('INSERT INTO "warehouse"."dim_product" ("product_id", "name", "price")')
    assert "VALUES (%s, %s, %s)" in text
    assert 'ON CONFLICT ("product_id") DO UPDATE SET' in text


def test_statement_updates_only_non_key_columns_and_the_audit_column() -> None:
    text = _statement()

    assert '"name" = EXCLUDED."name"' in text
    assert '"price" = EXCLUDED."price"' in text
    assert '"product_id" = EXCLUDED' not in text
    assert '"updated_at" = now()' in text


def test_statement_only_writes_changed_rows() -> None:
    text = _statement()

    assert (
        'WHERE ("dim_product"."name", "dim_product"."price")'
        ' IS DISTINCT FROM (EXCLUDED."name", EXCLUDED."price")'
    ) in text


def test_audit_column_can_be_omitted() -> None:
    assert "updated_at" not in _statement(audit_column=None)


def test_update_columns_can_be_restricted() -> None:
    text = _statement(update_columns=["price"])

    assert '"price" = EXCLUDED."price"' in text
    assert '"name" = EXCLUDED."name"' not in text


def test_empty_update_columns_means_do_nothing_on_conflict() -> None:
    text = _statement(update_columns=[])

    assert text.endswith('ON CONFLICT ("product_id") DO NOTHING')


def test_identifiers_are_quoted() -> None:
    text = _statement(table='odd"table')

    assert '"odd""table"' in text


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"columns": []}, "columns must not be empty"),
        ({"conflict_columns": []}, "conflict_columns must not be empty"),
        ({"conflict_columns": ["missing"]}, "conflict columns not in columns"),
        ({"update_columns": ["missing"]}, "update columns not in columns"),
        ({"update_columns": ["product_id"]}, "key columns cannot be updated"),
    ],
)
def test_invalid_arguments_are_rejected(overrides: dict[str, object], message: str) -> None:
    with pytest.raises(ValueError, match=message):
        _statement(**overrides)


def test_rows_must_match_the_column_count() -> None:
    with pytest.raises(ValueError, match="row 1 has 2 values, expected 3"):
        check_rows([("a", "b", "c"), ("a", "b")], 3)


def test_unchanged_is_attempted_minus_written() -> None:
    assert UpsertResult(attempted=10, written=3).unchanged == 7
