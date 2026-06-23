import json

import pytest

from lms.agent import messages as desk
from lms.agent.intent_parser import IntentParser, ParsedIntent
from lms.agent.schemas import IntentAction
from lms.agent.session import PendingActionKind
from lms.loan.domain.enums import FulfillmentStatus
from lms.shared.privacy.redaction import redact_for_audit

pytestmark = pytest.mark.unit


def test_missing_patron_messages_vary_by_intent() -> None:
    catalog = desk.missing_patron_for(IntentAction.SEARCH_CATALOG)
    barcode = desk.missing_patron_for(IntentAction.SELECT_BARCODE)
    commit = desk.missing_patron_for(IntentAction.REQUEST_COMMIT)
    assert "search for a copy" in catalog.lower()
    assert "barcode" in barcode.lower()
    assert "issue" in commit.lower()
    assert catalog != barcode != commit


def test_patron_search_empty_is_distinct_from_missing_patron_for_commit() -> None:
    empty = desk.patron_search_empty()
    missing = desk.missing_patron_for(IntentAction.REQUEST_COMMIT)
    assert empty != missing
    assert "didn't include" in empty.lower()


def test_approval_denied_messages_vary_by_pending_kind() -> None:
    commit = desk.approval_denied(PendingActionKind.COMMIT_ISSUE)
    cancel = desk.approval_denied(PendingActionKind.CANCEL_ISSUE)
    transition = desk.approval_denied(PendingActionKind.TRANSITION_FULFILLMENT)
    assert "issue" in commit.lower()
    assert "loan remains" in cancel.lower()
    assert "delivery" in transition.lower()
    assert commit != cancel != transition


def test_missing_slots_for_commit_names_each_gap() -> None:
    both = desk.missing_slots_for_commit(missing_patron=True, missing_copy=True)
    patron_only = desk.missing_slots_for_commit(missing_patron=True, missing_copy=False)
    copy_only = desk.missing_slots_for_commit(missing_patron=False, missing_copy=True)
    assert "patron and a copy" in both.lower()
    assert "still need a patron" in patron_only.lower()
    assert "still need a copy" in copy_only.lower()


def test_redact_for_audit_masks_card_like_numbers() -> None:
    text = redact_for_audit("card 4111-1111-1111-1111")
    assert "[CARD_REDACTED]" in text


def test_intent_parser_issue_phrase() -> None:
    parser = IntentParser()
    intent = parser.parse(
        "Issue Harry Potter to Riya Sharma, desk pickup",
        has_pending_approval=False,
    )
    assert intent.action.value == "request_commit"
    assert intent.patron_query == "Riya Sharma"
    assert "Harry Potter" in (intent.catalog_query or "")


def test_intent_parser_cancel_issue() -> None:
    parser = IntentParser()
    intent = parser.parse("Cancel the issue", has_pending_approval=False)
    assert intent.action.value == "request_cancel_issue"


def test_intent_parser_fulfillment_transition() -> None:
    parser = IntentParser()
    intent = parser.parse("Mark in transit", has_pending_approval=False)
    assert intent.fulfillment_status == FulfillmentStatus.IN_TRANSIT


def test_llm_intent_parser_falls_back_on_llm_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    from lms.agent.intent_parser import LLMIntentParser
    from lms.config import Settings

    settings = Settings(_env_file=None, agent_mock_llm=False, groq_api_key="test-key")
    parser = LLMIntentParser(settings)

    def _fail_llm(
        _message: str,
        *,
        has_pending_approval: bool,
        session_context: dict[str, bool] | None = None,
    ) -> ParsedIntent:
        raise ValueError("simulated LLM failure")

    monkeypatch.setattr(parser, "_parse_llm", _fail_llm)
    intent = parser.parse("Cancel the issue", has_pending_approval=False)
    assert intent.action.value == "request_cancel_issue"


def test_llm_intent_parser_passes_session_context(monkeypatch: pytest.MonkeyPatch) -> None:
    from types import SimpleNamespace

    from lms.agent.intent_parser import LLMIntentParser
    from lms.agent.llm_intent_prompt import LLM_INTENT_SYSTEM
    from lms.agent.schemas import IntentAction
    from lms.config import Settings

    settings = Settings(_env_file=None, agent_mock_llm=False, groq_api_key="test-key")
    parser = LLMIntentParser(settings)
    captured: dict[str, object] = {}

    class _FakeGateway:
        def complete(self, **kwargs: object) -> object:
            messages = kwargs["messages"]
            assert isinstance(messages, list)
            captured["messages"] = messages
            captured["max_tokens"] = kwargs["max_tokens"]
            captured["session_id"] = kwargs.get("session_id")
            captured["operator_id"] = kwargs.get("operator_id")
            payload = json.loads(messages[1]["content"])  # type: ignore[index]
            assert payload["message"] == "What books are issued to Riya Sharma?"
            assert payload["session_context"]["has_pending_desk_patron"] is True
            assert "start_patron_desk" in messages[0]["content"]  # type: ignore[index]
            assert "session_context" in messages[0]["content"]  # type: ignore[index]
            llm_json = '{"action":"start_patron_desk","patron_query":"Riya Sharma"}'
            response = SimpleNamespace(
                choices=[SimpleNamespace(message=SimpleNamespace(content=llm_json))]
            )
            from lms.shared.llm.models import LlmCompletionResult, LlmEndpoint

            return LlmCompletionResult(
                response=response,
                endpoint=LlmEndpoint(provider="groq", model="groq/test", api_key="k"),
                purpose="intent_parse",
            )

    monkeypatch.setattr(
        "lms.agent.intent_parser.LlmGateway.from_settings",
        lambda _settings: _FakeGateway(),
    )
    intent = parser.parse_with_context(
        "What books are issued to Riya Sharma?",
        has_pending_approval=False,
        has_return_candidates=False,
        has_pending_desk_patron=True,
        trace_session_id="sess-desk-1",
        trace_operator_id="lib-42",
    )
    assert intent.action == IntentAction.START_PATRON_DESK
    assert intent.patron_query == "Riya Sharma"
    assert captured["session_id"] == "sess-desk-1"
    assert captured["operator_id"] == "lib-42"
    messages = captured["messages"]
    assert isinstance(messages, list)
    assert messages[0]["content"] == LLM_INTENT_SYSTEM


def test_patron_search_results_echoes_query() -> None:
    msg = desk.patron_search_results("Sharma", 2, ["Riya Sharma", "Amit Sharma"])
    assert "Sharma" in msg
    assert "2 patrons" in msg
    assert "Riya Sharma" in msg
    assert "library card" in msg.lower()


def test_catalog_search_results_echoes_query() -> None:
    msg = desk.catalog_search_results("Harry Potter", 3, ["Harry Potter", "Harry Potter 2"])
    assert "Harry Potter" in msg
    assert "3 lendable copies" in msg
    assert "barcode" in msg.lower()


def test_issue_ready_names_patron_and_copy() -> None:
    msg = desk.issue_ready("Riya Sharma", "Harry Potter", "ABC-123")
    assert "Riya Sharma" in msg
    assert "Harry Potter" in msg
    assert "ABC-123" in msg
    assert "issue" in msg.lower()


def test_help_for_unknown_intent_echoes_user_message() -> None:
    msg = desk.help_for_unknown_intent("what can you do?")
    assert "what can you do?" in msg
    assert "search for a patron" in msg.lower()


def test_help_reply_for_issue_question() -> None:
    msg = desk.help_reply("how do I issue a book?")
    assert "issue" in msg.lower()
    assert "Harry Potter" in msg or "title and patron" in msg.lower()


def test_greeting_reply_is_friendly() -> None:
    msg = desk.greeting_reply()
    assert "hello" in msg.lower()
    assert "issue" in msg.lower()
    assert "pseudonym" not in msg.lower()


def test_intent_parser_help_routes_to_chat() -> None:
    parser = IntentParser()
    intent = parser.parse("help", has_pending_approval=False)
    assert intent.action == IntentAction.CHAT
    assert intent.reply_hint is not None
    assert "issue" in intent.reply_hint.lower()


def test_intent_parser_greeting_routes_to_chat() -> None:
    parser = IntentParser()
    intent = parser.parse("hello", has_pending_approval=False)
    assert intent.action == IntentAction.CHAT
    assert intent.reply_hint is not None
    assert "hello" in intent.reply_hint.lower()


def test_intent_parser_issue_help_question() -> None:
    parser = IntentParser()
    intent = parser.parse("how do I issue a book?", has_pending_approval=False)
    assert intent.action == IntentAction.CHAT
    assert intent.reply_hint is not None
    assert "issue" in intent.reply_hint.lower()


def test_fulfillment_transition_prompt_includes_title() -> None:
    msg = desk.fulfillment_transition_prompt(
        FulfillmentStatus.IN_TRANSIT,
        title="Harry Potter",
    )
    assert "Harry Potter" in msg
    assert "in transit" in msg.lower()


def test_redact_for_audit_masks_card_patterns() -> None:
    raw = "Card 4111-1111-1111-1111 for patron"
    assert "[CARD_REDACTED]" in redact_for_audit(raw)


def test_sanitize_approval_details_strips_internal_ids() -> None:
    from uuid import uuid4

    from lms.agent.masking import sanitize_approval_details

    loan_id = uuid4()
    details = sanitize_approval_details(
        {
            "candidate": {
                "loan_id": loan_id,
                "title": "Harry Potter",
                "barcode": "ABC-123",
            }
        }
    )
    assert "loan_id" not in details["candidate"]
    assert details["candidate"]["title"] == "Harry Potter"


def test_pending_approval_blocks_message_mentions_card_actions() -> None:
    msg = desk.pending_approval_blocks_message("Issue Harry Potter to Riya")
    assert "Approve" in msg
    assert "Deny" in msg
    assert "Harry Potter" in msg


def test_issue_committed_is_friendly_not_technical() -> None:
    msg = desk.issue_committed("Riya Sharma", "Harry Potter", "ABC-123")
    assert "issued to Riya Sharma" in msg
    assert "Harry Potter" in msg
    assert "committed" not in msg.lower()
