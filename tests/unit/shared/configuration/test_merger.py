from agpp.shared.configuration.merger import deep_merge


def test_override_replaces_scalar() -> None:
    assert deep_merge({"a": 1}, {"a": 2}) == {"a": 2}


def test_nested_mappings_are_merged() -> None:
    base = {"db": {"host": "h", "port": 1}}

    assert deep_merge(base, {"db": {"port": 2}}) == {"db": {"host": "h", "port": 2}}


def test_lists_are_replaced_not_concatenated() -> None:
    assert deep_merge({"x": [1, 2]}, {"x": [3]}) == {"x": [3]}


def test_new_keys_are_added() -> None:
    assert deep_merge({"a": 1}, {"b": 2}) == {"a": 1, "b": 2}


def test_inputs_are_not_mutated() -> None:
    base = {"db": {"port": 1}}
    override = {"db": {"port": 2}}

    result = deep_merge(base, override)
    result["db"]["port"] = 3

    assert base == {"db": {"port": 1}}
    assert override == {"db": {"port": 2}}
