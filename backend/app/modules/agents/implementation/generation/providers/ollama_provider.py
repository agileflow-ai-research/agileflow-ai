import json
import re
from threading import Lock
from typing import Any
from urllib.parse import urlsplit

import httpx
from pydantic import ValidationError

from app.core.config import Settings

from ..schemas import (
    CodeGenerationErrorCode as ErrorCode,
    ModelFileResponse,
    OllamaRuntimeMetadata,
    ProviderGenerationRequest,
    ProviderGenerationResponse,
)
from .base import CodeGenerationError


APPROVED_OLLAMA_MODEL = "qwen2.5-coder:3b"
MODEL_SOURCE = "Qwen/Qwen2.5-Coder-3B-Instruct"
MODEL_LICENSE = "Qwen Research License"
_LOOPBACK_HOSTS = frozenset({"127.0.0.1", "::1"})
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_LOCAL_INFERENCE_LOCK = Lock()


def validate_ollama_base_url(value: str) -> str:
    """Return a canonical loopback-only Ollama origin."""
    try:
        parsed = urlsplit(value)
        port = parsed.port
    except (TypeError, ValueError) as exc:
        raise ValueError("Ollama base URL is invalid") from exc
    if (
        parsed.scheme != "http"
        or parsed.hostname not in _LOOPBACK_HOSTS
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
        or parsed.path not in {"", "/"}
    ):
        raise ValueError("Ollama base URL must be an HTTP loopback origin")
    if port is None:
        port = 80
    host = f"[{parsed.hostname}]" if parsed.hostname == "::1" else parsed.hostname
    return f"http://{host}:{port}"


class OllamaCodeGenerationProvider:
    """Calls only a local Ollama native API; it never pulls or replaces models."""

    def __init__(
        self,
        *,
        enabled: bool,
        base_url: str,
        model: str,
        expected_model_digest: str = "",
        timeout_seconds: float = 180.0,
        max_response_bytes: int = 262_144,
        keep_alive: str = "0",
        http_client: httpx.Client | None = None,
    ) -> None:
        self._enabled = enabled
        self._base_url = validate_ollama_base_url(base_url)
        if model != APPROVED_OLLAMA_MODEL:
            raise ValueError("Only the approved local Qwen coder model is supported")
        if expected_model_digest and not _SHA256.fullmatch(expected_model_digest):
            raise ValueError("Expected Ollama model digest must be SHA-256")
        if keep_alive != "0":
            raise ValueError("GEN-R1.3B requires immediate Ollama model unload")
        self._model = model
        self._expected_model_digest = expected_model_digest
        self._timeout_seconds = timeout_seconds
        self._max_response_bytes = max_response_bytes
        self._keep_alive = keep_alive
        self._http_client = http_client
        self._inference_lock = _LOCAL_INFERENCE_LOCK

    def generate_file(
        self, request: ProviderGenerationRequest
    ) -> ProviderGenerationResponse:
        if not self._enabled:
            self._fail(
                ErrorCode.LOCAL_INFERENCE_DISABLED,
                "Local code-generation inference is disabled",
            )
        acquired = self._inference_lock.acquire(timeout=self._timeout_seconds)
        if not acquired:
            self._fail(
                ErrorCode.GENERATION_INTERRUPTED,
                "Another local generation request did not finish in time",
            )
        try:
            model_entry = self._installed_model()
            runtime_version = self._runtime_version()
            body = self._request_json(
                "POST",
                "/api/generate",
                json_body={
                    "model": self._model,
                    "system": request.system_prompt,
                    "prompt": request.user_prompt,
                    "format": request.response_schema,
                    "stream": False,
                    "keep_alive": self._keep_alive,
                    "options": {
                        "temperature": 0,
                        "num_ctx": request.context_tokens,
                        "num_predict": request.max_output_tokens,
                    },
                },
                failure_code=ErrorCode.MODEL_UNAVAILABLE,
            )
        finally:
            self._inference_lock.release()
        if body.get("done") is not True or body.get("done_reason") != "stop":
            self._fail(
                ErrorCode.GENERATION_INTERRUPTED,
                "Local model generation did not complete normally",
            )
        prompt_token_count = _optional_nonnegative_int(body.get("prompt_eval_count"))
        generated_token_count = _optional_nonnegative_int(body.get("eval_count"))
        if prompt_token_count is None or generated_token_count is None:
            self._fail(
                ErrorCode.INVALID_MODEL_RESPONSE,
                "Local model response omitted required token metadata",
            )
        if (
            prompt_token_count
            > request.context_tokens - request.max_output_tokens
            or generated_token_count > request.max_output_tokens
        ):
            self._fail(
                ErrorCode.CONTEXT_LIMIT_EXCEEDED,
                "Local model token usage exceeded the approved generation budget",
            )
        raw_result = body.get("response")
        if not isinstance(raw_result, str):
            self._fail(
                ErrorCode.INVALID_MODEL_RESPONSE,
                "Local model returned an invalid response",
            )
        try:
            parsed_result = json.loads(raw_result)
        except json.JSONDecodeError as exc:
            raise CodeGenerationError(
                ErrorCode.INVALID_MODEL_RESPONSE,
                "Local model response was not valid JSON",
            ) from exc
        try:
            result = ModelFileResponse.model_validate(parsed_result)
        except ValidationError as exc:
            raise CodeGenerationError(
                ErrorCode.INVALID_RESPONSE_SCHEMA,
                "Local model response did not match the required schema",
            ) from exc

        details = model_entry.get("details")
        if not isinstance(details, dict):
            details = {}
        digest = model_entry.get("digest")
        if not isinstance(digest, str) or not _SHA256.fullmatch(digest):
            digest = None
        return ProviderGenerationResponse(
            result=result,
            metadata=OllamaRuntimeMetadata(
                requested_model=self._model,
                resolved_model=str(
                    model_entry.get("model") or model_entry.get("name") or self._model
                ),
                model_digest=digest,
                model_source=MODEL_SOURCE,
                model_license=MODEL_LICENSE,
                quantization_level=_optional_string(details.get("quantization_level")),
                parameter_size=_optional_string(details.get("parameter_size")),
                ollama_version=runtime_version,
                done=True,
                done_reason=_optional_string(body.get("done_reason")),
                prompt_token_count=prompt_token_count,
                generated_token_count=generated_token_count,
                load_duration_ms=_nanoseconds_to_milliseconds(
                    body.get("load_duration")
                ),
                generation_duration_ms=_nanoseconds_to_milliseconds(
                    body.get("eval_duration")
                ),
                total_duration_ms=_nanoseconds_to_milliseconds(
                    body.get("total_duration")
                ),
                context_tokens=request.context_tokens,
                max_output_tokens=request.max_output_tokens,
                temperature=0,
                keep_alive=self._keep_alive,
            ),
        )

    def _installed_model(self) -> dict[str, Any]:
        body = self._request_json(
            "GET", "/api/tags", failure_code=ErrorCode.OLLAMA_UNAVAILABLE
        )
        models = body.get("models")
        if not isinstance(models, list):
            self._fail(
                ErrorCode.OLLAMA_UNAVAILABLE,
                "The local Ollama server returned an invalid model inventory",
            )
        match = next(
            (
                item
                for item in models
                if isinstance(item, dict)
                and self._model in {item.get("model"), item.get("name")}
            ),
            None,
        )
        if match is None:
            self._fail(
                ErrorCode.MODEL_NOT_INSTALLED,
                "The approved local code-generation model is not installed",
            )
        digest = match.get("digest")
        if self._expected_model_digest and digest != self._expected_model_digest:
            self._fail(
                ErrorCode.MODEL_UNAVAILABLE,
                "The installed local model does not match the approved digest",
            )
        return match

    def _runtime_version(self) -> str | None:
        body = self._request_json(
            "GET", "/api/version", failure_code=ErrorCode.OLLAMA_UNAVAILABLE
        )
        return _optional_string(body.get("version"))

    def _request_json(
        self,
        method: str,
        path: str,
        *,
        json_body: dict[str, Any] | None = None,
        failure_code: ErrorCode,
    ) -> dict[str, Any]:
        client = self._http_client
        owns_client = client is None
        if client is None:
            client = httpx.Client(
                timeout=self._timeout_seconds,
                follow_redirects=False,
                trust_env=False,
            )
        try:
            with client.stream(
                method,
                f"{self._base_url}{path}",
                json=json_body,
                headers={"Content-Type": "application/json"},
                timeout=self._timeout_seconds,
            ) as response:
                if response.history or 300 <= response.status_code < 400:
                    self._fail(
                        ErrorCode.OLLAMA_UNAVAILABLE,
                        "Redirects from the local Ollama endpoint are not allowed",
                    )
                if response.status_code >= 400:
                    self._fail(failure_code, "The local Ollama request failed")
                chunks: list[bytes] = []
                size = 0
                for chunk in response.iter_bytes():
                    size += len(chunk)
                    if size > self._max_response_bytes:
                        self._fail(
                            ErrorCode.UNSUPPORTED_CONTENT,
                            "The local model response exceeded the configured limit",
                        )
                    chunks.append(chunk)
            parsed = json.loads(b"".join(chunks))
        except httpx.TimeoutException as exc:
            raise CodeGenerationError(
                ErrorCode.MODEL_TIMEOUT, "The local model request timed out"
            ) from exc
        except (httpx.ConnectError, httpx.NetworkError) as exc:
            raise CodeGenerationError(
                ErrorCode.OLLAMA_UNAVAILABLE,
                "The local Ollama server is unavailable",
            ) from exc
        except httpx.HTTPError as exc:
            raise CodeGenerationError(
                failure_code,
                "The local Ollama request failed",
            ) from exc
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise CodeGenerationError(
                ErrorCode.INVALID_MODEL_RESPONSE,
                "The local Ollama server returned invalid JSON",
            ) from exc
        finally:
            if owns_client:
                client.close()
        if not isinstance(parsed, dict):
            self._fail(
                ErrorCode.INVALID_MODEL_RESPONSE,
                "The local Ollama response was not an object",
            )
        return parsed

    @staticmethod
    def _fail(code: ErrorCode, message: str):
        raise CodeGenerationError(code, message)


def build_code_generation_provider(
    settings: Settings,
    *,
    http_client: httpx.Client | None = None,
) -> OllamaCodeGenerationProvider:
    if settings.agent3_code_gen_provider.strip().lower() != "ollama":
        raise ValueError("Only the local Ollama code-generation provider is supported")
    return OllamaCodeGenerationProvider(
        enabled=settings.agent3_code_gen_local_enabled,
        base_url=settings.agent3_ollama_base_url,
        model=settings.agent3_ollama_model,
        expected_model_digest=settings.agent3_ollama_expected_model_digest,
        timeout_seconds=settings.agent3_code_gen_timeout_seconds,
        max_response_bytes=settings.agent3_code_gen_max_response_bytes,
        keep_alive=settings.agent3_ollama_keep_alive,
        http_client=http_client,
    )


def _optional_string(value: Any) -> str | None:
    return value if isinstance(value, str) and value else None


def _optional_nonnegative_int(value: Any) -> int | None:
    return value if isinstance(value, int) and value >= 0 else None


def _nanoseconds_to_milliseconds(value: Any) -> float | None:
    if not isinstance(value, int) or value < 0:
        return None
    return value / 1_000_000

