"""Staff-facing messages for the issue desk agent."""

from __future__ import annotations

from lms.agent.schemas import IntentAction
from lms.agent.session import PendingActionKind
from lms.loan.domain.enums import FulfillmentMode, FulfillmentStatus

DEFAULT_HELP = (
    "I can help issue a book to a patron. "
    "Try: 'Issue [title] to [patron name], desk pickup' "
    "or search for a patron by name first."
)
EMPTY_MESSAGE = (
    "Empty message. "
    "Describe what you need — e.g. issue a book, search for a patron, or scan a barcode."
)

_FULFILLMENT_STATUS_LABELS: dict[FulfillmentStatus, str] = {
    FulfillmentStatus.READY: "ready for dispatch",
    FulfillmentStatus.IN_TRANSIT: "in transit",
    FulfillmentStatus.COMPLETED: "delivered",
}

_FULFILLMENT_MODE_LABELS: dict[FulfillmentMode, str] = {
    FulfillmentMode.DESK: "desk pickup",
    FulfillmentMode.DELIVERY: "class delivery",
    FulfillmentMode.PICKUP_POINT: "pickup point",
}


def _format_list(items: list[str], *, limit: int = 3) -> str:
    shown = items[:limit]
    if len(shown) == 1:
        return shown[0]
    if len(shown) == 2:
        return f"{shown[0]} and {shown[1]}"
    extra = len(items) - limit
    if extra > 0:
        return f"{', '.join(shown)}, and {extra} more"
    return f"{', '.join(shown[:-1])}, and {shown[-1]}"


def fulfillment_mode_label(mode: FulfillmentMode) -> str:
    return _FULFILLMENT_MODE_LABELS.get(mode, mode.value.lower().replace("_", " "))


def missing_patron_for(action: IntentAction) -> str:
    match action:
        case IntentAction.SEARCH_CATALOG:
            return (
                "To search for a copy, I still need a patron. "
                "Search by name, card number, or admission number."
            )
        case IntentAction.SELECT_BARCODE:
            return (
                "To select this barcode, I still need a patron. "
                "Search by name, card number, or admission number."
            )
        case IntentAction.REQUEST_COMMIT:
            return (
                "Before I can issue this book, I still need a patron. "
                "Search by name, card number, or admission number."
            )
        case _:
            return (
                "I still need a patron for this step. "
                "Search by name, card number, or admission number."
            )


def missing_copy_for(action: IntentAction) -> str:
    match action:
        case IntentAction.REQUEST_COMMIT:
            return (
                "Before I can issue this book, I still need a copy. "
                "Search for the title or scan/enter a barcode."
            )
        case IntentAction.SELECT_BARCODE:
            return (
                "That barcode did not match an available copy. "
                "Scan or enter a valid barcode, or search for the title."
            )
        case _:
            return (
                "I still need a copy for this step. "
                "Search for the title or scan/enter a barcode."
            )


def missing_slots_for_commit(*, missing_patron: bool, missing_copy: bool) -> str:
    if missing_patron and missing_copy:
        return (
            "Before I can issue this book, I need a patron and a copy. "
            "Search for the patron and title, or scan a barcode."
        )
    if missing_patron:
        return (
            "Before I can issue this book, I still need a patron. "
            "Search by name, card number, or admission number."
        )
    return (
        "Before I can issue this book, I still need a copy. "
        "Search for the title or scan/enter a barcode."
    )


def patron_search_empty() -> str:
    return (
        "Your patron search didn't include a name or number. "
        "Enter a name, scan a card, or type an admission number."
    )


def no_open_loan_for_cancel() -> str:
    return (
        "To cancel a loan, I need an issued book in this session. "
        "Issue a book first, or use the step-by-step wizard to cancel an existing loan."
    )


def no_fulfillment_for_status_check() -> str:
    return (
        "To check delivery status, complete an issue with delivery mode first."
    )


def no_fulfillment_for_transition() -> str:
    return (
        "To update delivery status, complete a delivery issue first, "
        "then ask for a status change."
    )


def approval_denied(kind: PendingActionKind) -> str:
    match kind:
        case PendingActionKind.COMMIT_ISSUE:
            return (
                "Issue not completed — you denied approval. "
                "Adjust patron or copy and try again, or use the step-by-step wizard."
            )
        case PendingActionKind.CANCEL_ISSUE:
            return (
                "Cancel not completed — you denied approval. "
                "The loan remains active."
            )
        case PendingActionKind.TRANSITION_FULFILLMENT:
            return (
                "Delivery update not completed — you denied approval. "
                "The current delivery status is unchanged."
            )


def no_patron_found(query: str) -> str:
    return (
        f"No patrons matched '{query}'. "
        "Try a different name, card number, or admission number."
    )


def no_lendable_copies(query: str) -> str:
    return (
        f"No lendable copies matched '{query}'. "
        "Try another search term or check availability in the step-by-step wizard."
    )


def patron_cannot_borrow(display_name: str, reasons: str) -> str:
    return (
        f"{display_name} cannot borrow right now: {reasons}. "
        "Resolve the block with an administrator or choose another patron."
    )


def patron_eligible(display_name: str, *, query: str | None = None) -> str:
    if query:
        lead = f"I found {display_name} matching '{query}'."
    else:
        lead = f"{display_name} is ready to borrow."
    return (
        f"{lead} Search for a title or scan a barcode to continue this issue."
    )


def patron_search_results(query: str, count: int, names: list[str]) -> str:
    preview = _format_list(names)
    noun = "patron" if count == 1 else "patrons"
    return (
        f"I found {count} {noun} matching '{query}': {preview}. "
        "Tell me which one by name, or scan their library card."
    )


def catalog_search_results(query: str, count: int, titles: list[str]) -> str:
    preview = _format_list(titles)
    noun = "copy" if count == 1 else "copies"
    return (
        f"Found {count} lendable {noun} matching '{query}': {preview}. "
        "Tell me which barcode to issue, or scan one."
    )


def single_copy_for_issue(title: str, barcode: str, query: str) -> str:
    return (
        f"Found one lendable copy of '{title}' ({barcode}) matching '{query}'. "
        "Confirm pickup or delivery, then ask to issue when ready."
    )


def copy_selected(title: str, barcode: str, *, scanned: str | None = None) -> str:
    if scanned:
        lead = f"Barcode {scanned} selected {title} ({barcode}) for this issue."
    else:
        lead = f"Selected {title} ({barcode}) for this issue."
    return f"{lead} Confirm pickup or delivery, then ask to issue when ready."


def barcode_not_available(barcode: str, detail: str) -> str:
    return (
        f"Barcode {barcode} is not available: {detail}. "
        "Scan a different copy or search for the title."
    )


def issue_blocked_for_commit(reasons: str) -> str:
    return (
        f"This issue cannot proceed: {reasons}. "
        "Resolve the problem or choose a different patron or copy."
    )


def issue_ready(patron_name: str, title: str, barcode: str) -> str:
    return (
        f"{patron_name} can borrow {title} ({barcode}). "
        "Say 'issue' when you're ready — you'll review and approve before checkout."
    )


def ready_to_issue() -> str:
    return (
        "Patron and copy are ready for this issue. "
        "Say 'issue' when you're ready — you'll review and approve before checkout."
    )


def commit_approval_summary(
    patron_name: str,
    title: str,
    barcode: str,
    mode: FulfillmentMode,
) -> str:
    mode_label = fulfillment_mode_label(mode)
    return f"Issue {title} ({barcode}) to {patron_name} — {mode_label}."


def commit_approval_prompt(summary: str) -> str:
    return (
        f"{summary} Review and approve to complete the issue, or deny to make changes."
    )


def cancel_approval_summary(patron_name: str, title: str, barcode: str) -> str:
    return f"Cancel the issue of {title} ({barcode}) to {patron_name}."


def cancel_approval_prompt(summary: str) -> str:
    return (
        f"{summary} Review and approve to cancel the loan, or deny to keep it."
    )


def fulfillment_transition_prompt(
    target: FulfillmentStatus,
    *,
    title: str | None = None,
) -> str:
    label = _FULFILLMENT_STATUS_LABELS.get(
        target,
        target.value.lower().replace("_", " "),
    )
    book = f" for {title}" if title else ""
    return (
        f"Mark delivery{book} as {label}. "
        "Review and approve to update, or deny to keep the current status."
    )


def fulfillment_mode_set(mode: FulfillmentMode) -> str:
    label = fulfillment_mode_label(mode)
    return (
        f"Pickup/delivery set to {label} for this issue. "
        "Select patron and copy, then ask to issue when ready."
    )


def issue_committed(
    patron_name: str,
    title: str,
    barcode: str,
    *,
    delivery_status: str | None = None,
) -> str:
    msg = f"Done — {title} ({barcode}) is now issued to {patron_name}."
    if delivery_status:
        msg += f" Delivery is {delivery_status}."
    return msg


def issue_cancelled(patron_name: str, title: str, barcode: str) -> str:
    return f"The issue of {title} ({barcode}) to {patron_name} has been cancelled."


def delivery_status_check(status_label: str, *, title: str | None = None) -> str:
    book = f" for {title}" if title else ""
    return (
        f"Delivery{book} is {status_label}. "
        "Say 'mark ready', 'in transit', or 'complete' to request an update."
    )


def delivery_updated(status_label: str, *, title: str | None = None) -> str:
    book = f" for {title}" if title else ""
    return f"Delivery{book} updated — status is now {status_label}."


def help_for_unknown_intent(user_message: str) -> str:
    snippet = user_message.strip()
    if len(snippet) > 80:
        snippet = f"{snippet[:77]}..."
    return (
        f"I'm not sure how to help with \"{snippet}\" yet. "
        "You can search for a patron by name, search for a book, scan a barcode, "
        "or say something like 'Issue [book] to [patron], desk pickup'."
    )


def greeting_reply() -> str:
    return (
        "Hello! I can help issue books to patrons — search by name, "
        "find a title, scan a barcode, or say something like "
        "'Issue [book] to [patron], desk pickup'."
    )


def help_reply(user_message: str) -> str:
    lower = user_message.strip().lower()
    if "issue" in lower or "checkout" in lower or "lend" in lower:
        return (
            "To issue a book, tell me the title and patron — for example: "
            "'Issue Harry Potter to Riya Sharma, desk pickup' "
            "or 'deliver to Class 5A'. I'll find the patron and copy, "
            "then ask you to review before checkout."
        )
    if "search" in lower or "find" in lower or "patron" in lower:
        return (
            "To find a patron, type their name, card number, or admission number. "
            "To find a book, say 'search [title]' or scan a barcode."
        )
    if "cancel" in lower:
        return (
            "To cancel a loan from this session, say 'Cancel the issue' "
            "after a book has been checked out. You'll review before it is removed."
        )
    if "deliver" in lower or "delivery" in lower or "transit" in lower:
        return (
            "For delivery issues, include delivery in your issue request — "
            "for example, 'Issue [book] to [patron], deliver to Class 5A'. "
            "After checkout, say 'mark ready', 'in transit', or 'complete' to update status."
        )
    return help_for_unknown_intent(user_message)


def turn_acknowledged(user_message: str) -> str:
    snippet = user_message.strip()
    if len(snippet) > 60:
        snippet = f"{snippet[:57]}..."
    return f"Got it — \"{snippet}\". {DEFAULT_HELP}"
