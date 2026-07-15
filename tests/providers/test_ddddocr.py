"""Tests for the DdddOcr provider."""

import pytest

from nexus_verify.core.task import TaskType, VerifyTask
from nexus_verify.providers.ddddocr import DdddOcrProvider

ddddocr = pytest.importorskip("ddddocr")


@pytest.fixture
def provider() -> DdddOcrProvider:
    return DdddOcrProvider()


@pytest.mark.asyncio
async def test_available(provider: DdddOcrProvider) -> None:
    assert provider.available is True


@pytest.mark.asyncio
async def test_captcha_requires_image(provider: DdddOcrProvider) -> None:
    task = VerifyTask(task_type=TaskType.CAPTCHA)
    with pytest.raises(Exception):
        await provider.verify(task)


@pytest.mark.asyncio
async def test_click_captcha_requires_target(provider: DdddOcrProvider) -> None:
    from tests.conftest import make_image_b64

    task = VerifyTask(task_type=TaskType.CLICK_CAPTCHA, image_b64=make_image_b64())
    with pytest.raises(Exception):
        await provider.verify(task)
