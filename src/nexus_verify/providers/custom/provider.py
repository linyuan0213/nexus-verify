"""Custom / trained model provider stub."""

from nexus_verify.core.result import VerifyResult
from nexus_verify.core.task import TaskType, VerifyTask
from nexus_verify.providers.base import Provider


class CustomProvider(Provider):
    """Stub provider for user-trained or ONNX models."""

    name = "custom"
    tasks: set[TaskType] = set()

    @property
    def available(self) -> bool:
        return False

    async def verify(self, task: VerifyTask) -> VerifyResult:
        return VerifyResult(success=False, text="")
