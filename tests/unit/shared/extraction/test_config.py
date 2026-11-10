import pytest
from pydantic import ValidationError

from agpp.shared.extraction import CsvSource


def test_defaults() -> None:
    source = CsvSource.model_validate({"type": "csv", "path": "orders.csv"})

    assert (source.delimiter, source.encoding) == (",", "utf-8")


def test_only_csv_sources_are_supported() -> None:
    with pytest.raises(ValidationError):
        CsvSource.model_validate({"type": "ftp", "path": "x"})


@pytest.mark.parametrize("values", [{"path": ""}, {"delimiter": ";;"}, {"delimiter": ""}])
def test_invalid_settings_are_rejected(values: dict[str, str]) -> None:
    with pytest.raises(ValidationError):
        CsvSource.model_validate({"type": "csv", "path": "x", **values})
