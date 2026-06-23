"""Composition root for agent desk (Phase 8)."""

from __future__ import annotations

from lms.agent.coordinator import IssueAgentCoordinator
from lms.agent.intent_parser import LLMIntentParser
from lms.api.composition import get_circulation_orchestrator
from lms.api.workflows.return_book import ReturnBookWorkflow
from lms.api.workflows.search_and_issue import SearchAndIssueWorkflow
from lms.config import get_settings
from lms.loan.application.fulfillment_service import FulfillmentService
from lms.shared.auth.deps import DbSession
from lms.shared.observability.tracing import LangfuseTracing


def get_issue_agent_coordinator(session: DbSession) -> IssueAgentCoordinator:
    settings = get_settings()
    tracing = LangfuseTracing(settings)
    orchestrator = get_circulation_orchestrator(session)
    return IssueAgentCoordinator(
        session,
        settings=settings,
        workflow=SearchAndIssueWorkflow(session, orchestrator),
        return_workflow=ReturnBookWorkflow(session, orchestrator),
        fulfillment=FulfillmentService(session),
        parser=LLMIntentParser(settings, tracing=tracing),
        tracing=tracing,
    )
