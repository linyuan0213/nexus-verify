"""FastAPI router for verification endpoints."""

import base64
import io
from pathlib import Path

import cv2
import numpy as np
from fastapi import APIRouter
from loguru import logger
from PIL import Image

from nexus_verify.api.schemas import (
    FaceBBoxRequest,
    FaceBBoxResponse,
    FaceBox,
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


@router.post("/face/bbox", response_model=FaceBBoxResponse)
def face_bbox(request: FaceBBoxRequest) -> FaceBBoxResponse:
    """Detect frontal faces and return bounding boxes."""
    try:
        raw = base64.b64decode(request.image_b64, validate=True)
        with Image.open(io.BytesIO(raw)) as img:
            rgb = np.array(img.convert("RGB"))
    except Exception as exc:  # noqa: BLE001
        return FaceBBoxResponse(code=400, message=f"invalid image: {exc}")
    model = Path(__file__).resolve().parents[3] / "models" / "face_detection_yunet_2023mar.onnx"
    if not model.exists():
        return FaceBBoxResponse(code=500, message="face model missing")
    height, width = rgb.shape[:2]
    detector = cv2.FaceDetectorYN.create(str(model), "", (int(width), int(height)), 0.6, 0.3, 5000)
    bgr = cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)
    _, detected = detector.detect(bgr)
    faces = []
    if detected is not None:
        for item in detected:
            x, y, w, h = (int(v) for v in item[:4])
            if w >= request.min_size and h >= request.min_size:
                faces.append(FaceBox(x=x, y=y, width=w, height=h))
    faces.sort(key=lambda item: item.width * item.height, reverse=True)
    return FaceBBoxResponse(faces=faces, width=int(rgb.shape[1]), height=int(rgb.shape[0]))


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    """Health check endpoint."""
    return HealthResponse()
