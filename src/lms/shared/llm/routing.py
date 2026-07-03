"""Provider chain resolution and LiteLLM Router model_list construction."""

from __future__ import annotations

from collections.abc import Iterator
from typing import cast

from litellm_gateway.models import LlmEndpoint
from litellm_gateway.routing import (
    RouterConfig,
    is_cached_response,
    litellm_model_id,
    resolve_endpoint_from_response,
)
from litellm_gateway.routing import (
    build_router_config as _build_router_config,
)
from litellm_gateway.routing import (
    iter_llm_endpoints as _iter_llm_endpoints,
)
from litellm_gateway.routing import (
    llm_live_enabled as _llm_live_enabled,
)

from lms.config import Settings

__all__ = [
    "RouterConfig",
    "build_router_config",
    "is_cached_response",
    "iter_llm_endpoints",
    "litellm_model_id",
    "llm_live_enabled",
    "resolve_endpoint_from_response",
]


def llm_live_enabled(settings: Settings) -> bool:
    return cast(bool, _llm_live_enabled(settings.to_llm_gateway_settings()))


def iter_llm_endpoints(settings: Settings) -> Iterator[LlmEndpoint]:
    yield from _iter_llm_endpoints(settings.to_llm_gateway_settings())


def build_router_config(settings: Settings) -> RouterConfig:
    return _build_router_config(settings.to_llm_gateway_settings())
