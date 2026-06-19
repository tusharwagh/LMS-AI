"""LLM intent system prompt coverage."""

from __future__ import annotations

import pytest

from lms.agent.llm_intent_prompt import LLM_INTENT_SYSTEM
from lms.agent.schemas import IntentAction

pytestmark = pytest.mark.unit

# Every coordinator-handled action must appear in the prompt for the LLM to use it.
_EXPECTED_ACTIONS = {action.value for action in IntentAction}


@pytest.mark.parametrize("action", sorted(_EXPECTED_ACTIONS))
def test_llm_intent_prompt_documents_every_action(action: str) -> None:
    assert action in LLM_INTENT_SYSTEM


def test_llm_intent_prompt_covers_all_workflows() -> None:
    for phrase in (
        "Guided issue",
        "One-shot issue",
        "Patron at desk",
        "Return / check-in",
        "Catalog browse",
        "Patron lookup",
        "Fulfillment",
        "Human-in-the-loop",
        "session_context",
        "start_patron_desk",
        "request_commit",
        "decline_continue",
    ):
        assert phrase in LLM_INTENT_SYSTEM
