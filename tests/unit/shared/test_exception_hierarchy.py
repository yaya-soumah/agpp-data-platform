import pytest

from agpp.shared.exceptions import (
    AgppError,
    ConfigurationError,
    ConfigurationFileError,
    DatabaseConnectionError,
    DataValidationError,
    ExtractionError,
    InfrastructureError,
    InvalidConfigurationError,
    LoadingError,
    MigrationError,
    QualityThresholdExceededError,
    SchemaValidationError,
    SourceUnavailableError,
    TransformationError,
    TransientInfrastructureError,
    UnsupportedSourceError,
    WarehouseWriteError,
)

HIERARCHY: list[tuple[type[AgppError], type[AgppError], str, bool]] = [
    (ConfigurationError, AgppError, "configuration", False),
    (ConfigurationFileError, ConfigurationError, "configuration", False),
    (InvalidConfigurationError, ConfigurationError, "configuration", False),
    (ExtractionError, AgppError, "extraction", False),
    (SourceUnavailableError, ExtractionError, "extraction", True),
    (UnsupportedSourceError, ExtractionError, "extraction", False),
    (DataValidationError, AgppError, "validation", False),
    (SchemaValidationError, DataValidationError, "validation", False),
    (QualityThresholdExceededError, DataValidationError, "validation", False),
    (TransformationError, AgppError, "transformation", False),
    (LoadingError, AgppError, "loading", False),
    (WarehouseWriteError, LoadingError, "loading", False),
    (InfrastructureError, AgppError, "infrastructure", False),
    (TransientInfrastructureError, InfrastructureError, "infrastructure", True),
    (MigrationError, InfrastructureError, "infrastructure", False),
    (DatabaseConnectionError, TransientInfrastructureError, "infrastructure", True),
]


@pytest.mark.parametrize(("error_class", "parent", "stage", "retryable"), HIERARCHY)
def test_hierarchy_stage_and_retryability(
    error_class: type[AgppError], parent: type[AgppError], stage: str, retryable: bool
) -> None:
    error = error_class("boom", context={"detail": 1})

    assert issubclass(error_class, parent)
    assert error.stage == stage
    assert error.retryable is retryable
    assert error.context == {"detail": 1}


def test_wrapping_keeps_the_original_cause() -> None:
    def raise_exception() -> None:
        try:
            raise TimeoutError("socket timed out")
        except TimeoutError as original:
            raise SourceUnavailableError("supplier API down") from original

    with pytest.raises(SourceUnavailableError) as error:
        raise_exception()

    assert isinstance(error.value.__cause__, TimeoutError)
