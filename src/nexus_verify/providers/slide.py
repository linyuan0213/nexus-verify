"""OpenCV/ddddocr-based provider for slide and gap tasks."""

import base64
import io
from typing import Any

import cv2
import ddddocr
import numpy as np
from PIL import Image

from nexus_verify.core.exceptions import ImageDecodeError, RecognitionError
from nexus_verify.core.result import VerifyResult
from nexus_verify.core.task import TaskType, VerifyTask
from nexus_verify.preprocessing import grayscale, load_image
from nexus_verify.providers.base import Provider


def _decode_base64_rgba(image_b64: str) -> np.ndarray:
    """Decode base64 image and return OpenCV BGRA ndarray, preserving alpha."""
    raw = base64.b64decode(image_b64.encode("utf-8"))
    image = Image.open(io.BytesIO(raw))
    if image.mode == "RGBA":
        return cv2.cvtColor(np.array(image), cv2.COLOR_RGBA2BGRA)
    return cv2.cvtColor(np.array(image.convert("RGB")), cv2.COLOR_RGB2BGR)


class SlideProvider(Provider):
    """Provider using OpenCV or ddddocr for slide/gap tasks."""

    name = "slide"
    tasks = {TaskType.SLIDE_CAPTCHA, TaskType.GAP_MATCH}

    @property
    def available(self) -> bool:
        return True

    async def verify(self, task: VerifyTask) -> VerifyResult:
        background = load_image(task)

        if task.task_type == TaskType.SLIDE_CAPTCHA:
            slider, slider_offset = self._crop_slider(self._load_slider(task))
            # slider_offset is the positive distance from the background left edge
            # to the slider piece's left edge; the correction offset is negative.
            return self._match_slider(background, slider, -slider_offset)

        if task.task_type == TaskType.GAP_MATCH:
            piece, _ = self._crop_slider(self._load_slider(task))
            return self._match_slider(background, piece)

        raise RecognitionError(f"Unsupported task type: {task.task_type}")

    def _load_slider(self, task: VerifyTask) -> Any:
        extra = task.extra or {}
        slider_b64 = extra.get("slider_b64")
        if not slider_b64:
            raise ImageDecodeError("slide_captcha requires extra.slider_b64")
        return _decode_base64_rgba(slider_b64)

    def _crop_slider(self, slider: np.ndarray) -> tuple[np.ndarray, int]:
        """Crop composite slider images to the actual puzzle piece.

        Some captcha composites contain multiple UI elements (e.g. a blue
        drag handle and the real puzzle piece). This method finds the most
        square-ish large contour in the non-white region and returns that
        as the slider piece, along with the piece's x-offset in the original
        composite image.
        """
        # RGBA composites: use the alpha channel to locate the puzzle piece.
        if slider.shape[2] == 4:
            alpha = slider[:, :, 3]
            _, binary = cv2.threshold(alpha, 20, 255, cv2.THRESH_BINARY)
            coords = cv2.findNonZero(binary)
            if coords is not None:
                x, y, w, h = cv2.boundingRect(coords)
                strip = slider[y : y + h, x : x + w]
                return strip, x

        gray = cv2.cvtColor(slider, cv2.COLOR_BGR2GRAY)
        _, binary = cv2.threshold(gray, 250, 255, cv2.THRESH_BINARY_INV)
        coords = cv2.findNonZero(binary)
        if coords is None:
            return slider, 0

        x, y, w, h = cv2.boundingRect(coords)
        strip = slider[y : y + h, x : x + w]
        strip_gray = gray[y : y + h, x : x + w]
        _, strip_bin = cv2.threshold(strip_gray, 250, 255, cv2.THRESH_BINARY_INV)
        contours, _ = cv2.findContours(strip_bin, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        best_piece: tuple[int, int, int, int] | None = None
        best_score = float("inf")
        for c in contours:
            cx, cy, cw, ch = cv2.boundingRect(c)
            area = cv2.contourArea(c)
            if area < 1000:
                continue
            # The puzzle piece is roughly square, while distractors such as
            # drag handles tend to be wide ovals. Prefer the contour whose
            # aspect ratio is closest to 1:1.
            aspect_ratio = max(cw, ch) / max(min(cw, ch), 1)
            score = abs(aspect_ratio - 1.0)
            if score < best_score:
                best_score = score
                best_piece = (cx, cy, cw, ch)

        if best_piece is None:
            return strip, x

        cx, cy, cw, ch = best_piece
        return (
            slider[y + cy : y + cy + ch, x + cx : x + cx + cw],
            x + cx,
        )

    def _fit_to_background(self, slider: np.ndarray, background: np.ndarray) -> np.ndarray:
        """Resize slider so it fits inside the background for template matching."""
        bh, bw = background.shape[:2]
        sh, sw = slider.shape[:2]
        if sh <= bh and sw <= bw:
            return slider
        scale = min((bw - 1) / sw, (bh - 1) / sh)
        new_w = max(1, int(sw * scale))
        new_h = max(1, int(sh * scale))
        return cv2.resize(slider, (new_w, new_h), interpolation=cv2.INTER_AREA)

    def _match_slider(self, background: np.ndarray, slider: np.ndarray, slider_offset: int = 0) -> VerifyResult:
        slider = self._fit_to_background(slider, background)
        # Run ddddocr and OpenCV multi-scale in parallel and keep the result
        # with the highest reported confidence. The scaled puzzle piece often
        # matches the gap better than the raw sprite size for these captchas.
        ddddocr_result = self._ddddocr_match(background, slider)
        best_result = self._opencv_match(background, slider)
        best_confidence = best_result.confidence or 0.0
        for scale in (1.0, 1.03, 1.05, 1.08, 0.97, 0.95, 1.1, 0.9, 1.15):
            scaled = self._resize_slider(slider, scale, background)
            if scaled is None:
                continue
            result = self._opencv_match(background, scaled)
            result_confidence = result.confidence or 0.0
            if result_confidence > best_confidence:
                best_confidence = result_confidence
                best_result = result
        if ddddocr_result is not None:
            ddddocr_confidence = ddddocr_result.confidence or 0.0
            if ddddocr_confidence > best_confidence:
                best_result = ddddocr_result
                best_confidence = ddddocr_confidence

        # Correct the distance for captchas where the slider piece in the
        # composite image is not at the left edge of the background. The
        # offset is the signed distance from the background left edge to the
        # slider piece's left edge.
        points = best_result.points or [(0, 0)]
        x = int(points[0][0])
        y = int(points[0][1])
        distance = max(0, x + slider_offset)
        return VerifyResult(distance=distance, points=[(x, y)], confidence=best_confidence)

    def _resize_slider(self, slider: np.ndarray, scale: float, background: np.ndarray) -> np.ndarray | None:
        sh, sw = slider.shape[:2]
        new_h = max(1, int(sh * scale))
        new_w = max(1, int(sw * scale))
        if new_h > background.shape[0] or new_w > background.shape[1]:
            return None
        return cv2.resize(slider, (new_w, new_h), interpolation=cv2.INTER_LINEAR)

    def _ddddocr_match(self, background: np.ndarray, slider: np.ndarray) -> VerifyResult | None:
        try:
            slide = ddddocr.DdddOcr(det=False, ocr=False, show_ad=False)
            bg_bytes = self._cv2_to_bytes(background)
            slider_bytes = self._cv2_to_bytes(slider)
            res = slide.slide_match(slider_bytes, bg_bytes, simple_target=True)
            x = int(res.get("target_x", 0))
            y = int(res.get("target_y", 0))
            conf = float(res.get("confidence", 0.0))
            return VerifyResult(distance=x, points=[(x, y)], confidence=conf)
        except Exception:
            return None

    def _opencv_match(self, background: np.ndarray, slider: np.ndarray) -> VerifyResult:
        bg_gray = grayscale(background)
        slider_gray = grayscale(slider)

        if slider_gray.shape[0] > bg_gray.shape[0] or slider_gray.shape[1] > bg_gray.shape[1]:
            raise RecognitionError("Slider image is larger than background")

        result = cv2.matchTemplate(bg_gray, slider_gray, cv2.TM_CCOEFF_NORMED)
        _, max_val, _, max_loc = cv2.minMaxLoc(result)
        x = max_loc[0]
        y = max_loc[1]
        return VerifyResult(distance=x, points=[(x, y)], confidence=float(max_val))

    @staticmethod
    def _cv2_to_bytes(image: np.ndarray) -> bytes:
        _, encoded = cv2.imencode(".png", image)
        return io.BytesIO(encoded).getvalue()
