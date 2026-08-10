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


def test_specialized_exception_preserves_base_contract():
    error = ValidationError("Test validation error",
                           error_code='VALIDATION_INVALID_SUPPLIER', 
                           context={"supplier_id": "1847"},
                           retryable=False)

    assert isinstance(error, AGPPException)
    assert error.message == "Test validation error"
    assert error.error_code == 'VALIDATION_INVALID_SUPPLIER'    
    assert error.context == {"supplier_id": "1847"}
    assert error.retryable is False
