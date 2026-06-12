"""Agent desk API (Phase 8, REQ-31)."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends

from lms.agent.coordinator import IssueAgentCoordinator
from lms.agent.schemas import (
    AgentMessageRequest,
    AgentMessageResponse,
    AgentResumeRequest,
    AgentSessionResponse,
    PendingApprovalResponse,
)
from lms.api.deps import DbSession
from lms.api.rbac import StaffAuth, require_staff

router = APIRouter(prefix="/agent/issue", dependencies=[require_staff])


def _coordinator(session: DbSession) -> IssueAgentCoordinator:
    return IssueAgentCoordinator(session)


@router.post("/sessions", response_model=AgentSessionResponse, status_code=201)
def create_session(
    auth: StaffAuth,
    coordinator: Annotated[IssueAgentCoordinator, Depends(_coordinator)],
) -> AgentSessionResponse:
    sess = coordinator.start_session(auth.subject)
    return AgentSessionResponse(
        session_id=sess.session_id,
        operator_id=sess.operator_id,
        session_summary={
            "patron_display_name": None,
            "catalog_title": None,
            "holding_barcode": None,
            "fulfillment_mode": sess.slots.fulfillment_mode.value,
            "has_pending_approval": False,
        },
    )


@router.get("/sessions/{session_id}", response_model=AgentSessionResponse)
def get_session(
    session_id: UUID,
    auth: StaffAuth,
    coordinator: Annotated[IssueAgentCoordinator, Depends(_coordinator)],
) -> AgentSessionResponse:
    sess = coordinator.get_session(session_id)
    if sess.operator_id != auth.subject:
        from lms.api.errors import AppError, ErrorCode

        raise AppError(ErrorCode.FORBIDDEN, "Session belongs to another operator", status_code=403)
    return AgentSessionResponse(
        session_id=sess.session_id,
        operator_id=sess.operator_id,
        session_summary=coordinator.session_summary(sess),
    )


@router.post("/sessions/{session_id}/message", response_model=AgentMessageResponse)
def post_message(
    session_id: UUID,
    body: AgentMessageRequest,
    auth: StaffAuth,
    coordinator: Annotated[IssueAgentCoordinator, Depends(_coordinator)],
) -> AgentMessageResponse:
    result = coordinator.handle_message(session_id, body.message, auth.subject)
    pending = None
    if result.pending_approval:
        pending = PendingApprovalResponse(**result.pending_approval)
    return AgentMessageResponse(
        session_id=result.session_id,
        assistant_message=result.assistant_message,
        pending_approval=pending,
        session_summary=result.session_summary,
    )


@router.post("/sessions/{session_id}/resume", response_model=AgentMessageResponse)
def post_resume(
    session_id: UUID,
    body: AgentResumeRequest,
    auth: StaffAuth,
    coordinator: Annotated[IssueAgentCoordinator, Depends(_coordinator)],
) -> AgentMessageResponse:
    result = coordinator.resume(session_id, approved=body.approved, operator_id=auth.subject)
    return AgentMessageResponse(
        session_id=result.session_id,
        assistant_message=result.assistant_message,
        pending_approval=None,
        session_summary=result.session_summary,
    )
