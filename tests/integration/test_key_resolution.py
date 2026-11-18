from agpp.shared.database import Pool, connection
from agpp.shared.database.warehouse import resolve_keys


def _seed_customers(pool: Pool, ids: list[str]) -> dict[str, int]:
    keys: dict[str, int] = {}
    with connection(pool) as conn:
        for customer_id in ids:
            row = conn.execute(
                "INSERT INTO warehouse.dim_customer"
                " (customer_id, customer_name, country, source_updated_at)"
                " VALUES (%s, 'Marie Dupont', 'LU', now()) RETURNING customer_key",
                (customer_id,),
            ).fetchone()
            assert row is not None
            keys[customer_id] = int(row[0])
    return keys


def _resolve(pool: Pool, values: list[str]) -> dict[str, int]:
    with connection(pool) as conn:
        return resolve_keys(
            conn,
            schema="warehouse",
            table="dim_customer",
            business_key="customer_id",
            surrogate_key="customer_key",
            values=values,
        )


def test_existing_keys_are_resolved(warehouse: Pool) -> None:
    keys = _seed_customers(warehouse, ["CUS-00001", "CUS-00002"])

    assert _resolve(warehouse, ["CUS-00001", "CUS-00002"]) == keys


def test_missing_keys_are_absent_from_the_result(warehouse: Pool) -> None:
    keys = _seed_customers(warehouse, ["CUS-00001"])

    assert _resolve(warehouse, ["CUS-00001", "CUS-99999"]) == {"CUS-00001": keys["CUS-00001"]}


def test_no_values_resolve_to_nothing(warehouse: Pool) -> None:
    assert _resolve(warehouse, []) == {}


def test_the_unknown_member_can_be_resolved_like_any_other(warehouse: Pool) -> None:
    assert _resolve(warehouse, ["UNKNOWN"]) == {"UNKNOWN": -1}
