"""Tests for the click captcha solver."""

import numpy as np
import pytest
from PIL import Image

from nexus_verify.preprocessing import pil_to_cv2
from nexus_verify.providers.click_features import (
    cosine_similarity,
    extract_click_feature,
)
from nexus_verify.providers.click_solver import ClickCaptchaSolver, FontLibrary

ddddocr = pytest.importorskip("ddddocr")


class FakeOcr:
    """Fake ddddocr for deterministic tests."""

    def __init__(self, boxes: list[list[int]], texts: list[str]) -> None:
        self._boxes = boxes
        self._texts = texts
        self._call_count = 0

    def detection(self, image: Image.Image) -> list[list[int]]:
        self._call_count = 0
        return self._boxes

    def classification(self, image: bytes) -> str:
        idx = self._call_count // 5
        self._call_count += 1
        return self._texts[idx]


class FakeFontLibrary:
    """Font library that returns pre-computed variants."""

    def __init__(self, variants: dict[str, list]) -> None:
        self._variants = variants

    def render_variants(self, char: str) -> list:
        return self._variants.get(char, [])

    @property
    def available(self) -> bool:
        return True


def test_cosine_similarity_identical() -> None:
    image = np.zeros((32, 32), dtype=np.uint8)
    image[8:24, 8:24] = 255
    arr = extract_click_feature(image)
    assert cosine_similarity(arr, arr) == pytest.approx(1.0, abs=0.01)


def test_extract_click_feature_shape() -> None:
    image = Image.new("L", (64, 64), 128)
    feat = extract_click_feature(image)
    assert len(feat) == 324


def test_font_library_empty_when_no_fonts() -> None:
    lib = FontLibrary(font_dirs=[])
    assert lib.available is False
    assert lib.render_variants("测") == []


def test_click_solver_with_ocr_bonus() -> None:
    # Three boxes, OCR already matches the target in order.
    boxes = [[0, 0, 30, 30], [40, 0, 70, 30], [80, 0, 110, 30]]
    image = Image.new("RGB", (120, 40), (255, 255, 255))
    ocr = FakeOcr(boxes, ["碍", "蹦", "崩"] * 5)
    solver = ClickCaptchaSolver(ocr, ocr, font_library=FakeFontLibrary({}))  # type: ignore[arg-type]
    points = solver.solve(pil_to_cv2(image), "碍蹦崩")
    assert points == [(15, 15), (55, 15), (95, 15)]


def test_click_solver_no_detections() -> None:
    image = Image.new("RGB", (100, 100), (255, 255, 255))
    ocr = FakeOcr([], [])
    solver = ClickCaptchaSolver(ocr, ocr, font_library=FakeFontLibrary({}))  # type: ignore[arg-type]
    with pytest.raises(Exception):
        solver.solve(image, "碍")


def test_click_solver_not_enough_detections() -> None:
    image = Image.new("RGB", (100, 100), (255, 255, 255))
    ocr = FakeOcr([[0, 0, 10, 10]], ["x"] * 5)
    solver = ClickCaptchaSolver(ocr, ocr, font_library=FakeFontLibrary({}))  # type: ignore[arg-type]
    with pytest.raises(Exception):
        solver.solve(image, "abc")


def test_click_solver_merge_overlapping_boxes() -> None:
    raw = [[0, 0, 30, 30], [15, 0, 45, 30]]
    merged = ClickCaptchaSolver._merge_boxes(raw)
    assert merged == [[0, 0, 45, 30]]


def test_click_solver_no_merge_distant_boxes() -> None:
    raw = [[0, 0, 20, 20], [40, 0, 60, 20]]
    merged = ClickCaptchaSolver._merge_boxes(raw)
    assert merged == raw
