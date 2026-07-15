"""FastAPI router for verification endpoints."""

from fastapi import APIRouter
from loguru import logger

from nexus_verify.api.schemas import (
    HealthResponse,
    ProviderInfo,
    TaskInfo,
    VerifyRequest,
    VerifyResponse,
    VerifyResultData,
)
from nexus_verify.core.exceptions import VerifyError
from nexus_verify.core.result import VerifyResult
from nexus_verify.core.task import TaskType, VerifyTask
from nexus_verify.engine import VerifyEngine

router = APIRouter()
engine = VerifyEngine()


def _result_to_dict(result: VerifyResult) -> dict:
    return result.model_dump(exclude_none=True)


@router.post("/verify", response_model=VerifyResponse)
async def verify(request: VerifyRequest) -> VerifyResponse:
    """Submit a verification task."""
    task = VerifyTask.model_validate(request.model_dump())
    try:
        result = await engine.verify(task)
    except VerifyError as exc:
        logger.error(f"Verification failed: {exc.message}")
        return VerifyResponse(code=exc.code, message=exc.message)
    except Exception as exc:
        logger.exception("Unexpected error during verification")
        return VerifyResponse(code=500, message=f"Internal error: {exc}")

    data = VerifyResultData(
        task_type=task.task_type,
        provider=task.provider or "",
        result=_result_to_dict(result),
    )
    logger.info(
        f"Verification success: task={task.task_type}, "
        f"provider={task.provider or 'default'}, "
        f"target={task.target or ''}, "
        f"result={_result_to_dict(result)}"
    )
    return VerifyResponse(data=data)


@router.get("/providers", response_model=list[ProviderInfo])
async def list_providers() -> list[ProviderInfo]:
    """List registered providers and their supported task types."""
    return [ProviderInfo.model_validate(p) for p in engine.providers()]


@router.get("/tasks", response_model=list[TaskInfo])
async def list_tasks() -> list[TaskInfo]:
    """List supported verification task types."""
    return [TaskInfo(task_type=t.value, description=t.value) for t in TaskType]


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    """Health check endpoint."""
    return HealthResponse()
