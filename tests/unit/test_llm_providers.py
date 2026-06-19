"""LLM multi-provider routing."""

from __future__ import annotations

import pytest

from lms.agent.llm import (
    iter_llm_endpoints,
    litellm_model_id,
    llm_live_enabled,
)
from lms.config import Settings

pytestmark = pytest.mark.unit


def _isolated_settings(**overrides: object) -> Settings:
    """Build Settings without loading local .env (keeps CI/dev keys out of unit tests)."""
    return Settings(_env_file=None, **overrides)


def test_litellm_model_id_prefixes_provider() -> None:
    assert litellm_model_id("groq", "llama-3.3-70b-versatile") == (
        "groq/llama-3.3-70b-versatile"
    )
    assert litellm_model_id("openai", "gpt-4o-mini") == "openai/gpt-4o-mini"
    assert litellm_model_id("together", "Meta-Llama-3-8B-Instruct-Turbo") == (
        "together_ai/Meta-Llama-3-8B-Instruct-Turbo"
    )


def test_litellm_model_id_passes_through_full_path() -> None:
    assert litellm_model_id("groq", "openai/gpt-4o") == "openai/gpt-4o"
    assert litellm_model_id("together", "meta-llama/Llama-3-8b") == "meta-llama/Llama-3-8b"


def test_llm_live_enabled_requires_key() -> None:
    assert not llm_live_enabled(_isolated_settings(agent_mock_llm=True, groq_api_key="k"))
    assert not llm_live_enabled(
        _isolated_settings(
            agent_mock_llm=False,
            groq_api_key=None,
            openai_api_key=None,
            anthropic_api_key=None,
            together_api_key=None,
            hf_token=None,
        )
    )
    assert llm_live_enabled(_isolated_settings(agent_mock_llm=False, groq_api_key="k"))


def test_iter_llm_endpoints_primary_groq() -> None:
    settings = _isolated_settings(
        agent_mock_llm=False,
        llm_provider="groq",
        groq_api_key="gk-test",
        llm_model="llama-3.3-70b-versatile",
    )
    endpoints = list(iter_llm_endpoints(settings))
    assert len(endpoints) == 1
    assert endpoints[0].provider == "groq"
    assert endpoints[0].model == "groq/llama-3.3-70b-versatile"


def test_iter_llm_endpoints_provider_chain() -> None:
    settings = _isolated_settings(
        agent_mock_llm=False,
        llm_providers="groq,openai",
        groq_api_key="gk-test",
        openai_api_key="sk-test",
        llm_model="llama-3.3-70b-versatile",
    )
    endpoints = list(iter_llm_endpoints(settings))
    assert [e.provider for e in endpoints] == ["groq", "openai"]
    assert endpoints[1].model == "openai/llama-3.3-70b-versatile"


def test_iter_llm_endpoints_per_provider_model_override() -> None:
    settings = _isolated_settings(
        agent_mock_llm=False,
        llm_providers="groq:llama-3.3-70b-versatile,openai:gpt-4o-mini",
        groq_api_key="gk-test",
        openai_api_key="sk-test",
    )
    endpoints = list(iter_llm_endpoints(settings))
    assert endpoints[0].model == "groq/llama-3.3-70b-versatile"
    assert endpoints[1].model == "openai/gpt-4o-mini"


def test_iter_llm_endpoints_fallback_when_enabled() -> None:
    settings = _isolated_settings(
        agent_mock_llm=False,
        llm_provider="groq",
        groq_api_key="gk-test",
        together_api_key="tg-test",
        llm_fallback_enabled=True,
        llm_fallback_provider="together",
        llm_fallback_model="Meta-Llama-3-70b-chat-hf",
    )
    endpoints = list(iter_llm_endpoints(settings))
    assert len(endpoints) == 2
    assert endpoints[1].provider == "together"
    assert endpoints[1].model == "together_ai/Meta-Llama-3-70b-chat-hf"


def test_iter_llm_endpoints_skips_missing_keys() -> None:
    settings = _isolated_settings(
        agent_mock_llm=False,
        llm_providers="groq,openai",
        groq_api_key="gk-test",
        llm_model="llama-3.3-70b-versatile",
    )
    endpoints = list(iter_llm_endpoints(settings))
    assert len(endpoints) == 1
    assert endpoints[0].provider == "groq"


@pytest.mark.parametrize(
    ("provider", "key_field", "key_value"),
    [
        ("openai", "openai_api_key", "sk-test"),
        ("anthropic", "anthropic_api_key", "sk-ant-test"),
        ("huggingface", "hf_token", "hf_test"),
    ],
)
def test_iter_llm_endpoints_other_providers(
    provider: str,
    key_field: str,
    key_value: str,
) -> None:
    settings = _isolated_settings(
        agent_mock_llm=False,
        llm_provider=provider,
        llm_model="test-model",
        **{key_field: key_value},
    )
    endpoints = list(iter_llm_endpoints(settings))
    assert len(endpoints) == 1
    assert endpoints[0].provider == provider
