"""Tests for the slide/gap provider."""

import base64
from io import BytesIO

import cv2
import numpy as np
import pytest
from PIL import Image

from nexus_verify.core.task import TaskType, VerifyTask
from nexus_verify.providers.slide import SlideProvider


def _make_b64(image: Image.Image) -> str:
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return base64.b64encode(buffer.getvalue()).decode("utf-8")


def _cv2_image(image: Image.Image) -> np.ndarray:
    return cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)


@pytest.fixture
def provider() -> SlideProvider:
    return SlideProvider()


def _white_image(width: int, height: int) -> Image.Image:
    return Image.new("RGB", (width, height), (255, 255, 255))


def test_crop_slider_extracts_square_piece(provider: SlideProvider) -> None:
    """A square puzzle piece should be selected over a flat distractor."""
    composite = _white_image(300, 100)
    pixels = composite.load()
    assert pixels is not None

    # Blue distractor: wide rectangle at the left.
    for x in range(10, 80):
        for y in range(30, 60):
            pixels[x, y] = (0, 0, 255)

    # Real puzzle piece: square at the right.
    for x in range(150, 220):
        for y in range(20, 90):
            pixels[x, y] = (100, 100, 100)

    slider = _cv2_image(composite)
    cropped, offset = provider._crop_slider(slider)

    assert offset == 150
    assert cropped.shape[:2] == (70, 70)


def test_crop_slider_returns_full_image_when_no_content(
    provider: SlideProvider,
) -> None:
    """A fully white image should fall back to the original image."""
    slider = _cv2_image(_white_image(100, 100))
    cropped, offset = provider._crop_slider(slider)
    assert offset == 0
    assert cropped.shape == slider.shape


def _pattern_image(width: int, height: int, base_color: tuple[int, int, int]) -> Image.Image:
    image = Image.new("RGB", (width, height), base_color)
    pixels = image.load()
    assert pixels is not None
    for y in range(0, height, 10):
        for x in range(0, width, 10):
            if (x // 10 + y // 10) % 2 == 0:
                pixels[x, y] = (0, 0, 0)
    return image


def test_match_slider_applies_offset_correction(provider: SlideProvider, monkeypatch: pytest.MonkeyPatch) -> None:
    """Distance should be reduced by the signed slider offset."""
    monkeypatch.setattr(provider, "_ddddocr_match", lambda _bg, _slider: None)

    background = _cv2_image(Image.new("RGB", (300, 100), (0, 0, 0)))
    # Draw a unique patterned block so matchTemplate has a single best match.
    pattern = _pattern_image(70, 70, (100, 100, 100))
    background[30:100, 200:270] = _cv2_image(pattern)

    slider = _cv2_image(pattern)

    # Without offset: distance equals the gap x-coordinate.
    result_no_offset = provider._match_slider(background, slider)
    assert result_no_offset.distance == 200
    assert result_no_offset.points == [(200, 30)]

    # With offset -150: distance is 200 - 150 = 50.
    result_with_offset = provider._match_slider(background, slider, -150)
    assert result_with_offset.distance == 50
    assert result_with_offset.points == [(200, 30)]


@pytest.mark.asyncio
async def test_verify_slide_captcha_requires_slider_b64(provider: SlideProvider) -> None:
    """Missing slider_b64 should raise an error."""
    task = VerifyTask(task_type=TaskType.SLIDE_CAPTCHA, image_b64=_make_b64(_white_image(100, 100)))
    with pytest.raises(Exception):  # ImageDecodeError
        await provider.verify(task)


def test_fit_to_background_does_not_enlarge_small_slider(
    provider: SlideProvider,
) -> None:
    """Small sliders that already fit should not be resized."""
    background = np.zeros((100, 200, 3), dtype=np.uint8)
    slider = np.zeros((30, 30, 3), dtype=np.uint8)
    fitted = provider._fit_to_background(slider, background)
    assert fitted.shape == (30, 30, 3)


def test_fit_to_background_scales_large_slider(provider: SlideProvider) -> None:
    """Oversized sliders should be scaled down to fit the background."""
    background = np.zeros((100, 200, 3), dtype=np.uint8)
    slider = np.zeros((150, 250, 3), dtype=np.uint8)
    fitted = provider._fit_to_background(slider, background)
    assert fitted.shape[0] <= 100
    assert fitted.shape[1] <= 200
