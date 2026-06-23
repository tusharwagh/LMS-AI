"""Structured intent from librarian messages."""

from __future__ import annotations

import json
import re

import structlog
from litellm.exceptions import LITELLM_EXCEPTION_TYPES

from lms.agent import messages as desk
from lms.agent.constants import AGENT_ID
from lms.agent.llm_intent_prompt import LLM_INTENT_SYSTEM
from lms.agent.schemas import IntentAction, ParsedIntent
from lms.config import Settings
from lms.loan.domain.enums import FulfillmentMode, FulfillmentStatus
from lms.shared.llm import LlmGateway, llm_live_enabled
from lms.shared.llm.models import LlmGatewayError
from lms.shared.observability.tracing import LangfuseTracing
from lms.shared.privacy.redaction import redact_for_audit

_APPROVE_RE = re.compile(r"^(yes|y|approve|confirm|go ahead|proceed|ok)\.?$", re.I)
_DENY_RE = re.compile(r"^(no|n|deny|cancel|stop)\.?$", re.I)
_BARCODE_RE = re.compile(r"\b(?:barcode|copy)\s+([A-Za-z0-9-]+)", re.I)
_ISSUE_TO_RE = re.compile(
    r"\b(?:issue|lend|checkout)\s+(?:it\s+)?to\s+(?P<patron>.+)$",
    re.I,
)
_PROCEED_ISSUE_RE = re.compile(
    r"\b(yes,? issue|issue it|proceed with issue|go ahead with issue)\b",
    re.I,
)
_SEARCH_BOOK_RE = re.compile(
    r"^(?:search|find)\s+(?:book\s+|catalog\s+)?(?P<title>.+)$",
    re.I,
)
_SELECT_COPY_RE = re.compile(
    r"\b(?:select|choose|pick)\s+(?:copy\s+)?(COPY_\d+)\b",
    re.I,
)
_SELECT_PATRON_RE = re.compile(
    r"\b(?:select|choose|pick)\s+(?:patron\s+)?(PATRON_\d+)\b",
    re.I,
)
_ISSUE_RE = re.compile(
    r"(?:issue|lend|checkout)\s+(?:book\s+)?(?P<title>.+?)\s+(?:to|for)\s+(?P<patron>[^,]+)",
    re.I,
)
_START_ISSUE_TO_PATRON_RE = re.compile(
    r"^(?:i\s+)?(?:want\s+to\s+)?(?:issue|checkout|lend)\s+(?:a\s+)?book\s+to\s+"
    r"(?:(?:a\s+)?patron\s+)?(?P<patron>[^,]+)?\.?$",
    re.I,
)
_ISSUE_BOOK_GENERIC_RE = re.compile(
    r"^(?:i\s+)?(?:want\s+to\s+)?(?:issue|checkout|lend)\s+(?:a\s+)?book\.?$",
    re.I,
)
_RETURN_BOOK_GENERIC_RE = re.compile(
    r"^(?:i\s+)?(?:want\s+to\s+)?return\s+(?:a\s+)?book\.?$",
    re.I,
)
_RETURN_GENERIC_RE = re.compile(
    r"^return\s+(?:a\s+)?book\.?$",
    re.I,
)
_BROWSE_CATALOG_RE = re.compile(
    r"^(?:browse\s+(?:the\s+)?catalog|search\s+(?:the\s+)?catalog|find\s+(?:a\s+)?book)\.?$",
    re.I,
)
_START_PATRON_LOOKUP_RE = re.compile(
    r"^(?:look\s*up\s+patron|find\s+patron|who\s+is\s+(?:the\s+)?patron)\.?$",
    re.I,
)
_BARCODE_CRITERIA_RE = re.compile(
    r"^[A-Za-z0-9-]*[0-9][A-Za-z0-9-]*$",
)
_DESK_DONE_RE = re.compile(
    r"^(?:done|that'?s all|nothing else|finished|all set|we'?re done)\.?$",
    re.I,
)
_DESK_ISSUE_RE = re.compile(
    r"^(?:issue(?:\s+another)?(?:\s+book)?|borrow\s+another|checkout\s+another)\.?$",
    re.I,
)
_PATRON_LOANS_GENERIC_RE = re.compile(
    r"^(?:which|what)\s+books?\s+(?:are\s+)?(?:issued|checked\s*out|out|on\s+loan)(?:\s+to\s+me)?\??$",
    re.I,
)
_PATRON_ISSUED_TO_RE = re.compile(
    r"^(?:which|what)\s+books?\s+(?:are\s+)?(?:issued|checked\s*out|out|on\s+loan)\s+to\s+(?P<patron>.+)\??$",
    re.I,
)
_LIST_ISSUED_TO_RE = re.compile(
    r"^(?:list|show)(?:\s+me)?\s+(?:the\s+)?(?:books?\s+)?(?:issued|checked\s*out|on\s+loan)"
    r"(?:\s+to\s+(?P<patron>.+?))?\??$",
    re.I,
)
_PATRON_OPEN_LOANS_RE = re.compile(
    r"^(?:what|which)\s+(?:open\s+)?loans?\s+(?:does\s+)?(?P<patron>.+?)\s+have\??$",
    re.I,
)
_SHOW_LOANS_FOR_RE = re.compile(
    r"^(?:show|list)\s+(?:open\s+)?loans?\s+for\s+(?P<patron>.+)\??$",
    re.I,
)
_PATRON_HAS_OUT_RE = re.compile(
    r"^(?:what|show)\s+(?:does\s+)?(?P<patron>.+?)\s+have\s+(?:out|checked\s*out)\??$",
    re.I,
)
_PATRON_BORROWED_RE = re.compile(
    r"^(?:what|which)\s+(?:books?\s+)?(?:has|have)\s+(?P<patron>.+?)\s+borrowed\??$",
    re.I,
)
_CHECKED_OUT_TO_RE = re.compile(
    r"^(?:what'?s|what\s+is|which\s+books?\s+(?:are\s+)?)\s+(?:checked\s*out|out)\s+to\s+(?P<patron>.+)\??$",
    re.I,
)
_ISSUED_TO_TARGET_RE = re.compile(
    r"^(?:which|what|show|list)?\s*(?:books?\s+)?(?:are\s+)?(?:issued|checked\s*out|on\s+loan)\s+to\s+"
    r"(?P<target>.+)\??$",
    re.I,
)
_LOANS_FOR_TARGET_RE = re.compile(
    r"^(?:show|list|what|which)?\s*(?:open\s+)?loans?\s+for\s+(?P<target>.+)\??$",
    re.I,
)
_SHOW_PATRON_LOANS_RE = re.compile(
    r"^(?:show|list)\s+(?P<patron>.+?)\s+(?:open\s+)?loans?\??$",
    re.I,
)
_PATRON_POSSESSIVE_LOANS_RE = re.compile(
    r"^(?:what|which|show)\s+(?P<patron>.+?)(?:'s|’s)\s+(?:issued\s+)?(?:books?|loans?|checkouts?)\??$",
    re.I,
)
_ISSUED_FOR_TARGET_RE = re.compile(
    r"^(?:books?|loans?|checkouts?)\s+(?:issued|out|on\s+loan)\s+(?:to|for)\s+(?P<target>.+)\??$",
    re.I,
)
_BUSINESS_KEY_RE = re.compile(r"^(PATRON_\d+|CARD-[A-Za-z0-9-]+|ADM-[A-Za-z0-9-]+)$", re.I)
_GENERIC_RETURN_TITLES = frozenset({"a book", "book", "the book", "books"})
_VAGUE_RETURN_RE = re.compile(r"^return(?:\s+(?:a\s+)?book)?\.?$", re.I)
_DECLINE_CONTINUE_RE = re.compile(
    r"^(?:no|nope|cancel|stop|never\s*mind|nevermind|forget\s+it|"
    r"don'?t\s+(?:bother|continue)|skip|not\s+now)\.?$",
    re.I,
)
_GENERIC_PATRON_REFS = frozenset(
    {"", "a patron", "patron", "the patron", "someone", "a student", "student"}
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
_RETURN_BARCODE_RE = re.compile(
    r"\breturn(?:\s+(?:book|copy))?\s+(?:barcode|copy)\s+([A-Za-z0-9-]+)",
    re.I,
)
_RETURN_CODE_RE = re.compile(
    r"\breturn(?:\s+(?:book|copy))?\s+([A-Za-z0-9]*[0-9][A-Za-z0-9-]*)\b",
    re.I,
)
_CHECKIN_BARCODE_RE = re.compile(
    r"\b(?:check[\s-]?in|scan)\s+(?:barcode|copy)?\s*([A-Za-z0-9-]+)",
    re.I,
)
_COMMIT_RETURN_RE = re.compile(
    r"\b(complete\s+return|desk\s+return|check[\s-]?in\s+book|check\s+in)\b",
    re.I,
)
_RETURN_PICKUP_RE = re.compile(
    r"\b(schedule\s+pickup|pickup\s+from\s+class|collect\s+return)\b",
    re.I,
)
_RETURN_BY_NAME_RE = re.compile(
    r"^return\s+(?:book\s+)?(?P<title>.+?)\s+(?:from|for)\s+(?P<patron>.+)$",
    re.I,
)
_RETURN_FROM_PATRON_RE = re.compile(
    r"^return\s+(?:books?\s+)?(?:from|for)\s+(?P<patron>.+)$",
    re.I,
)
_RETURN_TITLE_ONLY_RE = re.compile(
    r"^return\s+(?:book\s+)?(?P<title>.+)$",
    re.I,
)
_SELECT_RETURN_LOAN_RE = re.compile(
    r"\b(?:select|choose|pick)\s+(?:loan\s+)?(LOAN_\d+)\b",
    re.I,
)
_BARE_PATRON_PSEUDONYM_RE = re.compile(r"^(PATRON_\d+)$", re.I)
_BARE_COPY_PSEUDONYM_RE = re.compile(r"^(COPY_\d+)$", re.I)
_BARE_LOAN_PSEUDONYM_RE = re.compile(r"^(LOAN_\d+)$", re.I)
_GREETING_RE = re.compile(
    r"^(hi|hello|hey|thanks|thank you|good morning|good afternoon)[!.?\s]*$",
    re.I,
)
_HELP_RE = re.compile(
    r"^(help(?:\s+me)?|\?|what can you do\??|how (?:do|can) i\b.+)$",
    re.I,
)

_LLM_INTENT_PARSE_ERRORS: tuple[type[BaseException], ...] = (
    json.JSONDecodeError,
    KeyError,
    TypeError,
    ValueError,
    IndexError,
    LlmGatewayError,
    *LITELLM_EXCEPTION_TYPES,
)

logger = structlog.get_logger(__name__)


def _strip_patron_tail(value: str) -> str:
    return value.strip().rstrip("?.!,").strip()


def _issued_books_intent_from_target(target: str) -> ParsedIntent:
    """Map a patron target (name wildcard, PATRON_N, CARD-, ADM-) to desk list intent."""
    target = _strip_patron_tail(target)
    if not target or target.lower() in _GENERIC_PATRON_REFS:
        return ParsedIntent(IntentAction.START_PATRON_DESK)
    if re.fullmatch(r"PATRON_\d+", target, re.I):
        return ParsedIntent(
            IntentAction.START_PATRON_DESK,
            patron_pseudonym=target.upper(),
        )
    upper = target.upper()
    if upper.startswith("CARD-"):
        return ParsedIntent(IntentAction.START_PATRON_DESK, card_barcode=upper)
    if upper.startswith("ADM-"):
        return ParsedIntent(IntentAction.START_PATRON_DESK, external_ref=upper)
    if target.lower() in {"me", "myself"}:
        return ParsedIntent(IntentAction.START_PATRON_DESK)
    return ParsedIntent(IntentAction.START_PATRON_DESK, patron_query=target)


def _parse_issued_books_query(text: str) -> ParsedIntent | None:
    """Issued/checked-out book inquiries — partial names and business-key wildcards."""
    stripped = text.strip()
    if _PATRON_LOANS_GENERIC_RE.match(stripped):
        return ParsedIntent(IntentAction.START_PATRON_DESK)

    for pattern, group in (
        (_PATRON_ISSUED_TO_RE, "patron"),
        (_PATRON_BORROWED_RE, "patron"),
        (_CHECKED_OUT_TO_RE, "patron"),
        (_PATRON_OPEN_LOANS_RE, "patron"),
        (_SHOW_LOANS_FOR_RE, "patron"),
        (_PATRON_HAS_OUT_RE, "patron"),
        (_SHOW_PATRON_LOANS_RE, "patron"),
        (_PATRON_POSSESSIVE_LOANS_RE, "patron"),
        (_ISSUED_TO_TARGET_RE, "target"),
        (_LOANS_FOR_TARGET_RE, "target"),
        (_ISSUED_FOR_TARGET_RE, "target"),
    ):
        match = pattern.match(stripped)
        if match:
            return _issued_books_intent_from_target(match.group(group))

    list_issued = _LIST_ISSUED_TO_RE.match(stripped)
    if list_issued:
        patron_raw = (list_issued.group("patron") or "").strip()
        if not patron_raw or patron_raw.lower() in {"me", "myself"}:
            return ParsedIntent(IntentAction.START_PATRON_DESK)
        return _issued_books_intent_from_target(patron_raw)

    return None


class IntentParser:
    """Rule-based parser used in tests and when LLM is unavailable."""

    def parse(
        self,
        message: str,
        *,
        has_pending_approval: bool,
        has_return_candidates: bool = False,
        has_catalog_candidates: bool = False,
        has_selected_copy_no_patron: bool = False,
        ready_to_issue: bool = False,
        has_pending_book_criteria_prompt: bool = False,
        has_pending_patron_prompt: bool = False,
        has_pending_desk_patron: bool = False,
        has_pending_desk_next_action: bool = False,
        has_pending_desk_return_pick: bool = False,
        has_pending_catalog_criteria: bool = False,
        has_pending_patron_lookup: bool = False,
        has_patron_candidates: bool = False,
        has_guided_issue_context: bool = False,
        has_guided_return_context: bool = False,
        has_guided_catalog_context: bool = False,
        has_guided_patron_lookup_context: bool = False,
    ) -> ParsedIntent:
        text = message.strip()
        if not text:
            return ParsedIntent(IntentAction.CHAT, reply_hint=desk.EMPTY_MESSAGE)

        if has_pending_approval:
            if _APPROVE_RE.match(text):
                return ParsedIntent(IntentAction.APPROVE)
            if _DENY_RE.match(text):
                return ParsedIntent(IntentAction.DENY)

        if (
            has_guided_issue_context
            or has_guided_return_context
            or has_guided_catalog_context
            or has_guided_patron_lookup_context
            or has_pending_book_criteria_prompt
            or has_pending_patron_prompt
            or has_pending_desk_patron
            or has_pending_desk_return_pick
            or has_pending_catalog_criteria
            or has_pending_patron_lookup
        ) and _DECLINE_CONTINUE_RE.match(text):
            return ParsedIntent(IntentAction.DECLINE_CONTINUE)

        if has_pending_patron_lookup:
            if text.upper().startswith("CARD-"):
                return ParsedIntent(
                    IntentAction.PROVIDE_PATRON_LOOKUP,
                    card_barcode=text.strip(),
                )
            if text.upper().startswith("ADM-"):
                return ParsedIntent(
                    IntentAction.PROVIDE_PATRON_LOOKUP,
                    external_ref=text.strip(),
                )
            return ParsedIntent(IntentAction.PROVIDE_PATRON_LOOKUP, patron_query=text)

        if has_pending_desk_patron:
            if text.upper().startswith("CARD-"):
                return ParsedIntent(
                    IntentAction.PROVIDE_PATRON_FOR_DESK,
                    card_barcode=text.strip(),
                )
            if text.upper().startswith("ADM-"):
                return ParsedIntent(
                    IntentAction.PROVIDE_PATRON_FOR_DESK,
                    external_ref=text.strip(),
                )
            barcode_pick = _BARCODE_RE.search(text)
            if barcode_pick:
                return ParsedIntent(
                    IntentAction.PROVIDE_PATRON_FOR_DESK,
                    holding_barcode=barcode_pick.group(1).strip(),
                )
            checkin_pick = _CHECKIN_BARCODE_RE.search(text)
            if checkin_pick:
                return ParsedIntent(
                    IntentAction.PROVIDE_PATRON_FOR_DESK,
                    holding_barcode=checkin_pick.group(1).strip(),
                )
            return ParsedIntent(IntentAction.PROVIDE_PATRON_FOR_DESK, patron_query=text)

        if has_pending_desk_return_pick:
            loan_sel = _SELECT_RETURN_LOAN_RE.search(text)
            if loan_sel:
                return ParsedIntent(
                    IntentAction.SELECT_RETURN_LOAN,
                    loan_pseudonym=loan_sel.group(1).upper(),
                )
            barcode_pick = _BARCODE_RE.search(text)
            if barcode_pick:
                return ParsedIntent(
                    IntentAction.SELECT_RETURN_LOAN,
                    holding_barcode=barcode_pick.group(1).strip(),
                )
            if _BARCODE_CRITERIA_RE.match(text.strip()):
                return ParsedIntent(
                    IntentAction.SELECT_RETURN_LOAN,
                    holding_barcode=text.strip(),
                )
            return ParsedIntent(IntentAction.SELECT_RETURN_LOAN, catalog_query=text)

        if has_pending_desk_next_action:
            if _DESK_DONE_RE.match(text):
                return ParsedIntent(IntentAction.DESK_SESSION_DONE)
            if _DESK_ISSUE_RE.match(text) or _ISSUE_BOOK_GENERIC_RE.match(text):
                return ParsedIntent(IntentAction.DESK_START_ISSUE)
            if _BROWSE_CATALOG_RE.match(text) or text.lower().startswith("search catalog"):
                return ParsedIntent(IntentAction.DESK_START_CATALOG)
            if _VAGUE_RETURN_RE.match(text) or _RETURN_BOOK_GENERIC_RE.match(text):
                return ParsedIntent(IntentAction.DESK_START_RETURN)
            if _COMMIT_RETURN_RE.search(text):
                return ParsedIntent(IntentAction.REQUEST_COMMIT_RETURN)
            if _RETURN_PICKUP_RE.search(text):
                return ParsedIntent(IntentAction.REQUEST_RETURN_PICKUP)
            if has_return_candidates:
                loan_sel = _SELECT_RETURN_LOAN_RE.search(text)
                if loan_sel:
                    return ParsedIntent(
                        IntentAction.SELECT_RETURN_LOAN,
                        loan_pseudonym=loan_sel.group(1).upper(),
                    )
                barcode_pick = _BARCODE_RE.search(text)
                if barcode_pick:
                    return ParsedIntent(
                        IntentAction.SELECT_RETURN_LOAN,
                        holding_barcode=barcode_pick.group(1).strip(),
                    )
                if not _VAGUE_RETURN_RE.match(text):
                    return ParsedIntent(
                        IntentAction.SELECT_RETURN_LOAN,
                        catalog_query=text,
                    )

        if has_pending_catalog_criteria:
            return ParsedIntent(IntentAction.PROVIDE_CATALOG_CRITERIA, catalog_query=text)

        if has_pending_patron_prompt:
            if text.upper().startswith("CARD-"):
                return ParsedIntent(
                    IntentAction.PROVIDE_PATRON_FOR_ISSUE,
                    card_barcode=text.strip(),
                )
            if text.upper().startswith("ADM-"):
                return ParsedIntent(
                    IntentAction.PROVIDE_PATRON_FOR_ISSUE,
                    external_ref=text.strip(),
                )
            return ParsedIntent(IntentAction.PROVIDE_PATRON_FOR_ISSUE, patron_query=text)

        if has_pending_book_criteria_prompt:
            return ParsedIntent(IntentAction.PROVIDE_BOOK_CRITERIA, catalog_query=text)

        if has_patron_candidates:
            bare_patron = _BARE_PATRON_PSEUDONYM_RE.match(text.strip())
            if bare_patron:
                return ParsedIntent(
                    IntentAction.SELECT_PATRON,
                    patron_pseudonym=bare_patron.group(1).upper(),
                )
            patron_sel = _SELECT_PATRON_RE.search(text)
            if patron_sel:
                return ParsedIntent(
                    IntentAction.SELECT_PATRON,
                    patron_pseudonym=patron_sel.group(1).upper(),
                )
            if text.upper().startswith("CARD-"):
                return ParsedIntent(IntentAction.SELECT_PATRON, card_barcode=text.strip())
            if text.upper().startswith("ADM-"):
                return ParsedIntent(IntentAction.SELECT_PATRON, external_ref=text.strip())
            return ParsedIntent(IntentAction.SELECT_PATRON, patron_query=text)

        if ready_to_issue and (
            _PROCEED_ISSUE_RE.search(text) or text.lower() in {"issue", "checkout", "lend"}
        ):
            return ParsedIntent(IntentAction.REQUEST_COMMIT)

        if has_return_candidates:
            bare_loan = _BARE_LOAN_PSEUDONYM_RE.match(text.strip())
            if bare_loan:
                return ParsedIntent(
                    IntentAction.SELECT_RETURN_LOAN,
                    loan_pseudonym=bare_loan.group(1).upper(),
                )
            loan_sel = _SELECT_RETURN_LOAN_RE.search(text)
            if loan_sel:
                return ParsedIntent(
                    IntentAction.SELECT_RETURN_LOAN,
                    loan_pseudonym=loan_sel.group(1).upper(),
                )
            barcode_pick = _BARCODE_RE.search(text)
            if barcode_pick:
                return ParsedIntent(
                    IntentAction.SELECT_RETURN_LOAN,
                    holding_barcode=barcode_pick.group(1).strip(),
                )
            checkin_pick = _CHECKIN_BARCODE_RE.search(text)
            if checkin_pick:
                return ParsedIntent(
                    IntentAction.SELECT_RETURN_LOAN,
                    holding_barcode=checkin_pick.group(1).strip(),
                )
            if not _COMMIT_RETURN_RE.search(text) and not _RETURN_PICKUP_RE.search(text):
                return ParsedIntent(IntentAction.SELECT_RETURN_LOAN, catalog_query=text)

        if has_catalog_candidates:
            bare_copy = _BARE_COPY_PSEUDONYM_RE.match(text.strip())
            if bare_copy:
                return ParsedIntent(
                    IntentAction.SELECT_CATALOG_COPY,
                    copy_pseudonym=bare_copy.group(1).upper(),
                )
            copy_sel = _SELECT_COPY_RE.search(text)
            if copy_sel:
                return ParsedIntent(
                    IntentAction.SELECT_CATALOG_COPY,
                    copy_pseudonym=copy_sel.group(1).upper(),
                )
            barcode_pick = _BARCODE_RE.search(text)
            if barcode_pick:
                return ParsedIntent(
                    IntentAction.SELECT_CATALOG_COPY,
                    holding_barcode=barcode_pick.group(1).strip(),
                )
            if not _ISSUE_TO_RE.search(text) and not _PROCEED_ISSUE_RE.search(text):
                if text.lower() not in {"issue", "checkout", "lend"}:
                    return ParsedIntent(IntentAction.SELECT_CATALOG_COPY, catalog_query=text)

        if has_selected_copy_no_patron:
            issue_to = _ISSUE_TO_RE.search(text)
            if issue_to:
                mode = FulfillmentMode.DESK
                dest: str | None = None
                if _DELIVER_RE.search(text):
                    mode = FulfillmentMode.DELIVERY
                    dest = text
                elif _DESK_RE.search(text):
                    mode = FulfillmentMode.DESK
                patron_raw = issue_to.group("patron").strip()
                if "," in patron_raw:
                    patron_raw = patron_raw.split(",", 1)[0].strip()
                return ParsedIntent(
                    IntentAction.ISSUE_TO_PATRON,
                    patron_query=patron_raw,
                    fulfillment_mode=mode,
                    destination_notes=dest,
                )
            if len(text.split()) <= 4 and not text.lower().startswith("search"):
                return ParsedIntent(IntentAction.ISSUE_TO_PATRON, patron_query=text)

        if (
            has_guided_issue_context
            and text.lower() in {"issue", "checkout", "lend"}
        ):
            return ParsedIntent(IntentAction.REQUEST_COMMIT)

        return_barcode = _RETURN_BARCODE_RE.search(text)
        if return_barcode:
            return ParsedIntent(
                IntentAction.LOOKUP_RETURN,
                holding_barcode=return_barcode.group(1).strip(),
            )

        if _COMMIT_RETURN_RE.search(text):
            return ParsedIntent(IntentAction.REQUEST_COMMIT_RETURN)

        if _RETURN_PICKUP_RE.search(text):
            return ParsedIntent(
                IntentAction.REQUEST_RETURN_PICKUP,
                destination_notes=text,
            )

        return_by_name = _RETURN_BY_NAME_RE.match(text)
        if return_by_name:
            return ParsedIntent(
                IntentAction.SEARCH_RETURN,
                catalog_query=return_by_name.group("title").strip(),
                patron_query=return_by_name.group("patron").strip(),
            )

        return_from_patron = _RETURN_FROM_PATRON_RE.match(text)
        if return_from_patron:
            return ParsedIntent(
                IntentAction.SEARCH_RETURN,
                patron_query=return_from_patron.group("patron").strip(),
            )

        return_title_only = _RETURN_TITLE_ONLY_RE.match(text)
        if return_title_only:
            title = return_title_only.group("title").strip()
            if title.lower() not in _GENERIC_RETURN_TITLES and not _COMMIT_RETURN_RE.search(title):
                return ParsedIntent(IntentAction.SEARCH_RETURN, catalog_query=title)

        if _PATRON_LOANS_GENERIC_RE.match(text):
            return ParsedIntent(IntentAction.START_PATRON_DESK)

        issued_books = _parse_issued_books_query(text)
        if issued_books is not None:
            return issued_books

        if _RETURN_BOOK_GENERIC_RE.match(text) or _RETURN_GENERIC_RE.match(text):
            return ParsedIntent(IntentAction.START_RETURN)

        checkin_barcode = _CHECKIN_BARCODE_RE.search(text)
        if checkin_barcode and "issue" not in text.lower():
            return ParsedIntent(
                IntentAction.LOOKUP_RETURN,
                holding_barcode=checkin_barcode.group(1).strip(),
            )

        return_code = _RETURN_CODE_RE.search(text)
        if return_code:
            return ParsedIntent(
                IntentAction.LOOKUP_RETURN,
                holding_barcode=return_code.group(1).strip(),
            )

        barcode_match = _BARCODE_RE.search(text)
        if barcode_match:
            return ParsedIntent(
                IntentAction.SELECT_BARCODE,
                holding_barcode=barcode_match.group(1).strip(),
            )

        issue_match = _ISSUE_RE.search(text)
        if issue_match:
            title = issue_match.group("title").strip()
            if title.lower() not in {"a book", "book", "the book"}:
                mode = FulfillmentMode.DESK
                dest = None
                if _DELIVER_RE.search(text):
                    mode = FulfillmentMode.DELIVERY
                    dest = text
                elif _DESK_RE.search(text):
                    mode = FulfillmentMode.DESK
                return ParsedIntent(
                    IntentAction.REQUEST_COMMIT,
                    patron_query=issue_match.group("patron").strip(),
                    catalog_query=title,
                    fulfillment_mode=mode,
                    destination_notes=dest,
                )

        start_issue = _START_ISSUE_TO_PATRON_RE.match(text)
        if start_issue:
            patron_raw = (start_issue.group("patron") or "").strip()
            if "," in patron_raw:
                patron_raw = patron_raw.split(",", 1)[0].strip()
            if patron_raw.lower() in _GENERIC_PATRON_REFS:
                patron_query = None
            else:
                patron_query = patron_raw or None
            mode = FulfillmentMode.DESK
            dest = None
            if _DELIVER_RE.search(text):
                mode = FulfillmentMode.DELIVERY
                dest = text
            elif _DESK_RE.search(text):
                mode = FulfillmentMode.DESK
            return ParsedIntent(
                IntentAction.START_ISSUE_TO_PATRON,
                patron_query=patron_query,
                fulfillment_mode=mode,
                destination_notes=dest,
            )

        if _ISSUE_BOOK_GENERIC_RE.match(text):
            return ParsedIntent(IntentAction.START_ISSUE_TO_PATRON)

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

        if _BROWSE_CATALOG_RE.match(text):
            return ParsedIntent(IntentAction.START_CATALOG_SEARCH)

        if _START_PATRON_LOOKUP_RE.match(text):
            return ParsedIntent(IntentAction.START_PATRON_LOOKUP)

        search_book = _SEARCH_BOOK_RE.match(text)
        if search_book:
            title = search_book.group("title").strip()
            if title.lower() not in {"catalog", "a book", "book", "the catalog"}:
                return ParsedIntent(
                    IntentAction.SEARCH_CATALOG,
                    catalog_query=title,
                )

        if _GREETING_RE.match(text):
            return ParsedIntent(IntentAction.CHAT, reply_hint=desk.greeting_reply())
        if _HELP_RE.match(text):
            return ParsedIntent(IntentAction.CHAT, reply_hint=desk.help_reply(text))

        business_key = _BUSINESS_KEY_RE.match(text)
        if business_key:
            return _issued_books_intent_from_target(business_key.group(1))

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

    def __init__(self, settings: Settings, *, tracing: LangfuseTracing | None = None) -> None:
        self._settings = settings
        self._rules = IntentParser()
        self._tracing = tracing or LangfuseTracing(settings)

    def parse(
        self,
        message: str,
        *,
        has_pending_approval: bool,
        has_return_candidates: bool = False,
        has_catalog_candidates: bool = False,
        has_selected_copy_no_patron: bool = False,
        ready_to_issue: bool = False,
        has_pending_book_criteria_prompt: bool = False,
        has_pending_patron_prompt: bool = False,
        has_pending_desk_patron: bool = False,
        has_pending_desk_next_action: bool = False,
        has_pending_desk_return_pick: bool = False,
        has_pending_catalog_criteria: bool = False,
        has_pending_patron_lookup: bool = False,
        has_patron_candidates: bool = False,
        has_guided_issue_context: bool = False,
        has_guided_return_context: bool = False,
        has_guided_catalog_context: bool = False,
        has_guided_patron_lookup_context: bool = False,
    ) -> ParsedIntent:
        return self.parse_with_context(
            message,
            has_pending_approval=has_pending_approval,
            has_return_candidates=has_return_candidates,
            has_catalog_candidates=has_catalog_candidates,
            has_selected_copy_no_patron=has_selected_copy_no_patron,
            ready_to_issue=ready_to_issue,
            has_pending_book_criteria_prompt=has_pending_book_criteria_prompt,
            has_pending_patron_prompt=has_pending_patron_prompt,
            has_pending_desk_patron=has_pending_desk_patron,
            has_pending_desk_next_action=has_pending_desk_next_action,
            has_pending_desk_return_pick=has_pending_desk_return_pick,
            has_pending_catalog_criteria=has_pending_catalog_criteria,
            has_pending_patron_lookup=has_pending_patron_lookup,
            has_patron_candidates=has_patron_candidates,
            has_guided_issue_context=has_guided_issue_context,
            has_guided_return_context=has_guided_return_context,
            has_guided_catalog_context=has_guided_catalog_context,
            has_guided_patron_lookup_context=has_guided_patron_lookup_context,
        )

    def parse_with_context(
        self,
        message: str,
        *,
        has_pending_approval: bool,
        has_return_candidates: bool,
        has_catalog_candidates: bool = False,
        has_selected_copy_no_patron: bool = False,
        ready_to_issue: bool = False,
        has_pending_book_criteria_prompt: bool = False,
        has_pending_patron_prompt: bool = False,
        has_pending_desk_patron: bool = False,
        has_pending_desk_next_action: bool = False,
        has_pending_desk_return_pick: bool = False,
        has_pending_catalog_criteria: bool = False,
        has_pending_patron_lookup: bool = False,
        has_patron_candidates: bool = False,
        has_guided_issue_context: bool = False,
        has_guided_return_context: bool = False,
        has_guided_catalog_context: bool = False,
        has_guided_patron_lookup_context: bool = False,
        trace_session_id: str = "",
        trace_operator_id: str = "",
    ) -> ParsedIntent:
        ctx = {
            "has_pending_approval": has_pending_approval,
            "has_return_candidates": has_return_candidates,
            "has_catalog_candidates": has_catalog_candidates,
            "has_selected_copy_no_patron": has_selected_copy_no_patron,
            "ready_to_issue": ready_to_issue,
            "has_pending_book_criteria_prompt": has_pending_book_criteria_prompt,
            "has_pending_patron_prompt": has_pending_patron_prompt,
            "has_pending_desk_patron": has_pending_desk_patron,
            "has_pending_desk_next_action": has_pending_desk_next_action,
            "has_pending_desk_return_pick": has_pending_desk_return_pick,
            "has_pending_catalog_criteria": has_pending_catalog_criteria,
            "has_pending_patron_lookup": has_pending_patron_lookup,
            "has_patron_candidates": has_patron_candidates,
            "has_guided_issue_context": has_guided_issue_context,
            "has_guided_return_context": has_guided_return_context,
            "has_guided_catalog_context": has_guided_catalog_context,
            "has_guided_patron_lookup_context": has_guided_patron_lookup_context,
        }
        if not llm_live_enabled(self._settings):
            return self._rules.parse(message, **ctx)
        try:
            return self._parse_llm(
                message,
                has_pending_approval=has_pending_approval,
                session_context=ctx,
                trace_session_id=trace_session_id,
                trace_operator_id=trace_operator_id,
            )
        except _LLM_INTENT_PARSE_ERRORS as exc:
            logger.warning("llm_intent_parse_failed", error=str(exc))
            return self._rules.parse(message, **ctx)

    def _parse_llm(
        self,
        message: str,
        *,
        has_pending_approval: bool,
        session_context: dict[str, bool] | None = None,
        trace_session_id: str = "",
        trace_operator_id: str = "",
    ) -> ParsedIntent:
        redacted_message = redact_for_audit(message)
        with self._tracing.intent_span(
            session_id=trace_session_id,
            operator_id=trace_operator_id,
            agent_id=AGENT_ID,
        ):
            user = json.dumps(
                {
                    "message": redacted_message,
                    "has_pending_approval": has_pending_approval,
                    "session_context": session_context or {},
                }
            )
            max_tokens = self._settings.max_tokens or 256
            temperature = (
                self._settings.temperature if self._settings.temperature is not None else 0
            )
            result = LlmGateway.from_settings(self._settings).complete(
                messages=[
                    {"role": "system", "content": LLM_INTENT_SYSTEM},
                    {"role": "user", "content": user},
                ],
                max_tokens=max_tokens,
                temperature=temperature,
                purpose="intent_parse",
                session_id=trace_session_id or None,
                operator_id=trace_operator_id or None,
            )
            content = result.response.choices[0].message.content or "{}"
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
            loan_pseudonym=data.get("loan_pseudonym"),
            copy_pseudonym=data.get("copy_pseudonym"),
            patron_pseudonym=data.get("patron_pseudonym"),
        )
