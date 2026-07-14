"""Tests for the verification engine."""

import pytest

from nexus_verify.core import ProviderRegistry
from nexus_verify.core.task import TaskType, VerifyTask
from nexus_verify.engine import VerifyEngine
from tests.conftest import DummyProvider


@pytest.fixture
def engine_with_dummy() -> VerifyEngine:
    registry = ProviderRegistry()
    registry.register(DummyProvider())
    return VerifyEngine(registry)


@pytest.mark.asyncio
async def test_engine_routes_captcha(engine_with_dummy: VerifyEngine) -> None:
    task = VerifyTask(task_type=TaskType.CAPTCHA)
    result = await engine_with_dummy.verify(task)
    assert result.text == "DUMMY"


def test_engine_lists_providers(engine_with_dummy: VerifyEngine) -> None:
    providers = engine_with_dummy.providers()
    assert len(providers) == 1
    assert providers[0]["name"] == "dummy"
