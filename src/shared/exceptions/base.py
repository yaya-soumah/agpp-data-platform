from typing import Any


class AGPPException(Exception):
    """Base class for all AGPP platform-specific exceptions."""

    def __init__(
        self,
        message: str,
        *,
        error_code: str,
        context: dict[str, Any] | None = None,
        retryable: bool = False,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.error_code = error_code
        self.context = dict(context) if context is not None else {}
        self.retryable = retryable
