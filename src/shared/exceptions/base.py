from typing import Any, Dict

class AGPPException(Exception):
    """Base class for all AGPP platform-specific exceptions."""

    def __init__(
            self, 
            message: str, 
            *,
            error_code: str, 
            context: Dict[str, Any] | None = None,
            retryable: bool = False
            ) -> None:
        super().__init__(message)
        self.message = message
        self.error_code = error_code
        self.context = context or {}
        self.retryable = retryable
