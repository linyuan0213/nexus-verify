"""Provider for image click-captcha tasks."""

import cv2
import ddddocr
import numpy as np
from PIL import Image

from nexus_verify.core.exceptions import ImageDecodeError, RecognitionError
from nexus_verify.core.result import VerifyResult
from nexus_verify.core.task import TaskType, VerifyTask
from nexus_verify.preprocessing import decode_base64, pil_to_cv2
from nexus_verify.providers.base import Provider
from nexus_verify.providers.image_click import matcher


class ImageClickProvider(Provider):
    """Provider using OpenCV and ddddocr for image click captchas."""

    name = "image_click"
    tasks = {TaskType.IMAGE_CLICK_CAPTCHA}

    def __init__(self) -> None:
        try:
            self._ocr = ddddocr.DdddOcr(show_ad=False)
        except Exception:
            self._ocr = None
        try:
            self._det_ocr = ddddocr.DdddOcr(det=True, ocr=False, show_ad=False)
        except Exception:
            self._det_ocr = None

    @property
    def available(self) -> bool:
        return True

    async def verify(self, task: VerifyTask) -> VerifyResult:
        background = pil_to_cv2(decode_base64(task.image_b64))
        target = self._load_target(task)

        target_icons = self._extract_target_icons(target)
        if not target_icons:
            raise RecognitionError("No target icons found in target image")

        candidates = self._detect_candidates(background)
        if not candidates:
            raise RecognitionError("No icon candidates detected in background")

        points = self._match_icons(target_icons, candidates, background)
        if not points:
            raise RecognitionError("Could not match target icons to background")

        return VerifyResult(points=points)

    def _load_target(self, task: VerifyTask) -> np.ndarray:
        extra = task.extra or {}
        target_b64 = extra.get("target_b64")
        if not target_b64:
            raise ImageDecodeError("image_click_captcha requires extra.target_b64")
        return pil_to_cv2(decode_base64(target_b64))

    def _extract_target_icons(self, target: np.ndarray) -> list[np.ndarray]:
        gray = cv2.cvtColor(target, cv2.COLOR_BGR2GRAY)
        _, binary = cv2.threshold(gray, 50, 255, cv2.THRESH_BINARY_INV)
        vproj = binary.sum(axis=0)

        threshold = vproj.max() * 0.1
        active = vproj > threshold
        if not active.any():
            raise RecognitionError("No target icons found in target image")

        icons = []
        in_icon = False
        start = 0
        for col, is_active in enumerate(active):
            if is_active and not in_icon:
                in_icon = True
                start = col
            elif not is_active and in_icon:
                in_icon = False
                if col - start >= 8:
                    icons.append(target[:, start:col])

        if in_icon and len(active) - start >= 8:
            icons.append(target[:, start:])

        if len(icons) >= 2:
            return icons

        num_parts = 3
        part_width = target.shape[1] // num_parts
        return [
            target[:, i * part_width : (i + 1) * part_width]
            for i in range(num_parts)
        ]

    def _detect_candidates(self, background: np.ndarray) -> list[tuple[int, int, int, int]]:
        candidates: list[tuple[int, int, int, int]] = []
        seen: set[tuple[int, int, int, int]] = set()

        binary = (
            (background[:, :, 0] < 30)
            & (background[:, :, 1] < 30)
            & (background[:, :, 2] < 30)
        ).astype(np.uint8) * 255
        contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        for c in contours:
            x, y, w, h = cv2.boundingRect(c)
            area = cv2.contourArea(c)
            if not (100 < area < 8000 and 20 <= w <= 160 and 20 <= h <= 160):
                continue
            key = (round(x / 5), round(y / 5), round(w / 5), round(h / 5))
            if key in seen:
                continue
            seen.add(key)
            candidates.append((x, y, w, h))

        return candidates

    def _recognize_icon(self, icon: np.ndarray) -> str:
        if self._ocr is None:
            return ""
        gray = cv2.cvtColor(icon, cv2.COLOR_BGR2GRAY)
        _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        coords = cv2.findNonZero(binary)
        if coords is not None:
            x, y, w, h = cv2.boundingRect(coords)
            cropped = binary[y : y + h, x : x + w]
        else:
            cropped = binary
        target_size = 64
        h, w = cropped.shape
        scale = min(target_size / w, target_size / h)
        new_w = max(1, int(w * scale))
        new_h = max(1, int(h * scale))
        resized = cv2.resize(cropped, (new_w, new_h))
        canvas = np.full((target_size, target_size), 255, dtype=np.uint8)
        y_off = (target_size - new_h) // 2
        x_off = (target_size - new_w) // 2
        canvas[y_off : y_off + new_h, x_off : x_off + new_w] = resized
        image = Image.fromarray(canvas).convert("RGB")
        try:
            return str(self._ocr.classification(image)).strip().lower()
        except Exception:
            return ""

    def _get_outer_contour(self, mask: np.ndarray, kernel_size: int = 3) -> np.ndarray | None:
        mask_u8 = (mask * 255).astype(np.uint8)
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (kernel_size, kernel_size))
        closed = cv2.morphologyEx(mask_u8, cv2.MORPH_CLOSE, kernel)
        contours, _ = cv2.findContours(closed, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not contours:
            return None
        return max(contours, key=cv2.contourArea)

    def _mask_correlation(self, a: np.ndarray, b: np.ndarray) -> float:
        h = max(a.shape[0], b.shape[0])
        w = max(a.shape[1], b.shape[1])
        a_r = cv2.resize(a.astype(np.uint8), (w, h)) > 0
        b_r = cv2.resize(b.astype(np.uint8), (w, h)) > 0
        a_flat = a_r.flatten().astype(np.float32)
        b_flat = b_r.flatten().astype(np.float32)
        if a_flat.std() == 0 or b_flat.std() == 0:
            return 0.0
        return float(np.corrcoef(a_flat, b_flat)[0, 1])

    def _match_icons(
        self,
        target_icons: list[np.ndarray],
        candidates: list[tuple[int, int, int, int]],
        background: np.ndarray,
    ) -> list[tuple[int, int]]:
        return matcher.match_icons(self, target_icons, candidates, background)
