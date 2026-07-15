"""Public core API exports."""

from nexus_verify.core.exceptions import (
    ImageDecodeError,
    ProviderNotFoundError,
    ProviderUnavailableError,
    RecognitionError,
    VerifyError,
)
from nexus_verify.core.registry import ProviderRegistry
from nexus_verify.core.result import VerifyResult
from nexus_verify.core.task import TaskType, VerifyTask

__all__ = [
    "TaskType",
    "VerifyTask",
    "VerifyResult",
    "ProviderRegistry",
    "VerifyError",
    "ProviderNotFoundError",
    "ProviderUnavailableError",
    "ImageDecodeError",
    "RecognitionError",
]
