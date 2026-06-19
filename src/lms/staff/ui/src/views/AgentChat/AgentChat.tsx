import { useCallback, useEffect, useRef, useState } from "react";

import {
  createAgentSession,
  resumeAgentSession,
  sendAgentMessage,
} from "@/api/agent";
import type { PendingApproval } from "@/api/types";
import { Alert } from "@/components/Alert/Alert";
import { ApprovalCard } from "@/components/ApprovalCard/ApprovalCard";
import { Button } from "@/components/Button/Button";
import { Card } from "@/components/Card/Card";
import {
  FormField,
  textareaClassName,
  actionRowClassName,
  mutedClassName,
} from "@/components/FormField/FormField";
import styles from "./AgentChat.module.css";

interface ChatMessage {
  role: "user" | "assistant";
  content: string;
}

export function AgentChat() {
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

  async function handleSend() {
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
  }

  async function handleResume(approved: boolean) {
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
  }

  return (
    <Card title="AI-assisted issue">
      {disclosure ? <p className={mutedClassName()}>{disclosure}</p> : null}
      {error ? <Alert variant="error">{error}</Alert> : null}
      <div
        ref={chatRef}
        className={styles.chat}
        role="log"
        aria-live="polite"
        aria-relevant="additions"
        aria-label="Agent conversation"
      >
        {messages.length === 0 ? (
          <p className={styles.empty}>Describe the issue in plain language to begin.</p>
        ) : (
          messages.map((msg, index) => (
            <div
              key={`${msg.role}-${index}`}
              className={`${styles.message} ${styles[msg.role]}`}
            >
              {msg.content}
            </div>
          ))
        )}
      </div>
      {pendingApproval ? (
        <ApprovalCard
          summary={pendingApproval.summary}
          onApprove={() => void handleResume(true)}
          onDeny={() => void handleResume(false)}
          busy={busy}
        />
      ) : null}
      <FormField id="agent-input" label="Your message">
        <textarea
          id="agent-input"
          className={textareaClassName()}
          rows={3}
          placeholder="Issue Harry Potter to Riya Sharma, desk pickup"
          value={input}
          onChange={(e) => setInput(e.target.value)}
        />
      </FormField>
      <div className={actionRowClassName()}>
        <Button onClick={() => void handleSend()} disabled={busy}>
          Send
        </Button>
        <Button variant="secondary" onClick={() => void resetSession()} disabled={busy}>
          New session
        </Button>
      </div>
    </Card>
  );
}
