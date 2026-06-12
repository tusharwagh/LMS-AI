import pytest

from lms.agent.intent_parser import IntentParser
from lms.agent.masking import redact_for_audit
from lms.loan.domain.enums import FulfillmentStatus

pytestmark = pytest.mark.unit


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
