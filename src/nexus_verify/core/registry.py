"""Provider registry and discovery."""

from __future__ import annotations

from typing import Any

from nexus_verify.core.exceptions import ProviderNotFoundError, ProviderUnavailableError
from nexus_verify.core.result import VerifyResult
from nexus_verify.core.task import TaskType, VerifyTask


class ProviderRegistry:
    """Registry for verification providers."""

    def __init__(self) -> None:
        self._providers: dict[str, Any] = {}

    def register(self, provider: Any) -> None:
        """Register a provider instance."""
        self._providers[provider.name] = provider

    def list_providers(self, task_type: TaskType | None = None) -> list[Any]:
        """Return providers, optionally filtered by supported task type."""
        providers = list(self._providers.values())
        if task_type is not None:
            providers = [p for p in providers if task_type in p.tasks]
        return providers

    def get(self, task: VerifyTask) -> Any:
        """Select a provider for the given task."""
        task_type = task.task_type

        if task.provider:
            provider = self._providers.get(task.provider)
            if provider is None:
                raise ProviderNotFoundError(f"Provider '{task.provider}' not found")
            if task_type not in provider.tasks:
                raise ProviderNotFoundError(
                    f"Provider '{task.provider}' does not support {task_type}"
                )
            return self._ensure_available(provider)

        candidates = self.list_providers(task_type)
        if not candidates:
            raise ProviderNotFoundError(f"No provider supports {task_type}")

        return self._ensure_available(candidates[0])

    def _ensure_available(self, provider: Any) -> Any:
        if not provider.available:
            raise ProviderUnavailableError(
                f"Provider '{provider.name}' is not available (missing dependencies)"
            )
        return provider

    async def verify(self, task: VerifyTask) -> VerifyResult:
        """Route a task to the selected provider and return its result."""
        provider = self.get(task)
        return await provider.verify(task)


__all__ = ["ProviderRegistry"]
