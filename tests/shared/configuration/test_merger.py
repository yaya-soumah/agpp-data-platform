from src.shared.configuration.merger import deep_merge


def test_deep_merge_preserves_base_values():
    base = {
        "database": {"port": 5432, "pool_size": 10, "connection_timeout": 30},
    }

    override = {
        "database": {
            "pool_size": 5,
        }
    }

    result = deep_merge(base, override)

    assert isinstance(result, dict)
    assert result == {
        "database": {"port": 5432, "pool_size": 5, "connection_timeout": 30},
    }


def test_override_replaces_scalar_value():
    base = {
        "pipeline": {
            "batch_size": 1000,
        },
    }

    override = {
        "pipeline": {
            "batch_size": 5000,
        },
    }

    result = deep_merge(base, override)

    assert result["pipeline"]["batch_size"] == 5000


def test_nested_values_are_merged_recursively():
    base = {
        "database": {
            "connection": {
                "host": "localhost",
                "port": 5432,
            },
        },
    }

    override = {
        "database": {
            "connection": {
                "port": 5433,
            },
        },
    }

    result = deep_merge(base, override)

    assert result == {
        "database": {
            "connection": {
                "host": "localhost",
                "port": 5433,
            },
        },
    }


def test_override_mapping_can_replace_scalar():
    base = {
        "database": {
            "pool_size": 10,
        },
    }

    override = {
        "database": 5,
    }

    result = deep_merge(base, override)

    assert result == {
        "database": 5,
    }


def test_lists_are_replaced():
    base = {
        "regions": ["EU", "ASIA"],
    }

    override = {
        "regions": ["EU"],
    }

    result = deep_merge(base, override)

    assert result == {
        "regions": ["EU"],
    }


def test_inputs_are_not_mutated():
    base = {
        "database": {
            "port": 5432,
            "pool_size": 10,
        },
    }

    override = {
        "database": {
            "pool_size": 5,
        },
    }

    base_before = {
        "database": {
            "port": 5432,
            "pool_size": 10,
        },
    }

    override_before = {
        "database": {
            "pool_size": 5,
        },
    }

    deep_merge(base, override)

    assert base == base_before
    assert override == override_before


def test_result_is_independent_from_inputs():
    base = {
        "database": {
            "pool_size": 10,
        },
    }

    override = {
        "pipeline": {
            "batch_size": 1000,
        },
    }

    result = deep_merge(base, override)

    result["database"]["pool_size"] = 20
    result["pipeline"]["batch_size"] = 5000

    assert base["database"]["pool_size"] == 10
    assert override["pipeline"]["batch_size"] == 1000
