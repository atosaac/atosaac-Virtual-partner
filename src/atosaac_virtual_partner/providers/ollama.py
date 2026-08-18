import json
from collections.abc import Iterator, Sequence
from http.client import HTTPException, HTTPResponse
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse, urlunparse
from urllib.request import Request, urlopen

from ..message import Message
from ..reply import CancellationToken, ReplyProviderError


DEFAULT_OLLAMA_URL = "http://localhost:11434"
DEFAULT_TIMEOUT_SECONDS = 120.0


def _build_chat_url(base_url: str) -> str:
    parsed = urlparse(base_url.strip())
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("Ollama URL must be an absolute http:// or https:// URL")
    if parsed.params or parsed.query or parsed.fragment:
        raise ValueError("Ollama URL cannot contain parameters, a query, or a fragment")

    path = parsed.path.rstrip("/")
    if path not in {"", "/api"}:
        raise ValueError("Ollama URL path must be empty or /api")

    return urlunparse(
        (
            parsed.scheme,
            parsed.netloc,
            "/api/chat",
            "",
            "",
            "",
        )
    )


def _read_error_detail(response: HTTPResponse) -> str | None:
    try:
        payload = json.loads(response.read().decode("utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None
    if isinstance(payload, dict) and isinstance(payload.get("error"), str):
        return payload["error"].strip() or None
    return None


def _parse_stream_event(raw_line: bytes) -> tuple[str, bool]:
    try:
        payload = json.loads(raw_line.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ReplyProviderError("Ollama returned an invalid JSON stream event") from exc

    if not isinstance(payload, dict):
        raise ReplyProviderError("Ollama returned an invalid stream event")

    error = payload.get("error")
    if isinstance(error, str) and error.strip():
        raise ReplyProviderError(f"Ollama stream failed: {error.strip()}")

    done = payload.get("done")
    if not isinstance(done, bool):
        raise ReplyProviderError("Ollama stream event is missing a done flag")

    message = payload.get("message")
    if not isinstance(message, dict):
        raise ReplyProviderError("Ollama stream event is missing message data")
    content = message.get("content")
    if not isinstance(content, str):
        raise ReplyProviderError("Ollama stream event has invalid message content")
    return content, done


class OllamaReplyProvider:
    """Generate replies with Ollama's local chat API."""

    def __init__(
        self,
        model: str,
        base_url: str = DEFAULT_OLLAMA_URL,
        timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    ) -> None:
        normalized_model = model.strip()
        if not normalized_model:
            raise ValueError("Ollama model cannot be empty")
        if timeout_seconds <= 0:
            raise ValueError("Ollama timeout must be greater than zero")

        self.model = normalized_model
        self.chat_url = _build_chat_url(base_url)
        self.timeout_seconds = timeout_seconds

    def stream_reply(
        self,
        messages: Sequence[Message],
        cancellation_token: CancellationToken | None = None,
    ) -> Iterator[str]:
        token = cancellation_token or CancellationToken()
        token.raise_if_cancelled()
        payload = {
            "model": self.model,
            "messages": [
                {"role": message.role.value, "content": message.content}
                for message in messages
            ],
            "stream": True,
            "think": False,
        }
        request = Request(
            self.chat_url,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Accept": "application/x-ndjson",
                "Content-Type": "application/json",
            },
            method="POST",
        )

        try:
            with urlopen(request, timeout=self.timeout_seconds) as response:
                completed = False
                for raw_line in response:
                    token.raise_if_cancelled()
                    if not raw_line.strip():
                        continue
                    content, done = _parse_stream_event(raw_line)
                    if content:
                        yield content
                    if done:
                        completed = True
                        break

                token.raise_if_cancelled()
                if not completed:
                    raise ReplyProviderError(
                        "Ollama stream ended before completion"
                    )
        except HTTPError as exc:
            detail = _read_error_detail(exc)
            suffix = f": {detail}" if detail else ""
            raise ReplyProviderError(
                f"Ollama request failed with HTTP {exc.code}{suffix}"
            ) from exc
        except (TimeoutError, URLError, OSError, HTTPException) as exc:
            raise ReplyProviderError(
                f"Cannot connect to Ollama at {self.chat_url}. "
                "Make sure Ollama is installed and running."
            ) from exc

    def generate_reply(self, messages: Sequence[Message]) -> str:
        """Return a complete reply for callers that do not consume streams."""
        content = "".join(self.stream_reply(messages)).strip()
        if not content:
            raise ReplyProviderError("Ollama returned an empty reply")
        return content
