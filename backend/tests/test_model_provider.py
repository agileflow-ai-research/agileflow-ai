import json
import httpx
import pytest

from app.common.model_provider import (
    LocalLlamaCppProvider,
    ModelProviderConfigurationError,
    ModelProviderError,
    ModelStructuredOutputError,
    OpenAICompatibleProvider,
    UnavailableModelProvider,
    build_model_provider,
)
from app.core.config import Settings


def test_llama_cpp_provider_configuration_requires_no_api_key():
    settings = Settings(
        model_provider="llama_cpp",
        model_name="Qwen3-4B-Instruct-2507-Q4_K_M",
        model_base_url="http://127.0.0.1:8080",
        model_api_key=None,
    )
    provider = build_model_provider(settings)
    assert isinstance(provider, LocalLlamaCppProvider)
    assert provider._model == "Qwen3-4B-Instruct-2507-Q4_K_M"
    assert provider._base_url == "http://127.0.0.1:8080"
    assert provider.endpoint_url == "http://127.0.0.1:8080/v1/chat/completions"


def test_local_llama_cpp_alias_configuration():
    settings = Settings(
        model_provider="local_llama_cpp",
        model_name="Qwen3-4B-Instruct-2507-Q4_K_M",
        model_base_url="http://127.0.0.1:8080/v1",
        model_api_key=None,
    )
    provider = build_model_provider(settings)
    assert isinstance(provider, LocalLlamaCppProvider)
    assert provider.endpoint_url == "http://127.0.0.1:8080/v1/chat/completions"


def test_llama_cpp_requires_model_name():
    settings = Settings(
        model_provider="llama_cpp",
        model_name="",
        model_base_url="http://127.0.0.1:8080",
    )
    provider = build_model_provider(settings)
    assert isinstance(provider, UnavailableModelProvider)
    with pytest.raises(ModelProviderConfigurationError, match="MODEL_NAME is not configured"):
        provider.generate_structured(system_prompt="s", user_prompt="u", json_schema={})


def test_openai_compatible_still_requires_api_key():
    settings = Settings(
        model_provider="openai_compatible",
        model_name="gpt-4.1-mini",
        model_api_key=None,
    )
    provider = build_model_provider(settings)
    assert isinstance(provider, UnavailableModelProvider)
    with pytest.raises(ModelProviderConfigurationError, match="MODEL_API_KEY is not configured"):
        provider.generate_structured(system_prompt="s", user_prompt="u", json_schema={})


def test_unsupported_model_provider():
    settings = Settings(
        model_provider="unknown_provider",
        model_name="test",
    )
    provider = build_model_provider(settings)
    assert isinstance(provider, UnavailableModelProvider)
    with pytest.raises(ModelProviderConfigurationError, match="Unsupported MODEL_PROVIDER"):
        provider.generate_structured(system_prompt="s", user_prompt="u", json_schema={})


def test_llama_cpp_generates_structured_and_forwards_schema(monkeypatch):
    captured = {}

    def post(url, **kwargs):
        captured["url"] = url
        captured["headers"] = kwargs.get("headers", {})
        captured["json"] = kwargs.get("json", {})
        return httpx.Response(
            200,
            request=httpx.Request("POST", url),
            json={
                "choices": [
                    {
                        "message": {
                            "content": json.dumps({"status": "ok", "count": 42})
                        }
                    }
                ]
            },
        )

    monkeypatch.setattr(httpx, "post", post)

    provider = LocalLlamaCppProvider(
        model="Qwen3-4B-Instruct-2507-Q4_K_M",
        base_url="http://127.0.0.1:8080",
        timeout_seconds=30.0,
    )

    schema = {
        "type": "object",
        "properties": {"status": {"type": "string"}, "count": {"type": "integer"}},
        "required": ["status", "count"],
    }

    result = provider.generate_structured(
        system_prompt="You are an assistant",
        user_prompt="Provide status",
        json_schema=schema,
    )

    assert result == {"status": "ok", "count": 42}
    assert captured["url"] == "http://127.0.0.1:8080/v1/chat/completions"
    assert "Authorization" not in captured["headers"]
    assert captured["headers"]["Content-Type"] == "application/json"
    assert captured["json"]["model"] == "Qwen3-4B-Instruct-2507-Q4_K_M"
    assert captured["json"]["temperature"] == 0.1
    assert captured["json"]["response_format"] == {
        "type": "json_schema",
        "json_schema": {
            "name": "specialist_structured_output",
            "strict": True,
            "schema": schema,
        },
    }


def test_llama_cpp_handles_invalid_json(monkeypatch):
    def post(*args, **kwargs):
        return httpx.Response(
            200,
            request=httpx.Request("POST", "http://127.0.0.1:8080/v1/chat/completions"),
            json={"choices": [{"message": {"content": "Not valid json at all"}}]},
        )

    monkeypatch.setattr(httpx, "post", post)

    provider = LocalLlamaCppProvider(
        model="Qwen3-4B-Instruct-2507-Q4_K_M",
        base_url="http://127.0.0.1:8080",
    )

    with pytest.raises(ModelStructuredOutputError, match="not valid structured JSON"):
        provider.generate_structured(
            system_prompt="system", user_prompt="user", json_schema={}
        )


def test_llama_cpp_handles_non_object_json(monkeypatch):
    def post(*args, **kwargs):
        return httpx.Response(
            200,
            request=httpx.Request("POST", "http://127.0.0.1:8080/v1/chat/completions"),
            json={"choices": [{"message": {"content": '["list", "not", "dict"]'}}]},
        )

    monkeypatch.setattr(httpx, "post", post)

    provider = LocalLlamaCppProvider(
        model="Qwen3-4B-Instruct-2507-Q4_K_M",
        base_url="http://127.0.0.1:8080",
    )

    with pytest.raises(ModelStructuredOutputError, match="not an object"):
        provider.generate_structured(
            system_prompt="system", user_prompt="user", json_schema={}
        )


@pytest.mark.parametrize(
    "error",
    [
        httpx.TimeoutException("Read timeout"),
        httpx.ConnectError("Connection refused"),
        httpx.HTTPStatusError(
            "Server error",
            request=httpx.Request("POST", "http://127.0.0.1:8080"),
            response=httpx.Response(500),
        ),
    ],
)
def test_llama_cpp_handles_network_and_http_errors(monkeypatch, error):
    def post(*args, **kwargs):
        raise error

    monkeypatch.setattr(httpx, "post", post)

    provider = LocalLlamaCppProvider(
        model="Qwen3-4B-Instruct-2507-Q4_K_M",
        base_url="http://127.0.0.1:8080",
    )

    with pytest.raises(ModelProviderError, match="Structured model generation failed"):
        provider.generate_structured(
            system_prompt="system", user_prompt="user", json_schema={}
        )
