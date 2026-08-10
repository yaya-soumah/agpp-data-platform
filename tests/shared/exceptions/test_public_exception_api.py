from src.shared.exceptions import (AGPPException, 
                                   TransformationError,
                                   ValidationError,
                                   InfrastructureError,     
                                 ConfigurationError,
                                    ExtractionError,
                                      LoadingError
                                   )

def test_public_exception_api():
    assert AGPPException is not None
    assert TransformationError is not None
    assert ValidationError is not None
    assert InfrastructureError is not None
    assert ConfigurationError is not None
    assert ExtractionError is not None
    assert LoadingError is not None 