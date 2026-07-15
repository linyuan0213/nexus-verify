"""Click-captcha solver combining ddddocr detection, OCR voting and visual matching."""

import glob
import io
import itertools
import os
from collections import Counter
from typing import Any

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

from nexus_verify.core.exceptions import RecognitionError
from nexus_verify.preprocessing import cv2_to_pil
from nexus_verify.providers.click_features import (
    cosine_similarity,
    extract_click_feature,
)

FEAT_SIZE = 32


def _preprocess_for_hog(image: Image.Image) -> np.ndarray:
    gray = np.array(image.convert("L"))
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(4, 4))
    enhanced = clahe.apply(gray)
    binary = cv2.adaptiveThreshold(enhanced, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2)
    if (binary == 0).sum() < (binary == 255).sum():
        binary = 255 - binary
    resized = cv2.resize(binary, (FEAT_SIZE, FEAT_SIZE), interpolation=cv2.INTER_LANCZOS4)
    return resized.astype(np.float32) / 255.0


_FONT_PATTERNS = [
    "PingFang",
    "STHeiti",
    "Songti",
    "Hiragino Sans GB",
    "Kaiti",
    "Baoli",
    "Hanzipen",
    "Lantinghei",
    "Libian",
    "Weibei",
    "Wawati",
    "Xingkai",
    "Yuanti",
    "Yuppy",
    "Heiti",
    "Fangsong",
    "Arial Unicode",
    "Noto",
    "SourceHan",
    "WenQuanYi",
    "DroidSansFallback",
]


def _pil_to_bytes(image: Image.Image) -> bytes:
    buf = io.BytesIO()
    image.save(buf, format="PNG")
    return buf.getvalue()


class FontLibrary:
    """Discovers and renders Chinese fonts for visual matching."""

    def __init__(self, font_dirs: list[str] | None = None) -> None:
        self._fonts: list[tuple[str, int]] = []
        self._font_cache: dict[tuple[str, int, int], ImageFont.FreeTypeFont | None] = {}
        self._variant_cache: dict[str, list[np.ndarray]] = {}
        self._font_dirs = self._default_font_dirs() if font_dirs is None else font_dirs
        self._scan()

    @staticmethod
    def _default_font_dirs() -> list[str]:
        dirs = [
            "/System/Library/Fonts",
            "/Library/Fonts",
            "~/Library/Fonts",
            "/usr/share/fonts",
            "/usr/local/share/fonts",
            "~/.fonts",
            "~/.local/share/fonts",
        ]
        return [os.path.expanduser(d) for d in dirs if os.path.isdir(os.path.expanduser(d))]

    def _scan(self) -> None:
        for directory in self._font_dirs:
            pattern = os.path.join(directory, "**", "*.tt[cf]")
            for path in glob.glob(pattern, recursive=True):
                if not any(p.lower() in os.path.basename(path).lower() for p in _FONT_PATTERNS):
                    continue
                for idx in range(8):
                    try:
                        font = ImageFont.truetype(path, 40, index=idx)
                    except Exception:
                        break
                    try:
                        cn_bb = font.getbbox("测")
                    except Exception:
                        continue
                    if cn_bb is None:
                        continue
                    cn_w = cn_bb[2] - cn_bb[0]
                    if cn_w >= 20:
                        self._fonts.append((path, idx))
                        break

    def _get_font(self, path: str, idx: int, size: int) -> ImageFont.FreeTypeFont | None:
        key = (path, idx, size)
        if key not in self._font_cache:
            try:
                self._font_cache[key] = ImageFont.truetype(path, size, index=idx)
            except Exception:
                self._font_cache[key] = None
        return self._font_cache[key]

    def render_variants(self, char: str) -> list[np.ndarray]:
        if char in self._variant_cache:
            return self._variant_cache[char]
        variants: list[np.ndarray] = []
        for size in [30, 36, 42]:
            for path, idx in self._fonts:
                font = self._get_font(path, idx, size)
                if font is None:
                    continue
                for angle in [-25, -15, 0, 15, 25]:
                    canvas = size + 30
                    img = Image.new("L", (canvas, canvas), 0)
                    draw = ImageDraw.Draw(img)
                    draw.text((15, 10), char, fill=255, font=font)
                    bbox = img.getbbox()
                    if bbox:
                        img = img.crop(bbox)
                    if angle != 0:
                        img = img.rotate(angle, fillcolor=0, expand=False)
                    img = img.resize((FEAT_SIZE, FEAT_SIZE), Image.Resampling.LANCZOS)
                    arr = np.array(img, dtype=np.float32) / 255.0
                    variants.append(arr)
        self._variant_cache[char] = variants
        return variants

    @property
    def available(self) -> bool:
        return len(self._fonts) > 0


class ClickCaptchaSolver:
    """Solve Chinese click-captcha by visual matching and OCR voting."""

    def __init__(
        self,
        det_ocr: Any,
        cls_ocr: Any,
        font_library: FontLibrary | None = None,
    ) -> None:
        self.det_ocr = det_ocr
        self.cls_ocr = cls_ocr
        self.fonts = font_library or FontLibrary()

    def solve(self, image: Any, target: str) -> list[tuple[int, int]]:
        pil_image = cv2_to_pil(image)
        detections = self._detect(pil_image)
        if not detections:
            raise RecognitionError("No clickable targets detected")
        return self._assign(pil_image, detections, target)

    @staticmethod
    def _merge_boxes(boxes: list[list[int]]) -> list[list[int]]:
        """Merge detection boxes that overlap significantly."""
        if not boxes:
            return boxes
        sorted_boxes = sorted(boxes, key=lambda b: b[0])
        merged: list[list[int]] = [sorted_boxes[0]]
        for box in sorted_boxes[1:]:
            last = merged[-1]
            x1 = max(box[0], last[0])
            y1 = max(box[1], last[1])
            x2 = min(box[2], last[2])
            y2 = min(box[3], last[3])
            inter = max(0, x2 - x1) * max(0, y2 - y1)
            if inter == 0:
                merged.append(box)
                continue
            area_box = (box[2] - box[0]) * (box[3] - box[1])
            area_last = (last[2] - last[0]) * (last[3] - last[1])
            union = area_box + area_last - inter
            iou = inter / union if union > 0 else 0
            if iou >= 0.15 or inter / min(area_box, area_last) >= 0.3:
                merged[-1] = [
                    min(box[0], last[0]),
                    min(box[1], last[1]),
                    max(box[2], last[2]),
                    max(box[3], last[3]),
                ]
            else:
                merged.append(box)
        return merged

    def _detect(self, pil_image: Image.Image) -> list[dict[str, Any]]:
        boxes = self._merge_boxes(self.det_ocr.detection(pil_image))
        detections = []
        for box in boxes:
            x1, y1, x2, y2 = box
            crop = pil_image.crop((x1, y1, x2, y2))
            char, confidence, all_chars = self._ocr_ensemble(crop)
            detections.append(
                {
                    "box": box,
                    "char": char,
                    "confidence": confidence,
                    "all_chars": all_chars,
                    "center": ((x1 + x2) // 2, (y1 + y2) // 2),
                    "feat": extract_click_feature(_preprocess_for_hog(crop)),
                }
            )
        return detections

    def _ocr_ensemble(self, crop: Image.Image) -> tuple[str, float, set[str]]:
        gray = np.array(crop.convert("L"))
        results: list[str] = []
        results.append(self.cls_ocr.classification(_pil_to_bytes(crop)))
        _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        results.append(self.cls_ocr.classification(_pil_to_bytes(Image.fromarray(binary))))
        clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(4, 4))
        results.append(self.cls_ocr.classification(_pil_to_bytes(Image.fromarray(clahe.apply(gray)))))
        results.append(self.cls_ocr.classification(_pil_to_bytes(Image.fromarray(255 - gray))))
        blurred = cv2.GaussianBlur(gray, (3, 3), 0)
        _, binary2 = cv2.threshold(blurred, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        results.append(self.cls_ocr.classification(_pil_to_bytes(Image.fromarray(binary2))))
        counter = Counter(results)
        char, count = counter.most_common(1)[0]
        return char, count / len(results), set(results)

    def _assign(
        self,
        pil_image: Image.Image,
        detections: list[dict[str, Any]],
        target: str,
    ) -> list[tuple[int, int]]:
        n = len(target)
        m = len(detections)
        if n > m:
            raise RecognitionError(f"Need {n} targets but only {m} detected")
        min_dist = min(pil_image.width, pil_image.height) * 0.10
        prompt_vars = {ch: self.fonts.render_variants(ch) for ch in set(target)}
        score = [[0.0] * m for _ in range(n)]
        for i, ch in enumerate(target):
            variants = prompt_vars[ch]
            for j, det in enumerate(detections):
                img_sim = self._best_variant_sim(variants, det["feat"])
                ocr_bonus = 0.0
                if det["char"] == ch:
                    ocr_bonus = 0.3 * det["confidence"]
                elif ch in det["all_chars"]:
                    ocr_bonus = 0.1
                score[i][j] = img_sim + ocr_bonus
        best = self._search_permutation(detections, score, min_dist)
        return [detections[i]["center"] for i in best]

    def _best_variant_sim(self, variants: list[np.ndarray], feat: np.ndarray) -> float:
        if not variants:
            return 0.0
        return max(cosine_similarity(extract_click_feature(v), feat) for v in variants)

    def _search_permutation(
        self,
        detections: list[dict[str, Any]],
        score: list[list[float]],
        min_dist: float,
    ) -> tuple[int, ...]:
        n = len(score)
        m = len(score[0])
        best_total = -float("inf")
        best_perm = None
        for perm in itertools.permutations(range(m), n):
            ok = True
            for i in range(n):
                for j in range(i + 1, n):
                    if self._dist(detections[perm[i]], detections[perm[j]]) < min_dist:
                        ok = False
                        break
                if not ok:
                    break
            if not ok:
                continue
            total = sum(score[i][perm[i]] for i in range(n))
            if total > best_total:
                best_total = total
                best_perm = perm
        if best_perm is None:
            for perm in itertools.permutations(range(m), n):
                total = sum(score[i][perm[i]] for i in range(n))
                if total > best_total:
                    best_total = total
                    best_perm = perm
        if best_perm is None:
            raise RecognitionError("No valid assignment found")
        return best_perm

    @staticmethod
    def _dist(a: dict[str, Any], b: dict[str, Any]) -> float:
        ax, ay = a["center"]
        bx, by = b["center"]
        return ((ax - bx) ** 2 + (ay - by) ** 2) ** 0.5
