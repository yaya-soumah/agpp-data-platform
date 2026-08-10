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

def test_exception_chaining_preserves_original_exception():
    original_exception = RuntimeError("Database connection failed")

    try:
        try:
            raise original_exception
        except RuntimeError as exc:
            raise LoadingError("Failed to load data",
                                error_code='LOADING_ERROR',
                                context={"file": "data.csv"},
                                retryable=True) from exc
    except LoadingError as error:        
        assert isinstance(error, AGPPException)
        assert error.__cause__ is original_exception
        assert str(error.__cause__) == "Database connection failed"    

def test_exception_chaining_is_explicit():
    original = RuntimeError("connection failed")

    try:
        try:
            raise original
        except RuntimeError as exc:
            raise LoadingError("Failed to load data",
                                error_code='LOADING_ERROR',  
            ) from exc 
    except LoadingError as error:
        assert error.__cause__ is original
        assert error.__suppress_context__ is True

def test_error_code_is_machine_readable_identifier() :
    error = ValidationError(
        "Supplier currency is invalid",
        error_code='VALIDATION_INVALID_CURRENCY',
    )

    assert error.error_code == 'VALIDATION_INVALID_CURRENCY'
    assert error.message == "Supplier currency is invalid"
    assert error.error_code != error.message  # Ensure error_code is distinct from message

def test_context_is_independent_from_source_dictionary():
    context = {"supplier_id": 1847}

    error = ValidationError(
        "Invalid supplier ID",
        error_code='VALIDATION_INVALID_SUPPLIER',
        context={"supplier_id": 1847},
    )

    assert error.context is not context