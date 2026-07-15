"""Task type definitions for verification requests."""

from enum import StrEnum
from typing import Any

from pydantic import BaseModel


class TaskType(StrEnum):
    """Supported verification task types."""

    CAPTCHA = "captcha"
    CLICK_CAPTCHA = "click_captcha"
    IMAGE_CLICK_CAPTCHA = "image_click_captcha"
    SLIDE_CAPTCHA = "slide_captcha"
    ROTATE_CAPTCHA = "rotate_captcha"
    GAP_MATCH = "gap_match"
    TEXT_OCR = "text_ocr"


class VerifyTask(BaseModel):
    """A single verification task request."""

    task_type: TaskType
    image_b64: str | None = None
    image_url: str | None = None
    target: str | None = None
    provider: str | None = None
    extra: dict[str, Any] | None = None

    model_config = {"extra": "ignore"}
