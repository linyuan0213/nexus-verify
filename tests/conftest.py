"""Shared pytest fixtures and helpers."""

import base64
from io import BytesIO

import pytest
from PIL import Image

from nexus_verify.core.registry import ProviderRegistry
from nexus_verify.core.result import VerifyResult
from nexus_verify.core.task import TaskType, VerifyTask
from nexus_verify.providers.base import Provider


def make_image_b64(width: int = 100, height: int = 40, color: tuple[int, int, int] = (255, 255, 255)) -> str:
    """Create a simple base64 encoded PNG image for tests."""
    image = Image.new("RGB", (width, height), color)
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return base64.b64encode(buffer.getvalue()).decode("utf-8")


class DummyProvider(Provider):
    """Provider mock for tests."""

    name = "dummy"
    tasks = {TaskType.CAPTCHA}

    @property
    def available(self) -> bool:
        return True

    async def verify(self, task: VerifyTask) -> VerifyResult:
        return VerifyResult(text="DUMMY")


class UnavailableProvider(Provider):
    """Unavailable provider mock for tests."""

    name = "unavailable"
    tasks = {TaskType.CAPTCHA}

    @property
    def available(self) -> bool:
        return False

    async def verify(self, task: VerifyTask) -> VerifyResult:
        return VerifyResult(text="")


@pytest.fixture
def registry() -> ProviderRegistry:
    reg = ProviderRegistry()
    reg.register(DummyProvider())
    return reg


@pytest.fixture
def sample_image_b64() -> str:
    return make_image_b64()
