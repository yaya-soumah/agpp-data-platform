from src.shared.exceptions import AGPPException


def test_agpp_exception_is_exception() -> None:

    error = AGPPException(
        "Test error message",
        error_code="AGPP_TEST_ERROR",
    )

    assert isinstance(error, Exception)


def test_agpp_exception_stores_error_information() -> None:

    error_message = "Test error message"
    error_code = "AGPP_TEST_ERROR"
    error_context = {"component": "test"}
    error_retryable = True

    error = AGPPException(
        error_message,
        error_code=error_code,
        context=error_context,
        retryable=error_retryable,
    )

    assert error.message == error_message
    assert error.error_code == error_code
    assert error.context == error_context
    assert error.retryable is True


def test_agpp_exception_defaults_to_non_retryable() -> None:

    error_message = "Test error message"
    error = AGPPException(
        error_message,
        error_code="AGPP_TEST_ERROR",
    )

    assert error.retryable is False
    assert str(error) == error_message
