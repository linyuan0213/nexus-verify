"""DdddOcr-based provider for captcha and OCR tasks."""

import base64
import collections
import re
from typing import Any

import cv2
import ddddocr
import numpy as np

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
            if task.extra and task.extra.get("ensemble"):
                return VerifyResult(text=self._recognize_ensemble(image, ocr, task.image_b64))
            return self._recognize_captcha(image, ocr, task.extra, task.image_b64)

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
        self,
        image: Any,
        ocr: Any,
        extra: dict[str, Any] | None,
        raw_b64: str | None = None,
    ) -> VerifyResult:
        if extra and extra.get("line_remove"):
            text = self._recognize_without_line(image, ocr)
        elif extra and extra.get("raw") and raw_b64:
            # 部分验证码的干扰线/颜色在预处理后反而丢失字符，直接识别原图更稳
            text = ocr.classification(base64.b64decode(raw_b64))
        else:
            if extra is None or extra.get("preprocess", True):
                pil_image = preprocess_captcha(image, extra)
            else:
                pil_image = cv2_to_pil(image)
            text = ocr.classification(pil_image)
        text = text.replace("之", "2").replace(">", "7").upper()
        return VerifyResult(text=text)

    @staticmethod
    def _recognize_ensemble(image: Any, ocr: Any, raw_b64: str | None) -> str:
        """多预处理逐位投票，降低单次 OCR 的错字率."""
        variants: list[str] = []
        if raw_b64:
            try:
                raw = base64.b64decode(raw_b64)
                variants.append(ocr.classification(raw))
                beta = ddddocr.DdddOcr(show_ad=False, beta=True)
                variants.append(str(beta.classification(raw)))
            except Exception:  # noqa: BLE001, S110 - 单个变体失败不影响投票
                pass
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if len(image.shape) == 3 else image
        for candidate in (
            cv2.resize(gray, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC),
            cv2.resize(
                cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)[1],
                None,
                fx=2,
                fy=2,
                interpolation=cv2.INTER_CUBIC,
            ),
        ):
            try:
                variants.append(ocr.classification(cv2.imencode(".png", candidate)[1].tobytes()))
            except Exception:  # noqa: BLE001, S110
                continue
        try:
            variants.append(DdddOcrProvider._recognize_without_line(image, ocr))
        except Exception:  # noqa: BLE001, S110
            pass
        variants = [re.sub(r"[^A-Za-z0-9]", "", item).lower() for item in variants if item]
        variants = [item for item in variants if item]
        if not variants:
            return ""
        length = collections.Counter(len(item) for item in variants).most_common(1)[0][0]
        same_length = [item for item in variants if len(item) == length]
        return "".join(
            collections.Counter(item[index] for item in same_length).most_common(1)[0][0] for index in range(length)
        )

    @staticmethod
    def _recognize_without_line(image: Any, ocr: Any) -> str:
        """去除水平干扰线后按字符区域识别，适合细字体验证码."""
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if len(image.shape) == 3 else image
        _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
        width = max(15, binary.shape[1] // 12)
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (width, 1))
        line = cv2.morphologyEx(binary, cv2.MORPH_OPEN, kernel)
        clean = cv2.subtract(binary, line)
        ys, xs = np.where(clean > 0)
        if len(xs):
            clean = clean[ys.min() : ys.max() + 1, xs.min() : xs.max() + 1]
        clean = cv2.resize(clean, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)
        _, buffer = cv2.imencode(".png", 255 - clean)
        text = ocr.classification(buffer.tobytes())
        return re.sub(r"[^A-Za-z0-9]", "", str(text)).lower()

    def _recognize_click(self, image: Any, det_ocr: Any, cls_ocr: Any, target: str) -> VerifyResult:
        solver = ClickCaptchaSolver(det_ocr, cls_ocr)
        points = solver.solve(image, target)
        return VerifyResult(points=points)

    def _recognize_text(self, image: Any, det_ocr: Any, cls_ocr: Any) -> VerifyResult:
        detections = self._detect_and_classify(image, det_ocr, cls_ocr)
        texts = [det["text"] for det in detections]
        if texts:
            return VerifyResult(text="\n".join(texts))

        # 字幕/海报等大字号文本常无法被验证码检测模型框出，回退整图分类
        try:
            beta = ddddocr.DdddOcr(beta=True, show_ad=False)
            text = beta.classification(cv2_to_pil(image))
            return VerifyResult(text=text if isinstance(text, str) else "")
        except Exception as exc:
            raise RecognitionError(f"OCR failed: {exc}") from exc

    def _detect_and_classify(self, image: Any, det_ocr: Any, cls_ocr: Any) -> list[dict[str, Any]]:
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
