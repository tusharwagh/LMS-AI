"""Agent desk API (Phase 8, REQ-31)."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends

from lms.agent.coordinator import AgentTurnResult, IssueAgentCoordinator
from lms.agent.schemas import (
    AgentMessageRequest,
    AgentMessageResponse,
    AgentResumeRequest,
    AgentSessionResponse,
    PendingApprovalResponse,
)
from lms.agent.session import AgentIssueSession
from lms.api.agent_composition import get_issue_agent_coordinator
from lms.platform.auth.rbac import StaffAuth, require_staff
from lms.shared.auth.deps import DbSession

router = APIRouter(prefix="/agent/issue", dependencies=[require_staff])


def _coordinator(session: DbSession) -> IssueAgentCoordinator:
    return get_issue_agent_coordinator(session)


def _session_response(
    coordinator: IssueAgentCoordinator,
    sess: AgentIssueSession,
) -> AgentSessionResponse:
    return AgentSessionResponse(
        session_id=sess.session_id,
        operator_id=sess.operator_id,
        session_summary=coordinator.session_summary(sess),
    )


def _message_response(result: AgentTurnResult) -> AgentMessageResponse:
    pending = None
    if result.pending_approval:
        pending = PendingApprovalResponse(**result.pending_approval)
    return AgentMessageResponse(
        session_id=result.session_id,
        assistant_message=result.assistant_message,
        pending_approval=pending,
        session_summary=result.session_summary,
    )


@router.post("/sessions", response_model=AgentSessionResponse, status_code=201)
def create_session(
    auth: StaffAuth,
    coordinator: Annotated[IssueAgentCoordinator, Depends(_coordinator)],
) -> AgentSessionResponse:
    sess = coordinator.start_session(auth.subject)
    return _session_response(coordinator, sess)


@router.get("/sessions/{session_id}", response_model=AgentSessionResponse)
def get_session(
    session_id: UUID,
    auth: StaffAuth,
    coordinator: Annotated[IssueAgentCoordinator, Depends(_coordinator)],
) -> AgentSessionResponse:
    sess = coordinator.get_session_for_operator(session_id, auth.subject)
    return _session_response(coordinator, sess)


@router.post("/sessions/{session_id}/message", response_model=AgentMessageResponse)
def post_message(
    session_id: UUID,
    body: AgentMessageRequest,
    auth: StaffAuth,
    coordinator: Annotated[IssueAgentCoordinator, Depends(_coordinator)],
) -> AgentMessageResponse:
    result = coordinator.handle_message(session_id, body.message, auth.subject)
    return _message_response(result)


@router.post("/sessions/{session_id}/resume", response_model=AgentMessageResponse)
def post_resume(
    session_id: UUID,
    body: AgentResumeRequest,
    auth: StaffAuth,
    coordinator: Annotated[IssueAgentCoordinator, Depends(_coordinator)],
) -> AgentMessageResponse:
    result = coordinator.resume(session_id, approved=body.approved, operator_id=auth.subject)
    return _message_response(result)
