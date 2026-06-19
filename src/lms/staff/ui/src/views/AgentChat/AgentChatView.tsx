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
    conversationRef,
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

        <div className={styles.workspace}>
          <section className={styles.inputPanel} aria-label="Message input">
            <h3 className={styles.panelTitle}>Your message</h3>
            <FormField id="agent-input" label="Type here">
              <textarea
                id="agent-input"
                className={`${textareaClassName()} ${styles.textarea}`}
                rows={8}
                placeholder="Issue Harry Potter to Riya Sharma, desk pickup"
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" && !e.shiftKey) {
                    e.preventDefault();
                    void sendMessage();
                  }
                }}
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
          </section>

          <section className={styles.conversationPanel} aria-label="Conversation">
            <h3 className={styles.panelTitle}>Conversation</h3>
            <div className={styles.conversationFrame}>
              <div
                ref={conversationRef}
                className={styles.conversationScroll}
                role="log"
                aria-live="polite"
                aria-relevant="additions"
                aria-label="Agent conversation"
              >
                {messages.length === 0 && !pendingApproval ? (
                  <p className={styles.empty}>
                    Your messages and assistant replies appear here in order.
                  </p>
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
                {pendingApproval ? (
                  <ApprovalCard
                    summary={pendingApproval.summary}
                    onApprove={() => void resume(true)}
                    onDeny={() => void resume(false)}
                    busy={busy}
                  />
                ) : null}
              </div>
            </div>
          </section>
        </div>
      </Card>
    </PageShell>
  );
}
