"""LiteLLM gateway — routing, cache, rate limit, guardrails, Router."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from tests.helpers import isolated_settings

from lms.shared.llm import (
    LlmGateway,
    LlmGuardrailError,
    LlmRateLimitError,
    build_router_config,
    iter_llm_endpoints,
    litellm_model_id,
    llm_live_enabled,
)

pytestmark = pytest.mark.unit


def _fake_response(*, content: str = '{"action":"chat"}') -> SimpleNamespace:
    return SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=content))],
        usage=SimpleNamespace(prompt_tokens=1, completion_tokens=1, total_tokens=2),
        model="groq/test",
        _hidden_params={"model_id": "lms-groq-0"},
    )


def test_litellm_model_id_prefixes_provider() -> None:
    assert litellm_model_id("groq", "llama-3.3-70b-versatile") == (
        "groq/llama-3.3-70b-versatile"
    )


def test_llm_live_enabled_requires_key() -> None:
    assert not llm_live_enabled(isolated_settings(agent_mock_llm=True, groq_api_key="k"))
    assert llm_live_enabled(isolated_settings(agent_mock_llm=False, groq_api_key="k"))


def test_iter_llm_endpoints_provider_chain() -> None:
    settings = isolated_settings(
        llm_providers="groq,openai",
        groq_api_key="gk-test",
        openai_api_key="sk-test",
        llm_model="llama-3.3-70b-versatile",
    )
    endpoints = list(iter_llm_endpoints(settings))
    assert [e.provider for e in endpoints] == ["groq", "openai"]


def test_build_router_config_sets_rpm_and_fallbacks() -> None:
    settings = isolated_settings(
        llm_providers="groq,openai",
        groq_api_key="gk",
        openai_api_key="sk",
        llm_rate_limit_enabled=True,
        llm_rate_limit_max=120,
        llm_rate_limit_window_seconds=60,
    )
    config = build_router_config(settings)
    assert config.primary_model == "lms-groq-0"
    assert config.fallbacks == [{"lms-groq-0": ["lms-openai-1"]}]
    assert config.model_list[0]["rpm"] == 120


def test_guardrail_rejects_empty_messages() -> None:
    gateway = LlmGateway.from_settings(isolated_settings(groq_api_key="k"))
    with pytest.raises(LlmGuardrailError, match="At least one message"):
        gateway.complete(messages=[], max_tokens=64)


def test_guardrail_rejects_oversized_prompt() -> None:
    settings = isolated_settings(groq_api_key="k", llm_max_prompt_chars=10)
    gateway = LlmGateway.from_settings(settings)
    with pytest.raises(LlmGuardrailError, match="maximum length"):
        gateway.complete(
            messages=[{"role": "user", "content": "x" * 20}],
            max_tokens=64,
        )


def test_rate_limit_surfaces_router_error() -> None:
    settings = isolated_settings(
        groq_api_key="k",
        llm_cache_enabled=False,
        llm_rate_limit_enabled=True,
    )
    router = MagicMock()
    router.completion.side_effect = RuntimeError("rate limit exceeded for deployment")
    config = build_router_config(settings)
    gateway = LlmGateway(settings, router=router, router_config=config)

    with pytest.raises(LlmRateLimitError):
        gateway.complete(messages=[{"role": "user", "content": "hello"}], max_tokens=64)


def test_gateway_uses_router_completion() -> None:
    settings = isolated_settings(groq_api_key="k", llm_cache_enabled=False)
    router = MagicMock()
    router.completion.return_value = _fake_response()
    config = build_router_config(settings)
    gateway = LlmGateway(settings, router=router, router_config=config)

    result = gateway.complete(
        messages=[{"role": "user", "content": "hello"}],
        max_tokens=64,
        purpose="test",
        session_id="sess-abc",
        operator_id="op-123",
    )

    router.completion.assert_called_once()
    metadata = router.completion.call_args.kwargs["metadata"]
    assert metadata["purpose"] == "test"
    assert metadata["session_id"] == "sess-abc"
    assert metadata["operator_id"] == "op-123"
    assert result.endpoint.provider == "groq"
    assert not result.cached


def test_gateway_fallback_tries_second_provider() -> None:
    settings = isolated_settings(
        llm_providers="groq,openai",
        groq_api_key="gk",
        openai_api_key="sk",
        llm_cache_enabled=False,
        llm_rate_limit_enabled=False,
    )
    fake_response = _fake_response()
    fake_response.model = "openai/test"
    fake_response._hidden_params = {"model_id": "lms-openai-1"}

    router = MagicMock()
    router.completion.return_value = fake_response
    gateway = LlmGateway.from_settings(settings)
    gateway._router = router

    result = gateway.complete(
        messages=[{"role": "user", "content": "hello"}],
        max_tokens=64,
    )

    assert result.endpoint.provider == "openai"
    assert result.fallback_index == 1


def test_gateway_proxy_pass_through() -> None:
    settings = isolated_settings(
        groq_api_key="gk",
        llm_proxy_url="http://localhost:4000",
        llm_cache_enabled=False,
    )
    gateway = LlmGateway.from_settings(settings)
    fake_response = _fake_response()

    with patch("litellm.completion", return_value=fake_response) as mock_completion:
        result = gateway.complete(
            messages=[{"role": "user", "content": "hello"}],
            max_tokens=64,
        )

    assert mock_completion.call_count == 1
    assert mock_completion.call_args.kwargs["api_base"] == "http://localhost:4000"
    assert result.endpoint.provider == "groq"


def test_configure_litellm_skips_langfuse_callback_for_sdk_v4() -> None:
    import litellm

    from lms.shared.llm.setup import configure_litellm

    litellm.success_callback.clear()
    litellm.failure_callback.clear()
    settings = isolated_settings(
        langfuse_public_key="pk-test",
        langfuse_secret_key="sk-test",
        langfuse_host="https://us.cloud.langfuse.com",
    )

    configure_litellm(settings)

    assert "langfuse" not in litellm.success_callback
    assert "langfuse" not in litellm.failure_callback
