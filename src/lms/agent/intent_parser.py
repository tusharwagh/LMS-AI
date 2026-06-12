"""Structured intent from librarian messages."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from enum import StrEnum

from lms.config import Settings
from lms.loan.domain.enums import FulfillmentMode, FulfillmentStatus


class IntentAction(StrEnum):
    CHAT = "chat"
    SEARCH_PATRON = "search_patron"
    SEARCH_CATALOG = "search_catalog"
    SELECT_BARCODE = "select_barcode"
    SET_FULFILLMENT = "set_fulfillment"
    REQUEST_COMMIT = "request_commit"
    REQUEST_CANCEL_ISSUE = "request_cancel_issue"
    REQUEST_FULFILLMENT_TRANSITION = "request_fulfillment_transition"
    APPROVE = "approve"
    DENY = "deny"


@dataclass(frozen=True, slots=True)
class ParsedIntent:
    action: IntentAction
    patron_query: str | None = None
    card_barcode: str | None = None
    external_ref: str | None = None
    catalog_query: str | None = None
    holding_barcode: str | None = None
    fulfillment_mode: FulfillmentMode | None = None
    destination_notes: str | None = None
    fulfillment_status: FulfillmentStatus | None = None
    reply_hint: str | None = None


_APPROVE_RE = re.compile(r"^(yes|y|approve|confirm|go ahead|proceed|ok)\.?$", re.I)
_DENY_RE = re.compile(r"^(no|n|deny|cancel|stop)\.?$", re.I)
_BARCODE_RE = re.compile(r"\b(?:barcode|copy)\s+([A-Za-z0-9-]+)", re.I)
_ISSUE_RE = re.compile(
    r"(?:issue|lend|checkout)\s+(?:book\s+)?(?P<title>.+?)\s+(?:to|for)\s+(?P<patron>[^,]+)",
    re.I,
)
_DELIVER_RE = re.compile(r"\b(deliver|delivery|class)\b", re.I)
_DESK_RE = re.compile(r"\b(desk|counter|pick up at desk)\b", re.I)
_TRANSIT_RE = re.compile(r"\b(in transit|in-transit)\b", re.I)
_READY_RE = re.compile(r"\b(ready|mark ready)\b", re.I)
_COMPLETE_RE = re.compile(r"\b(complete|completed|delivered|received)\b", re.I)
_CANCEL_ISSUE_RE = re.compile(
    r"\b(cancel|rollback|undo)\s+(the\s+)?(issue|loan|checkout)\b",
    re.I,
)


class IntentParser:
    """Rule-based parser used in tests and when LLM is unavailable."""

    def parse(self, message: str, *, has_pending_approval: bool) -> ParsedIntent:
        text = message.strip()
        if not text:
            return ParsedIntent(IntentAction.CHAT, reply_hint="Please enter a message.")

        if has_pending_approval:
            if _APPROVE_RE.match(text):
                return ParsedIntent(IntentAction.APPROVE)
            if _DENY_RE.match(text):
                return ParsedIntent(IntentAction.DENY)

        barcode_match = _BARCODE_RE.search(text)
        if barcode_match:
            return ParsedIntent(
                IntentAction.SELECT_BARCODE,
                holding_barcode=barcode_match.group(1).strip(),
            )

        issue_match = _ISSUE_RE.search(text)
        if issue_match:
            mode = FulfillmentMode.DESK
            dest: str | None = None
            if _DELIVER_RE.search(text):
                mode = FulfillmentMode.DELIVERY
                dest = text
            elif _DESK_RE.search(text):
                mode = FulfillmentMode.DESK
            return ParsedIntent(
                IntentAction.REQUEST_COMMIT,
                patron_query=issue_match.group("patron").strip(),
                catalog_query=issue_match.group("title").strip(),
                fulfillment_mode=mode,
                destination_notes=dest,
            )

        if _READY_RE.search(text):
            return ParsedIntent(
                IntentAction.REQUEST_FULFILLMENT_TRANSITION,
                fulfillment_status=FulfillmentStatus.READY,
            )
        if _TRANSIT_RE.search(text):
            return ParsedIntent(
                IntentAction.REQUEST_FULFILLMENT_TRANSITION,
                fulfillment_status=FulfillmentStatus.IN_TRANSIT,
            )
        if _COMPLETE_RE.search(text):
            return ParsedIntent(
                IntentAction.REQUEST_FULFILLMENT_TRANSITION,
                fulfillment_status=FulfillmentStatus.COMPLETED,
            )

        if _CANCEL_ISSUE_RE.search(text):
            return ParsedIntent(IntentAction.REQUEST_CANCEL_ISSUE)

        if text.upper().startswith("CARD-"):
            return ParsedIntent(IntentAction.SEARCH_PATRON, card_barcode=text.strip())
        if text.upper().startswith("ADM-"):
            return ParsedIntent(IntentAction.SEARCH_PATRON, external_ref=text.strip())

        if len(text.split()) <= 4 and not text.lower().startswith("search"):
            return ParsedIntent(IntentAction.SEARCH_PATRON, patron_query=text)

        if text.lower().startswith("search "):
            return ParsedIntent(IntentAction.SEARCH_CATALOG, catalog_query=text[7:].strip())

        return ParsedIntent(IntentAction.SEARCH_CATALOG, catalog_query=text)


class LLMIntentParser(IntentParser):
    """Optional LiteLLM-backed parser; falls back to rules on failure."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._rules = IntentParser()

    def parse(self, message: str, *, has_pending_approval: bool) -> ParsedIntent:
        if self._settings.agent_mock_llm or not self._settings.groq_api_key:
            return self._rules.parse(message, has_pending_approval=has_pending_approval)
        try:
            return self._parse_llm(message, has_pending_approval=has_pending_approval)
        except Exception:
            return self._rules.parse(message, has_pending_approval=has_pending_approval)

    def _parse_llm(self, message: str, *, has_pending_approval: bool) -> ParsedIntent:
        import litellm

        system = (
            "Extract librarian desk intent as JSON with keys: "
            "action, patron_query, card_barcode, external_ref, catalog_query, "
            "holding_barcode, fulfillment_mode (DESK|DELIVERY|PICKUP_POINT), "
            "destination_notes, fulfillment_status (READY|IN_TRANSIT|COMPLETED), reply_hint. "
            "Actions: chat, search_patron, search_catalog, select_barcode, set_fulfillment, "
            "request_commit, request_cancel_issue, request_fulfillment_transition, approve, deny."
        )
        user = json.dumps({"message": message, "has_pending_approval": has_pending_approval})
        response = litellm.completion(
            model=f"groq/{self._settings.llm_model}",
            api_key=self._settings.groq_api_key,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            max_tokens=256,
            temperature=0,
        )
        content = response.choices[0].message.content or "{}"
        data = json.loads(content)
        mode = data.get("fulfillment_mode")
        fmode = FulfillmentMode(mode) if mode else None
        fstatus_raw = data.get("fulfillment_status")
        fstatus = FulfillmentStatus(fstatus_raw) if fstatus_raw else None
        return ParsedIntent(
            action=IntentAction(data.get("action", "chat")),
            patron_query=data.get("patron_query"),
            card_barcode=data.get("card_barcode"),
            external_ref=data.get("external_ref"),
            catalog_query=data.get("catalog_query"),
            holding_barcode=data.get("holding_barcode"),
            fulfillment_mode=fmode,
            destination_notes=data.get("destination_notes"),
            fulfillment_status=fstatus,
            reply_hint=data.get("reply_hint"),
        )
