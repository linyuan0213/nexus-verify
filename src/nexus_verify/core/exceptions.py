"""Business exceptions for nexus_verify."""


class VerifyError(Exception):
    """Base exception for verification errors."""

    def __init__(self, message: str, code: int = -1) -> None:
        super().__init__(message)
        self.message = message
        self.code = code


class ProviderNotFoundError(VerifyError):
    """Raised when no provider supports the requested task type."""

    def __init__(self, message: str = "No provider available") -> None:
        super().__init__(message, code=404)


class ProviderUnavailableError(VerifyError):
    """Raised when a provider is registered but its dependencies are missing."""

    def __init__(self, message: str = "Provider is unavailable") -> None:
        super().__init__(message, code=503)


class ImageDecodeError(VerifyError):
    """Raised when an image cannot be decoded."""

    def __init__(self, message: str = "Failed to decode image") -> None:
        super().__init__(message, code=400)


class RecognitionError(VerifyError):
    """Raised when recognition fails within a provider."""

    def __init__(self, message: str = "Recognition failed") -> None:
        super().__init__(message, code=-1)
