"""Composition root for agent desk (Phase 8)."""

from __future__ import annotations

from lms.agent.coordinator import IssueAgentCoordinator
from lms.agent.intent_parser import LLMIntentParser
from lms.api.composition import get_circulation_orchestrator
from lms.api.deps import DbSession
from lms.api.workflows.search_and_issue import SearchAndIssueWorkflow
from lms.config import get_settings
from lms.loan.application.fulfillment_service import FulfillmentService


def get_issue_agent_coordinator(session: DbSession) -> IssueAgentCoordinator:
    settings = get_settings()
    orchestrator = get_circulation_orchestrator(session)
    return IssueAgentCoordinator(
        session,
        settings=settings,
        workflow=SearchAndIssueWorkflow(session, orchestrator),
        fulfillment=FulfillmentService(session),
        parser=LLMIntentParser(settings),
    )
