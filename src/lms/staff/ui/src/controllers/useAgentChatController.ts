import { useCallback, useEffect, useRef, useState } from "react";

import { createAgentSession, resumeAgentSession, sendAgentMessage } from "@/models";
import type { PendingApproval } from "@/models";

export interface ChatMessage {
  role: "user" | "assistant";
  content: string;
}

/** Controller — agent chat session, messages, and HITL approval (MVC). */
export function useAgentChatController() {
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [pendingApproval, setPendingApproval] = useState<PendingApproval | null>(null);
  const [disclosure, setDisclosure] = useState<string | null>(null);
  const [input, setInput] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const chatRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = useCallback(() => {
    const el = chatRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, []);

  useEffect(() => {
    scrollToBottom();
  }, [messages, pendingApproval, scrollToBottom]);

  const ensureSession = useCallback(async () => {
    if (sessionId) return sessionId;
    const res = await createAgentSession();
    setSessionId(res.session_id);
    return res.session_id;
  }, [sessionId]);

  const resetSession = useCallback(async () => {
    setSessionId(null);
    setMessages([]);
    setPendingApproval(null);
    setDisclosure(null);
    setError(null);
    setInput("");
    try {
      const res = await createAgentSession();
      setSessionId(res.session_id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not start session");
    }
  }, []);

  useEffect(() => {
    void ensureSession().catch((err) => {
      setError(err instanceof Error ? err.message : "Could not start session");
    });
  }, [ensureSession]);

  const sendMessage = useCallback(async () => {
    const text = input.trim();
    if (!text) return;
    setError(null);
    setBusy(true);
    setInput("");
    setMessages((prev) => [...prev, { role: "user", content: text }]);
    try {
      const sid = await ensureSession();
      const res = await sendAgentMessage(sid, text);
      setDisclosure(res.agent_disclosure);
      setMessages((prev) => [...prev, { role: "assistant", content: res.assistant_message }]);
      setPendingApproval(res.pending_approval ?? null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Request failed");
    } finally {
      setBusy(false);
    }
  }, [ensureSession, input]);

  const resume = useCallback(
    async (approved: boolean) => {
      if (!sessionId) return;
      setError(null);
      setBusy(true);
      try {
        const res = await resumeAgentSession(sessionId, approved);
        setDisclosure(res.agent_disclosure);
        setMessages((prev) => [...prev, { role: "assistant", content: res.assistant_message }]);
        setPendingApproval(null);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Request failed");
      } finally {
        setBusy(false);
      }
    },
    [sessionId],
  );

  return {
    chatRef,
    messages,
    pendingApproval,
    disclosure,
    input,
    setInput,
    error,
    busy,
    sendMessage,
    resume,
    resetSession,
  };
}
