"""Vision provider tests using a local OpenAI-compatible mock endpoint."""

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from nexus_verify.config import settings
from nexus_verify.core.exceptions import RecognitionError
from nexus_verify.core.task import TaskType, VerifyTask
from nexus_verify.providers.vision import VisionProvider, clean_captcha_text


class _Handler(BaseHTTPRequestHandler):
    answer = "```text\nAB12\n```"

    def do_POST(self) -> None:  # noqa: N802
        length = int(self.headers.get("Content-Length", "0"))
        body = json.loads(self.rfile.read(length) or b"{}")
        assert body["model"] == "test-vl"
        payload = {
            "choices": [{"message": {"content": self.answer}}],
            "usage": {"total_tokens": 12},
        }
        data = json.dumps(payload).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *_args) -> None:
        return


@pytest.fixture()
def mock_vision(monkeypatch):
    server = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    monkeypatch.setattr(settings, "vision_api_url", f"http://127.0.0.1:{server.server_port}/v1/chat/completions")
    monkeypatch.setattr(settings, "vision_api_key", "test-key")
    monkeypatch.setattr(settings, "vision_model", "test-vl")
    yield
    server.shutdown()
    server.server_close()


def test_clean_captcha_text() -> None:
    assert clean_captcha_text("```\nAb12\n```") == "ab12"
    assert clean_captcha_text('"x y z"') == "xyz"


@pytest.mark.asyncio
async def test_vision_provider(mock_vision) -> None:
    provider = VisionProvider()
    assert provider.available
    result = await provider.verify(VerifyTask(task_type=TaskType.CAPTCHA, image_b64="aGVsbG8=", extra={"length": 5}))
    assert result.text == "ab12"
    assert result.raw and result.raw["model"] == "test-vl"


@pytest.mark.asyncio
async def test_vision_provider_unavailable(monkeypatch) -> None:
    monkeypatch.setattr(settings, "vision_api_url", "")
    monkeypatch.setattr(settings, "vision_api_key", "")
    with pytest.raises(RecognitionError):
        await VisionProvider().verify(VerifyTask(task_type=TaskType.CAPTCHA, image_b64="aGVsbG8="))
