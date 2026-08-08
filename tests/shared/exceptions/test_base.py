from src.shared.exceptions import AGPPException

def test_agpp_exception_is_exception():

    error = AGPPException("Test error message",
                          error_code='AGPP_TEST_ERROR',)

    assert isinstance(error, Exception)


def test_agpp_exception_stores_error_information():

    error_message = "Test error message"
    error_code = 'AGPP_TEST_ERROR'
    error_context = {'component': 'test'}
    error_recyclable = True

    error = AGPPException(error_message, 
                          error_code=error_code,
                          context=error_context,
                          recyclable=error_recyclable)

    assert error.message == error_message
    assert error.error_code == error_code
    assert error.context == error_context
    assert error.recyclable is True

def test_agpp_exception_defaults_to_non_retryable():

    error_message = "Test error message"
    error = AGPPException(error_message,
                          error_code='AGPP_TEST_ERROR',)

    assert error.recyclable is False
    assert str(error) == error_message

