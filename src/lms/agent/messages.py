"""Staff-facing messages for the circulation desk agent."""

from __future__ import annotations

from datetime import date

from lms.agent.schemas import IntentAction
from lms.agent.session import PendingActionKind
from lms.loan.domain.enums import FulfillmentMode, FulfillmentStatus

DEFAULT_HELP = (
    "I can help issue or return books. "
    "Try: 'I want to issue a book to [patron]' — I'll help find a copy by subject or area code. "
    "Or 'Search Harry Potter' to find lendable copies, then 'issue to [patron]'. "
    "Or 'Return [title] from [patron]' then 'Complete return'."
)
EMPTY_MESSAGE = (
    "Empty message. "
    "Describe what you need — e.g. issue a book, return a copy, search for a patron, "
    "or scan a barcode."
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
        case IntentAction.ISSUE_TO_PATRON:
            return (
                "Before I can issue this book, I still need a copy. "
                "Search the catalog or scan a barcode first."
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
        case PendingActionKind.COMMIT_RETURN:
            return (
                "Return not completed — you denied approval. "
                "The loan is still open. Scan the barcode again or use the return wizard."
            )
        case PendingActionKind.SELECT_RETURN:
            return (
                "Book selection not confirmed — you denied approval. "
                "Pick another copy from the list or search again."
            )
        case PendingActionKind.INITIATE_RETURN_PICKUP:
            return (
                "Return pick-up not scheduled — you denied approval. "
                "The loan is still open at the desk."
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


def guided_issue_ask_patron() -> str:
    return (
        "I'll help you issue a book. Who is the borrower? "
        "Give me their name, card barcode, or admission number — or say 'cancel' to stop."
    )


def guided_issue_ask_book_criteria(*, patron_name: str | None = None) -> str:
    if patron_name:
        lead = f"I'll help issue a book to {patron_name}."
    else:
        lead = "I'll help you issue a book."
    return (
        f"{lead} What kind of book are you looking for? "
        "Tell me a subject (e.g. science fiction), call number / area code (e.g. FIC ROW), "
        "or DDC code — or say 'cancel' to stop."
    )


def guided_issue_no_books_retry(criteria: str) -> str:
    return (
        f"No lendable copies matched '{criteria}'. "
        "Try a different subject or area code, or say 'cancel' if you want to stop."
    )


def guided_issue_declined() -> str:
    return (
        "Okay — I've stopped looking for a book. "
        "You can start a new search anytime, or use the step-by-step issue wizard."
    )


def guided_desk_ask_patron_for_return() -> str:
    return (
        "The patron wants to return a book. Who are they? "
        "Give me their name, card barcode, admission number, or scan the book barcode — "
        "or say 'cancel' to stop."
    )


def guided_desk_ask_patron() -> str:
    return (
        "I'll help at the desk. Who is the patron? "
        "Give me their name, card barcode, or admission number — or say 'cancel' to stop."
    )


def guided_desk_patron_not_found(query: str) -> str:
    return (
        f"I couldn't find a patron matching '{query}'. "
        "Try a different name or card — or say 'cancel' to stop."
    )


def desk_patron_loans_list(
    patron_name: str,
    items: list[tuple[str, str, str, str, bool]],
    *,
    loan_count: int,
) -> str:
    """Items: (loan_label, title, barcode, due_date, is_overdue)."""
    if loan_count == 0:
        return desk_patron_no_loans(patron_name)
    lines: list[str] = []
    for loan_label, title, barcode, due_date, is_overdue in items[:8]:
        overdue = " (overdue)" if is_overdue else ""
        lines.append(f"• {title} ({barcode}), due {due_date}{overdue} [{loan_label}]")
    noun = "book" if loan_count == 1 else "books"
    return (
        f"{patron_name} has {loan_count} {noun} checked out:\n"
        + "\n".join(lines)
    )


def desk_patron_no_loans(patron_name: str) -> str:
    return f"{patron_name} has no books checked out right now."


def desk_next_actions_prompt(*, patron_name: str, has_loans: bool) -> str:
    actions = [
        "• Return a book — say 'return' and pick from the list (barcode or LOAN_N)",
        "• Issue another book — say 'issue a book'",
        "• Browse the catalog — say 'search catalog'",
        "• Finished — say 'done'",
    ]
    lead = "What would you like to do next?"
    if not has_loans:
        lead = (
            f"What would you like to do for {patron_name}?"
        )
        actions = [
            "• Issue a book — say 'issue a book'",
            "• Browse the catalog — say 'search catalog'",
            "• Finished — say 'done'",
        ]
    return lead + "\n" + "\n".join(actions)


def desk_return_no_loans(patron_name: str) -> str:
    return (
        f"{patron_name} has no books checked out — there's nothing to return right now."
    )


def desk_return_pick_from_list(patron_name: str) -> str:
    return (
        f"Which book is {patron_name} returning? "
        "Tell me the title, barcode, or loan label (e.g. LOAN_1) from the list above."
    )


def desk_return_single_book_ready(
    patron_name: str,
    title: str,
    barcode: str,
    *,
    due_date: str,
    is_overdue: bool,
) -> str:
    overdue_note = " This copy is overdue." if is_overdue else ""
    return (
        f"{patron_name} is returning {title} ({barcode}), due {due_date}.{overdue_note} "
        "Say 'complete return' when you're ready — you'll review and approve before check-in."
    )


def desk_pick_book_to_return() -> str:
    return (
        "Which book should we return? Tell me the title, barcode, or loan label "
        "(e.g. LOAN_1) from the list above."
    )


def desk_session_done(patron_name: str | None = None) -> str:
    if patron_name:
        return f"All set for {patron_name}. Let me know when the next patron is at the desk."
    return "All set. Let me know when the next patron is at the desk."


def guided_desk_declined() -> str:
    return (
        "Okay — I've ended this desk session. "
        "Start again anytime when a patron is at the counter."
    )


def guided_catalog_ask_criteria() -> str:
    return (
        "I'll help you browse the catalog. What are you looking for? "
        "Tell me a subject (e.g. science fiction), call number / area code (e.g. FIC ROW), "
        "DDC code, or title — or say 'cancel' to stop."
    )


def guided_catalog_no_match_retry(criteria: str) -> str:
    return (
        f"No lendable copies matched '{criteria}'. "
        "Try a different subject or area code, or say 'cancel' if you want to stop."
    )


def guided_catalog_declined() -> str:
    return (
        "Okay — I've stopped browsing the catalog. "
        "You can start a new search anytime, or use the step-by-step issue wizard."
    )


def catalog_browse_candidates_list(
    items: list[tuple[str, str, str, str | None]],
    *,
    query: str | None = None,
) -> str:
    """Items: (copy_label, title, barcode, shelf)."""
    lines: list[str] = []
    for copy_label, title, barcode, shelf in items[:5]:
        shelf_note = f", shelf {shelf}" if shelf else ""
        lines.append(f"• {title} ({barcode}){shelf_note} [{copy_label}]")
    lead = f"I found {len(items)} lendable copies"
    if query:
        lead += f" matching '{query}'"
    lead += ":"
    return (
        f"{lead}\n"
        + "\n".join(lines)
        + "\nTell me which copy — by barcode, title, or copy label (e.g. COPY_1)."
    )


def catalog_browse_single_copy(
    title: str,
    barcode: str,
    query: str,
    *,
    shelf: str | None = None,
) -> str:
    shelf_note = f" on shelf {shelf}" if shelf else ""
    return (
        f"Found one lendable copy of '{title}' ({barcode}){shelf_note} matching '{query}'."
    )


def catalog_browse_copy_selected(title: str, barcode: str) -> str:
    return f"Selected {title} ({barcode}) from the catalog browse."


def guided_patron_lookup_ask() -> str:
    return (
        "I'll help you look up a patron. "
        "Give me their name, card barcode, or admission number — or say 'cancel' to stop."
    )


def guided_patron_found(
    display_name: str,
    *,
    card_barcode: str | None = None,
    external_ref: str | None = None,
    query: str | None = None,
) -> str:
    if query:
        lead = f"I found {display_name} matching '{query}'."
    else:
        lead = f"Here is {display_name}."
    details: list[str] = []
    if card_barcode:
        details.append(f"card {card_barcode}")
    if external_ref:
        details.append(f"admission {external_ref}")
    if details:
        lead += f" ({', '.join(details)})"
    return lead


def guided_patron_lookup_candidates_list(
    items: list[tuple[str, str, str | None, str | None]],
    *,
    query: str | None = None,
) -> str:
    """Items: (patron_label, display_name, card_barcode, external_ref)."""
    lines: list[str] = []
    for patron_label, name, card, adm in items[:5]:
        extras: list[str] = []
        if card:
            extras.append(f"card {card}")
        if adm:
            extras.append(f"adm {adm}")
        extra_note = f" ({', '.join(extras)})" if extras else ""
        lines.append(f"• {name}{extra_note} [{patron_label}]")
    lead = f"I found {len(items)} patrons"
    if query:
        lead += f" matching '{query}'"
    lead += ":"
    return (
        f"{lead}\n"
        + "\n".join(lines)
        + "\nTell me which patron — by name, card, or patron label (e.g. PATRON_1)."
    )


def guided_patron_lookup_retry(query: str) -> str:
    return (
        f"No patrons matched '{query}'. "
        "Try a different name, card number, or admission number — "
        "or say 'cancel' if you want to stop."
    )


def guided_patron_lookup_declined() -> str:
    return (
        "Okay — I've stopped the patron lookup. "
        "You can search again anytime, or use the reference desk tools."
    )


def patron_selection_not_found(hint: str) -> str:
    return (
        f"No patron in this session matched '{hint}'. "
        "Use a name or patron label from the list, or search again."
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


def catalog_candidates_list(
    items: list[tuple[str, str, str, str | None]],
    *,
    query: str | None = None,
) -> str:
    """Items: (copy_label, title, barcode, shelf)."""
    lines: list[str] = []
    for copy_label, title, barcode, shelf in items[:5]:
        shelf_note = f", shelf {shelf}" if shelf else ""
        lines.append(f"• {title} ({barcode}){shelf_note} [{copy_label}]")
    lead = f"I found {len(items)} lendable copies"
    if query:
        lead += f" matching '{query}'"
    lead += ":"
    return (
        f"{lead}\n"
        + "\n".join(lines)
        + "\nWhich copy should we issue? Tell me the barcode, title, or copy label (e.g. COPY_1)."
    )


def catalog_single_copy_ask_issue(
    title: str,
    barcode: str,
    query: str,
    *,
    shelf: str | None = None,
) -> str:
    shelf_note = f" on shelf {shelf}" if shelf else ""
    return (
        f"Found one lendable copy of '{title}' ({barcode}){shelf_note} matching '{query}'. "
        "Would you like to issue it? Say 'issue to [patron name]' — "
        "add 'desk pickup' or 'deliver to Class 5A' for fulfillment."
    )


def catalog_copy_selected_ask_patron(title: str, barcode: str) -> str:
    return (
        f"Selected {title} ({barcode}) for issue. "
        "Which patron should borrow it? Say 'issue to [patron name]' "
        "— add 'desk pickup' or 'deliver to Class 5A' if needed."
    )


def catalog_selection_not_found(hint: str) -> str:
    return (
        f"No lendable copy in this session matched '{hint}'. "
        "Use a barcode or copy label from the list, or search the catalog again."
    )


def issue_patron_resolved_ready(
    patron_name: str,
    title: str,
    barcode: str,
    *,
    mode: FulfillmentMode,
) -> str:
    mode_label = fulfillment_mode_label(mode)
    return (
        f"{patron_name} can borrow {title} ({barcode}) — {mode_label}. "
        "Say 'issue' when you're ready — you'll review and approve before checkout."
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


def no_open_loan_for_return(barcode: str, detail: str) -> str:
    return (
        f"No open loan found for barcode {barcode}: {detail}. "
        "Check the barcode, confirm the book is on loan, or use the return wizard."
    )


def missing_loan_for_return() -> str:
    return (
        "To complete a return, scan or enter the copy barcode first — "
        "for example, 'Return barcode ABC-123'."
    )


def return_lookup_success(
    patron_name: str,
    title: str,
    barcode: str,
    *,
    due_date: date,
    is_overdue: bool,
    scanned: str,
    open_loans: int,
) -> str:
    due_label = due_date.isoformat()
    overdue_note = " This copy is overdue." if is_overdue else ""
    extra_loans = ""
    if open_loans > 1:
        extra_loans = f" {patron_name} has {open_loans} books out in total."
    return (
        f"Barcode {scanned} — {title} ({barcode}) is on loan to {patron_name}. "
        f"Due {due_label}.{overdue_note}{extra_loans} "
        "Say 'complete return' for a desk check-in, or 'schedule pickup' to collect from class."
    )


def return_commit_approval_summary(patron_name: str, title: str, barcode: str) -> str:
    return f"Return {title} ({barcode}) from {patron_name} at the desk."


def return_commit_approval_prompt(summary: str) -> str:
    return (
        f"{summary} Review and approve to check in the copy, or deny to keep the loan open."
    )


def return_pickup_approval_summary(patron_name: str, title: str, barcode: str) -> str:
    return f"Schedule class pick-up to return {title} ({barcode}) from {patron_name}."


def return_pickup_approval_prompt(summary: str) -> str:
    return (
        f"{summary} Review and approve to start pick-up, or deny to keep the loan open."
    )


def return_committed(patron_name: str, title: str, barcode: str) -> str:
    return f"Done — {title} ({barcode}) is checked in from {patron_name}."


def return_blocked(reason: str) -> str:
    return (
        f"This return cannot proceed: {reason}. "
        "Resolve the problem or use the step-by-step return wizard."
    )


def return_pickup_blocked(reason: str) -> str:
    return (
        f"Return pick-up cannot be scheduled: {reason}. "
        "Try a desk return or use the return wizard."
    )


def return_pickup_scheduled(
    patron_name: str,
    title: str,
    barcode: str,
    *,
    status_label: str,
) -> str:
    return (
        f"Pick-up scheduled for {title} ({barcode}) from {patron_name}. "
        f"Status is {status_label}."
    )


def no_open_loans_for_return_search(*, patron_query: str | None, title_query: str | None) -> str:
    parts: list[str] = []
    if patron_query:
        parts.append(f"patron '{patron_query}'")
    if title_query:
        parts.append(f"title '{title_query}'")
    scope = " and ".join(parts) if parts else "that search"
    return (
        f"No open loans matched {scope}. "
        "Try a different name or title, scan a barcode, or use the return wizard."
    )


def return_candidates_list(
    items: list[tuple[str, str, str, str, str, bool]],
    *,
    query: str | None = None,
) -> str:
    """Items: (loan_label, title, barcode, patron, due_date, is_overdue)."""
    lines: list[str] = []
    for loan_label, title, barcode, patron, due_date, is_overdue in items[:5]:
        overdue = " (overdue)" if is_overdue else ""
        lines.append(f"• {title} ({barcode}) — {patron}, due {due_date}{overdue} [{loan_label}]")
    lead = f"I found {len(items)} open loans"
    if query:
        lead += f" matching '{query}'"
    lead += ":"
    return (
        f"{lead}\n"
        + "\n".join(lines)
        + "\nTell me which copy — by title, barcode, or loan label (e.g. LOAN_1). "
        "I'll ask you to confirm before check-in."
    )


def return_single_candidate_ready(
    patron_name: str,
    title: str,
    barcode: str,
    *,
    due_date: date,
    is_overdue: bool,
) -> str:
    overdue_note = " This copy is overdue." if is_overdue else ""
    return (
        f"Found one open loan: {title} ({barcode}) to {patron_name}, due {due_date.isoformat()}."
        f"{overdue_note} Say 'complete return' for desk check-in, or 'schedule pickup'."
    )


def return_selection_ambiguous(count: int) -> str:
    noun = "loan" if count == 1 else "loans"
    return (
        f"That still matches {count} open {noun}. "
        "Be more specific — use the barcode or loan label from the list."
    )


def return_selection_not_found(hint: str) -> str:
    return (
        f"No open loan in this session matched '{hint}'. "
        "Use a barcode or loan label from the list, or search again."
    )


def return_select_approval_summary(
    patron_name: str,
    title: str,
    barcode: str,
    *,
    due_date: date,
) -> str:
    return (
        f"Confirm return of {title} ({barcode}) from {patron_name} — due {due_date.isoformat()}."
    )


def return_select_approval_prompt(summary: str) -> str:
    return (
        f"{summary} Review and approve to select this copy, or deny to pick another."
    )


def return_select_confirmed(title: str, barcode: str, patron_name: str) -> str:
    return (
        f"Selected {title} ({barcode}) from {patron_name}. "
        "Say 'complete return' when you're ready to check in at the desk."
    )


def return_workflow_rolled_back(reason: str) -> str:
    return (
        f"Return could not be completed: {reason}. "
        "Nothing was changed — you can try again or use the return wizard."
    )


def help_for_unknown_intent(user_message: str) -> str:
    snippet = user_message.strip()
    if len(snippet) > 80:
        snippet = f"{snippet[:77]}..."
    return (
        f"I'm not sure how to help with \"{snippet}\" yet. "
        "You can search for a patron by name, search for a book, scan a barcode, "
        "ask 'What books are issued to [patron]?', "
        "say 'Issue [book] to [patron], desk pickup', or 'Return [title] from [patron]'."
    )


def greeting_reply() -> str:
    return (
        "Hello! I can help issue or return books — search by name, "
        "find a title, scan a barcode, ask what books are issued to a patron, "
        "or say something like "
        "'Issue [book] to [patron], desk pickup' or 'Return barcode [copy barcode]'."
    )


def help_reply(user_message: str) -> str:
    lower = user_message.strip().lower()
    if "issue" in lower or "checkout" in lower or "lend" in lower:
        return (
            "To issue a book, say 'I want to issue a book to [patron name]' — "
            "I'll ask what subject or area code to search. "
            "Or give title and patron together: "
            "'Issue Harry Potter to Riya Sharma, desk pickup'. "
            "I'll find the patron and copy, then ask you to review before checkout."
        )
    if "search" in lower or "find" in lower or "patron" in lower:
        return (
            "To find a book, say 'search [title]' — I'll list lendable copies with barcodes. "
            "Pick a copy, then say 'issue to [patron name]'. "
            "To find a patron first, type their name, card number, or admission number."
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
    if "return" in lower or "check in" in lower or "check-in" in lower:
        return (
            "To return a book, scan or enter the copy barcode — "
            "for example, 'Return barcode ABC-123'. "
            "I'll show who has it and when it's due, then ask you to approve the check-in."
        )
    if (
        "issued" in lower
        or "checked out" in lower
        or "on loan" in lower
        or "have out" in lower
        or "open loan" in lower
    ):
        return (
            "To see what a patron currently has out, ask "
            "'What books are issued to [patron name]?' or 'Show open loans for [name]'. "
            "I'll list their checked-out books and offer return, issue, or catalog next steps."
        )
    return help_for_unknown_intent(user_message)


def turn_acknowledged(user_message: str) -> str:
    snippet = user_message.strip()
    if len(snippet) > 60:
        snippet = f"{snippet[:57]}..."
    return f"Got it — \"{snippet}\". {DEFAULT_HELP}"
