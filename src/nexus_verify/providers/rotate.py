"""OpenCV-based provider for rotate captcha tasks."""

import cv2
from typing import Any

from nexus_verify.core.exceptions import ImageDecodeError, RecognitionError
from nexus_verify.core.result import VerifyResult
from nexus_verify.core.task import TaskType, VerifyTask
from nexus_verify.preprocessing import decode_base64, load_image, pil_to_cv2
from nexus_verify.preprocessing.transforms import find_best_rotation
from nexus_verify.providers.base import Provider


class RotateProvider(Provider):
    """Provider using OpenCV rotation matching for rotate captcha."""

    name = "rotate"
    tasks = {TaskType.ROTATE_CAPTCHA}

    @property
    def available(self) -> bool:
        try:
            import cv2

            return True
        except ImportError:
            return False

    async def verify(self, task: VerifyTask) -> VerifyResult:
        image = load_image(task)

        extra = task.extra or {}
        template_b64 = extra.get("template_b64")
        if not template_b64:
            raise ImageDecodeError("rotate_captcha requires extra.template_b64")

        template = pil_to_cv2(decode_base64(template_b64))

        angle, confidence = find_best_rotation(image, template)
        return VerifyResult(angle=angle, confidence=confidence)
