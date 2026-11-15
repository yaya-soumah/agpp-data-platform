import pytest
from pydantic import ValidationError

from agpp.shared.extraction import ApiSource, CsvSource


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


def _api(**overrides: object) -> ApiSource:
    return ApiSource.model_validate(
        {"type": "api", "base_url": "https://stock.example.com", **overrides}
    )


def test_an_api_source_has_defaults() -> None:
    source = _api()

    assert (source.path, source.timeout_seconds, source.page_size) == ("/", 10.0, 500)
    assert source.token is None


def test_a_blank_token_means_no_authentication() -> None:
    assert _api(token="").token is None
    assert _api(token="   ").token is None  # noqa: S106


def test_the_token_is_a_secret() -> None:
    source = _api(token="s3cret")  # noqa: S106

    assert source.token is not None
    assert source.token.get_secret_value() == "s3cret"
    assert "s3cret" not in repr(source)
    assert "s3cret" not in str(source)


@pytest.mark.parametrize(
    "invalid",
    [
        {"base_url": "ftp://stock.example.com"},
        {"base_url": "stock.example.com"},
        {"path": "v1/stock"},
        {"timeout_seconds": 0},
        {"page_size": 0},
        {"page_size": 10_001},
    ],
)
def test_invalid_api_settings_are_rejected(invalid: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        _api(**invalid)


def test_an_api_source_is_not_a_csv_source() -> None:
    with pytest.raises(ValidationError):
        CsvSource.model_validate({"type": "api", "path": "x"})
