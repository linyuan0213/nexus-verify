"""Verification engine."""

from nexus_verify.config import settings
from nexus_verify.core import ProviderRegistry, TaskType, VerifyTask
from nexus_verify.core.result import VerifyResult
from nexus_verify.providers import default_providers


class VerifyEngine:
    """High-level engine that routes tasks to providers."""

    def __init__(self, registry: ProviderRegistry | None = None) -> None:
        self.registry = registry or ProviderRegistry()
        if not self.registry._providers:
            for provider in default_providers():
                self.registry.register(provider)

    async def verify(self, task: VerifyTask) -> VerifyResult:
        """Route and execute a verification task."""
        if not task.provider:
            default = self._default_provider(task.task_type)
            if default and default in self.registry._providers:
                task.provider = default
        return await self.registry.verify(task)

    def _default_provider(self, task_type: TaskType) -> str:
        mapping = {
            TaskType.CAPTCHA: settings.default_provider_captcha,
            TaskType.CLICK_CAPTCHA: settings.default_provider_click_captcha,
            TaskType.IMAGE_CLICK_CAPTCHA: settings.default_provider_image_click_captcha,
            TaskType.TEXT_OCR: settings.default_provider_text_ocr,
            TaskType.SLIDE_CAPTCHA: settings.default_provider_slide_captcha,
            TaskType.ROTATE_CAPTCHA: settings.default_provider_rotate_captcha,
            TaskType.GAP_MATCH: settings.default_provider_gap_match,
        }
        return mapping.get(task_type, "")

    def providers(self) -> list[dict[str, str | list[str] | bool]]:
        """Return metadata for all registered providers."""
        return [
            {
                "name": p.name,
                "tasks": [t.value for t in p.tasks],
                "available": p.available,
            }
            for p in self.registry.list_providers()
        ]
