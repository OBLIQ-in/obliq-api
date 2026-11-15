from typing import Any


class ObliqError(Exception):
    """Base application error."""

    def __init__(
        self,
        code: str,
        message: str,
        *,
        status_code: int = 400,
        retryable: bool = False,
        details: dict[str, Any] | None = None,
    ) -> None:
        self.code = code
        self.message = message
        self.status_code = status_code
        self.retryable = retryable
        self.details = details or {}
        super().__init__(message)


class AuthenticationError(ObliqError):
    def __init__(self, message: str = "Invalid or missing credentials", **kwargs: Any) -> None:
        super().__init__("authentication_error", message, status_code=401, **kwargs)


class AuthorizationError(ObliqError):
    def __init__(self, message: str = "Insufficient permissions", **kwargs: Any) -> None:
        super().__init__("authorization_error", message, status_code=403, **kwargs)


class InsufficientCreditsError(ObliqError):
    def __init__(self, remaining: int = 0, **kwargs: Any) -> None:
        super().__init__(
            "insufficient_credits",
            "Not enough credits to process this request",
            status_code=402,
            details={"remaining_credits": remaining},
            **kwargs,
        )


class RateLimitExceededError(ObliqError):
    def __init__(self, retry_after: int = 60, **kwargs: Any) -> None:
        super().__init__(
            "rate_limit_exceeded",
            "Rate limit exceeded",
            status_code=429,
            retryable=True,
            details={"retry_after": retry_after},
            **kwargs,
        )


class PayloadTooLargeError(ObliqError):
    def __init__(self, message: str = "Upload exceeds maximum allowed size", **kwargs: Any) -> None:
        super().__init__("payload_too_large", message, status_code=413, **kwargs)


class UnsupportedMediaTypeError(ObliqError):
    def __init__(self, message: str = "Unsupported file type", **kwargs: Any) -> None:
        super().__init__("unsupported_media_type", message, status_code=415, **kwargs)


class ValidationError(ObliqError):
    def __init__(self, message: str, **kwargs: Any) -> None:
        super().__init__("validation_error", message, status_code=422, **kwargs)


class NotFoundError(ObliqError):
    def __init__(self, message: str = "Resource not found", **kwargs: Any) -> None:
        super().__init__("not_found", message, status_code=404, **kwargs)


class JobError(ObliqError):
    def __init__(self, code: str, message: str, **kwargs: Any) -> None:
        super().__init__(code, message, status_code=400, **kwargs)


class ProcessingError(ObliqError):
    def __init__(self, message: str = "OCR processing failed", **kwargs: Any) -> None:
        super().__init__("processing_error", message, status_code=500, retryable=True, **kwargs)


class ServiceUnavailableError(ObliqError):
    def __init__(self, message: str = "Service temporarily unavailable", **kwargs: Any) -> None:
        super().__init__(
            "service_unavailable",
            message,
            status_code=503,
            retryable=True,
            **kwargs,
        )
