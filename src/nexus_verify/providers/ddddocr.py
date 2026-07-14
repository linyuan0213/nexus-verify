"""DdddOcr-based provider for captcha and OCR tasks."""

from typing import Any

import ddddocr
from nexus_verify.core.exceptions import RecognitionError
from nexus_verify.core.result import VerifyResult
from nexus_verify.core.task import TaskType, VerifyTask
from nexus_verify.preprocessing import cv2_to_pil, load_image, preprocess_captcha
from nexus_verify.providers.base import Provider
from nexus_verify.providers.click_solver import ClickCaptchaSolver


class DdddOcrProvider(Provider):
    """Provider using ddddocr for character captcha, click captcha and OCR."""

    name = "ddddocr"
    tasks = {TaskType.CAPTCHA, TaskType.CLICK_CAPTCHA, TaskType.TEXT_OCR}

    @property
    def available(self) -> bool:
        return True

    async def verify(self, task: VerifyTask) -> VerifyResult:
        image = load_image(task)

        if task.task_type == TaskType.CAPTCHA:
            ocr = ddddocr.DdddOcr(show_ad=False)
            return self._recognize_captcha(image, ocr, task.extra)

        if task.task_type == TaskType.CLICK_CAPTCHA:
            if not task.target:
                raise RecognitionError("click_captcha requires 'target' text")
            det_ocr = ddddocr.DdddOcr(det=True, ocr=False, show_ad=False)
            cls_ocr = ddddocr.DdddOcr(beta=True, show_ad=False)
            return self._recognize_click(image, det_ocr, cls_ocr, task.target)

        if task.task_type == TaskType.TEXT_OCR:
            det_ocr = ddddocr.DdddOcr(det=True, ocr=False, show_ad=False)
            cls_ocr = ddddocr.DdddOcr(show_ad=False)
            return self._recognize_text(image, det_ocr, cls_ocr)

        raise RecognitionError(f"Unsupported task type: {task.task_type}")

    def _recognize_captcha(
        self, image: Any, ocr: Any, extra: dict[str, Any] | None
    ) -> VerifyResult:
        if extra is None or extra.get("preprocess", True):
            pil_image = preprocess_captcha(image, extra)
        else:
            pil_image = cv2_to_pil(image)

        text = ocr.classification(pil_image)
        text = text.replace("之", "2").replace(">", "7").upper()
        return VerifyResult(text=text)

    def _recognize_click(
        self, image: Any, det_ocr: Any, cls_ocr: Any, target: str
    ) -> VerifyResult:
        solver = ClickCaptchaSolver(det_ocr, cls_ocr)
        points = solver.solve(image, target)
        return VerifyResult(points=points)

    def _recognize_text(self, image: Any, det_ocr: Any, cls_ocr: Any) -> VerifyResult:
        detections = self._detect_and_classify(image, det_ocr, cls_ocr)
        texts = [det["text"] for det in detections]
        return VerifyResult(text="\n".join(texts))

    def _detect_and_classify(
        self, image: Any, det_ocr: Any, cls_ocr: Any
    ) -> list[dict[str, Any]]:
        try:
            pil_image = cv2_to_pil(image)
            boxes = det_ocr.detection(pil_image)
        except Exception as exc:
            raise RecognitionError(f"Detection failed: {exc}") from exc

        detections: list[dict[str, Any]] = []
        for box in boxes:
            x1, y1, x2, y2 = box
            crop = pil_image.crop((x1, y1, x2, y2))
            try:
                text = cls_ocr.classification(crop)
            except Exception:
                text = ""
            detections.append(
                {
                    "box": box,
                    "text": text,
                    "center_x": (x1 + x2) // 2,
                    "center_y": (y1 + y2) // 2,
                }
            )
        return detections
