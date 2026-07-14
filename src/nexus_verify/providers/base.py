"""Abstract base class for verification providers."""

from abc import ABC, abstractmethod

from nexus_verify.core.result import VerifyResult
from nexus_verify.core.task import TaskType, VerifyTask


class Provider(ABC):
    """Base class for all verification providers."""

    name: str
    tasks: set[TaskType]

    @property
    @abstractmethod
    def available(self) -> bool:
        """Whether the provider's dependencies are installed and usable."""

    @abstractmethod
    async def verify(self, task: VerifyTask) -> VerifyResult:
        """Execute the verification task."""
