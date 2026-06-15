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
import { PageShell } from "@/components/PageShell/PageShell";
import { useAgentChatController } from "@/controllers/useAgentChatController";
import styles from "./AgentChat.module.css";

/** View — AI assist chat presentation (MVC). */
export function AgentChatView() {
  const {
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
  } = useAgentChatController();

  return (
    <PageShell>
      <Card>
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
            onApprove={() => void resume(true)}
            onDeny={() => void resume(false)}
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
          <Button onClick={() => void sendMessage()} disabled={busy}>
            Send
          </Button>
          <Button variant="secondary" onClick={() => void resetSession()} disabled={busy}>
            New session
          </Button>
        </div>
      </Card>
    </PageShell>
  );
}
