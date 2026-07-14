"""Tests for the provider registry."""

import pytest

from nexus_verify.core import (
    ProviderRegistry,
    ProviderNotFoundError,
    ProviderUnavailableError,
)
from nexus_verify.core.task import TaskType, VerifyTask
from tests.conftest import UnavailableProvider


def test_register_and_list(registry: ProviderRegistry) -> None:
    providers = registry.list_providers()
    assert len(providers) == 1
    assert providers[0].name == "dummy"


def test_filter_by_task_type(registry: ProviderRegistry) -> None:
    providers = registry.list_providers(TaskType.CAPTCHA)
    assert len(providers) == 1

    providers = registry.list_providers(TaskType.SLIDE_CAPTCHA)
    assert len(providers) == 0


def test_get_provider_by_name(registry: ProviderRegistry) -> None:
    task = VerifyTask(task_type=TaskType.CAPTCHA, provider="dummy")
    provider = registry.get(task)
    assert provider.name == "dummy"


def test_get_unknown_provider(registry: ProviderRegistry) -> None:
    task = VerifyTask(task_type=TaskType.CAPTCHA, provider="unknown")
    with pytest.raises(ProviderNotFoundError):
        registry.get(task)


def test_unavailable_provider() -> None:
    reg = ProviderRegistry()
    reg.register(UnavailableProvider())
    task = VerifyTask(task_type=TaskType.CAPTCHA)
    with pytest.raises(ProviderUnavailableError):
        reg.get(task)


@pytest.mark.asyncio
async def test_verify_routes_to_provider(registry: ProviderRegistry) -> None:
    task = VerifyTask(task_type=TaskType.CAPTCHA)
    result = await registry.verify(task)
    assert result.text == "DUMMY"
