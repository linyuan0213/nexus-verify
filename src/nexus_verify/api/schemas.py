"""API request and response schemas."""

from typing import Any

from pydantic import BaseModel, Field

from nexus_verify.core.task import TaskType


class VerifyRequest(BaseModel):
    """Request body for /verify endpoint."""

    task_type: TaskType
    image_b64: str | None = None
    image_url: str | None = None
    target: str | None = None
    provider: str | None = None
    extra: dict[str, Any] | None = Field(default=None, description="Provider-specific options")


class VerifyResultData(BaseModel):
    """Inner data containing task result and metadata."""

    task_type: TaskType
    provider: str
    result: dict[str, Any]


class VerifyResponse(BaseModel):
    """Standard API response envelope."""

    code: int = 0
    data: VerifyResultData | None = None
    message: str = "ok"


class ProviderInfo(BaseModel):
    """Provider metadata."""

    name: str
    tasks: list[str]
    available: bool


class TaskInfo(BaseModel):
    """Task type metadata."""

    task_type: str
    description: str


class HealthResponse(BaseModel):
    """Health check response."""

    status: str = "ok"
    version: str = "2.0.0"
