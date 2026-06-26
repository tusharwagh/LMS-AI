"""NeMo Guardrails checker — input/output rail wiring."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from nemoguardrails.rails.llm.options import RailsResult, RailStatus
from tests.helpers import isolated_settings

from lms.shared.llm.models import LlmGuardrailError
from lms.shared.llm.nemo_guardrails import NemoGuardrailsChecker, apply_output_content

pytestmark = pytest.mark.unit


def test_checker_disabled_by_default() -> None:
    checker = NemoGuardrailsChecker.from_settings(isolated_settings())
    assert not checker.enabled


def test_validate_input_raises_when_blocked() -> None:
    checker = NemoGuardrailsChecker(isolated_settings())
    checker._rails = MagicMock()
    checker._rails.check.return_value = RailsResult(
        status=RailStatus.BLOCKED,
        content="I cannot respond to that request.",
        rail="jailbreak detection model",
    )

    with pytest.raises(LlmGuardrailError, match="blocked input"):
        checker.validate_input([{"role": "user", "content": "bad"}], purpose="test")


def test_validate_output_returns_modified_content() -> None:
    checker = NemoGuardrailsChecker(isolated_settings())
    checker._rails = MagicMock()
    checker._rails.check.return_value = RailsResult(
        status=RailStatus.MODIFIED,
        content='{"action":"chat","reply_hint":"safe"}',
    )

    result = checker.validate_output(
        [{"role": "user", "content": "hello"}],
        '{"action":"chat"}',
        purpose="test",
    )
    assert result == '{"action":"chat","reply_hint":"safe"}'


def test_apply_output_content_mutates_response() -> None:
    response = SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content='{"action":"chat"}'))]
    )
    apply_output_content(response, '{"action":"deny"}')
    assert response.choices[0].message.content == '{"action":"deny"}'
