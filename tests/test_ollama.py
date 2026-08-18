import json
from collections.abc import Sequence
from io import BytesIO
from urllib.error import HTTPError, URLError

import pytest

from atosaac_virtual_partner.message import Message, MessageRole
from atosaac_virtual_partner.providers import ollama
from atosaac_virtual_partner.providers.ollama import OllamaReplyProvider
from atosaac_virtual_partner.reply import (
    CancellationToken,
    ReplyCancelled,
    ReplyProviderError,
)


class FakeResponse:
    def __init__(self, events: Sequence[object | bytes]) -> None:
        self._lines = tuple(
            event
            if isinstance(event, bytes)
            else f"{json.dumps(event)}\n".encode("utf-8")
            for event in events
        )

    def __enter__(self) -> "FakeResponse":
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def __iter__(self):
        return iter(self._lines)


def test_ollama_provider_streams_conversation_context(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def fake_urlopen(request, timeout):
        captured["request"] = request
        captured["timeout"] = timeout
        return FakeResponse(
            (
                {
                    "message": {"role": "assistant", "content": "你好"},
                    "done": False,
                },
                {
                    "message": {"role": "assistant", "content": "呀。"},
                    "done": False,
                },
                {
                    "message": {"role": "assistant", "content": ""},
                    "done": True,
                },
            )
        )

    monkeypatch.setattr(ollama, "urlopen", fake_urlopen)
    provider = OllamaReplyProvider(
        model="qwen3:4b-instruct",
        base_url="http://127.0.0.1:11434/api",
        timeout_seconds=30,
    )

    chunks = list(
        provider.stream_reply(
            (
                Message(MessageRole.SYSTEM, "Be playful."),
                Message(MessageRole.USER, "你好"),
            )
        )
    )

    request = captured["request"]
    payload = json.loads(request.data.decode("utf-8"))
    assert request.full_url == "http://127.0.0.1:11434/api/chat"
    assert captured["timeout"] == 30
    assert payload == {
        "model": "qwen3:4b-instruct",
        "messages": [
            {"role": "system", "content": "Be playful."},
            {"role": "user", "content": "你好"},
        ],
        "stream": True,
        "think": False,
    }
    assert request.get_header("Accept") == "application/x-ndjson"
    assert chunks == ["你好", "呀。"]


def test_ollama_provider_does_not_return_separate_thinking(monkeypatch) -> None:
    def fake_urlopen(_request, timeout):
        return FakeResponse(
            (
                {
                    "message": {
                        "role": "assistant",
                        "thinking": "internal reasoning",
                        "content": "只返回最终回复。",
                    },
                    "done": False,
                },
                {
                    "message": {"role": "assistant", "content": ""},
                    "done": True,
                },
            )
        )

    monkeypatch.setattr(ollama, "urlopen", fake_urlopen)
    provider = OllamaReplyProvider(model="qwen3:4b-instruct")

    reply = provider.generate_reply((Message(MessageRole.USER, "hello"),))

    assert reply == "只返回最终回复。"


def test_ollama_provider_reports_api_error(monkeypatch) -> None:
    def fail_with_http_error(request, timeout):
        raise HTTPError(
            request.full_url,
            404,
            "Not Found",
            {},
            BytesIO(b'{"error":"model not found"}'),
        )

    monkeypatch.setattr(ollama, "urlopen", fail_with_http_error)
    provider = OllamaReplyProvider(model="missing")

    with pytest.raises(ReplyProviderError, match="HTTP 404: model not found"):
        list(provider.stream_reply((Message(MessageRole.USER, "hello"),)))


def test_ollama_provider_reports_connection_error(monkeypatch) -> None:
    def fail_to_connect(_request, timeout):
        raise URLError("connection refused")

    monkeypatch.setattr(ollama, "urlopen", fail_to_connect)
    provider = OllamaReplyProvider(model="qwen3:4b-instruct")

    with pytest.raises(ReplyProviderError, match="Cannot connect to Ollama"):
        list(provider.stream_reply((Message(MessageRole.USER, "hello"),)))


def test_ollama_provider_reports_midstream_error(monkeypatch) -> None:
    def fake_urlopen(_request, timeout):
        return FakeResponse(
            (
                {
                    "message": {"role": "assistant", "content": "一半"},
                    "done": False,
                },
                {"error": "generation failed"},
            )
        )

    monkeypatch.setattr(ollama, "urlopen", fake_urlopen)
    provider = OllamaReplyProvider(model="qwen3:4b-instruct")

    with pytest.raises(ReplyProviderError, match="generation failed"):
        list(provider.stream_reply((Message(MessageRole.USER, "hello"),)))


def test_ollama_provider_rejects_incomplete_stream(monkeypatch) -> None:
    def fake_urlopen(_request, timeout):
        return FakeResponse(
            (
                {
                    "message": {"role": "assistant", "content": "一半"},
                    "done": False,
                },
            )
        )

    monkeypatch.setattr(ollama, "urlopen", fake_urlopen)
    provider = OllamaReplyProvider(model="qwen3:4b-instruct")

    with pytest.raises(ReplyProviderError, match="before completion"):
        list(provider.stream_reply((Message(MessageRole.USER, "hello"),)))


def test_ollama_provider_honors_cancellation_before_request(monkeypatch) -> None:
    def unexpected_urlopen(_request, timeout):
        raise AssertionError("urlopen should not be called")

    monkeypatch.setattr(ollama, "urlopen", unexpected_urlopen)
    provider = OllamaReplyProvider(model="qwen3:4b-instruct")
    cancellation_token = CancellationToken()
    cancellation_token.cancel()

    with pytest.raises(ReplyCancelled):
        list(
            provider.stream_reply(
                (Message(MessageRole.USER, "hello"),),
                cancellation_token=cancellation_token,
            )
        )


@pytest.mark.parametrize(
    "base_url",
    ["localhost:11434", "ftp://localhost:11434", "http://localhost:11434/v1"],
)
def test_ollama_provider_rejects_invalid_url(base_url: str) -> None:
    with pytest.raises(ValueError, match="Ollama URL"):
        OllamaReplyProvider(model="qwen3:4b-instruct", base_url=base_url)
