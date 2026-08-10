import pytest

from src.shared.exceptions import (
    AGPPException,
    TransformationError,
    ValidationError,
    InfrastructureError,
    ConfigurationError,
    ExtractionError,
    LoadingError,
)

@pytest.mark.parametrize(
    "exception_type",
    [
        TransformationError,
        ValidationError,
        InfrastructureError,
        ConfigurationError,
        ExtractionError,
        LoadingError,
    ]
)
def test_exception_types_inherit_from_agpp_exception(exception_type):
    error = exception_type("Test error message",
                           error_code='AGPP_TEST_ERROR',)

    assert isinstance(error, AGPPException)
    assert isinstance(error, Exception) 


