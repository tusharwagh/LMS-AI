"""Browser E2E tests for React staff desk (login, issue wizard, return wizard, agent assist)."""

from __future__ import annotations

import re

import pytest
from playwright.sync_api import Page, expect

from tests.e2e.conftest import staff_login

pytestmark = [pytest.mark.e2e, pytest.mark.playwright]


def test_staff_login_flow(page: Page, staff_server: str) -> None:
    page.goto(f"{staff_server}/staff/")
    expect(page.get_by_role("heading", name="LMS-AI Staff Desk")).to_be_visible()
    staff_login(page, staff_server)
    expect(page.get_by_role("button", name="Issue book")).to_have_attribute("aria-current", "page")
    expect(page.get_by_text("librarian", exact=False)).to_be_visible()


def test_issue_wizard_desk_commit(
    page: Page,
    staff_server: str,
    issue_fixture: dict[str, str],
) -> None:
    staff_login(page, staff_server)

    page.get_by_label("Card barcode").fill(issue_fixture["card"])
    page.get_by_role("button", name="Find patron").click()
    expect(page.get_by_text(issue_fixture["patron_name"])).to_be_visible()

    page.get_by_label("Search title / ISBN / call no.").fill(issue_fixture["title"])
    page.get_by_role("button", name="Search lendable copies").click()
    page.get_by_text(issue_fixture["title"]).click()

    page.get_by_text(issue_fixture["barcode"]).click()
    expect(page.get_by_role("button", name="Commit issue")).to_be_enabled()
    page.get_by_role("button", name="Commit issue").click()

    expect(page.get_by_role("status")).to_contain_text("issued to")
    expect(page.get_by_role("status")).to_contain_text(issue_fixture["patron_name"])
    expect(page.get_by_role("status")).to_contain_text(issue_fixture["title"])


def test_return_wizard_desk_return(
    page: Page,
    staff_server: str,
    issued_loan_fixture: dict[str, str],
) -> None:
    staff_login(page, staff_server)
    page.get_by_role("button", name="Return book").click()
    expect(page.get_by_role("heading", name="Return a book")).to_be_visible()

    page.get_by_label("Holding barcode").fill(issued_loan_fixture["barcode"])
    page.get_by_role("button", name="Look up loan").click()
    expect(page.get_by_text(issued_loan_fixture["patron_name"])).to_be_visible()
    expect(page.get_by_text(issued_loan_fixture["title"])).to_be_visible()

    page.get_by_role("button", name="Complete return").click()
    expect(page.get_by_role("status")).to_contain_text("available again")
    expect(page.get_by_role("status")).to_contain_text(issued_loan_fixture["title"])


def test_agent_assist_pending_approval(
    page: Page,
    agent_staff_server: str,
    issue_fixture: dict[str, str],
) -> None:
    staff_login(page, agent_staff_server)
    page.get_by_role("button", name="AI assist").click()
    expect(page.get_by_role("heading", name="AI-assisted issue")).to_be_visible()

    message = (
        f"Issue {issue_fixture['title']} to {issue_fixture['patron_name']}, desk pickup"
    )
    page.get_by_label("Your message").fill(message)
    page.get_by_role("button", name="Send").click()

    chat = page.get_by_role("log", name="Agent conversation")
    expect(chat).to_contain_text(message, timeout=15_000)

    approval = page.get_by_role("region", name="Pending approval")
    expect(approval).to_be_visible(timeout=15_000)
    expect(approval).to_contain_text(issue_fixture["title"])
    expect(approval).to_contain_text(issue_fixture["patron_name"])
    expect(approval).to_contain_text(re.compile(r"approve", re.I))


def test_agent_assist_hitl_approve_commit(
    page: Page,
    agent_staff_server: str,
    issue_fixture: dict[str, str],
) -> None:
    staff_login(page, agent_staff_server)
    page.get_by_role("button", name="AI assist").click()

    message = (
        f"Issue {issue_fixture['title']} to {issue_fixture['patron_name']}, desk pickup"
    )
    page.get_by_label("Your message").fill(message)
    page.get_by_role("button", name="Send").click()

    approval = page.get_by_role("region", name="Pending approval")
    expect(approval).to_be_visible(timeout=15_000)
    page.get_by_role("button", name="Approve").click()

    chat = page.get_by_role("log", name="Agent conversation")
    expect(chat).to_contain_text(re.compile(r"issued", re.I), timeout=15_000)
    expect(chat).to_contain_text(issue_fixture["patron_name"])
    expect(chat).to_contain_text(issue_fixture["title"])
    expect(page.get_by_role("region", name="Pending approval")).not_to_be_visible()
