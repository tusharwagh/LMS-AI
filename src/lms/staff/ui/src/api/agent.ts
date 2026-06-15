import { api } from "./client";
import type { AgentMessageResponse, AgentSessionResponse } from "./types";

export async function createAgentSession(): Promise<AgentSessionResponse> {
  return api<AgentSessionResponse>("/api/v1/agent/issue/sessions", { method: "POST" });
}

export async function sendAgentMessage(
  sessionId: string,
  message: string,
): Promise<AgentMessageResponse> {
  return api<AgentMessageResponse>(`/api/v1/agent/issue/sessions/${sessionId}/message`, {
    method: "POST",
    body: { message },
  });
}

export async function resumeAgentSession(
  sessionId: string,
  approved: boolean,
): Promise<AgentMessageResponse> {
  return api<AgentMessageResponse>(`/api/v1/agent/issue/sessions/${sessionId}/resume`, {
    method: "POST",
    body: { approved },
  });
}
