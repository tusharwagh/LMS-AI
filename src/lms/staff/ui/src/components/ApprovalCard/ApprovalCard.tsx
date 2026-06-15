import { Button } from "@/components/Button/Button";
import styles from "./ApprovalCard.module.css";

interface ApprovalCardProps {
  summary: string;
  onApprove: () => void;
  onDeny: () => void;
  busy?: boolean;
}

export function ApprovalCard({ summary, onApprove, onDeny, busy = false }: ApprovalCardProps) {
  return (
    <div className={styles.panel} role="region" aria-label="Pending approval">
      <p className={styles.summary}>{summary}</p>
      <div className={styles.actions}>
        <Button onClick={onApprove} disabled={busy}>
          Approve
        </Button>
        <Button variant="secondary" onClick={onDeny} disabled={busy}>
          Deny
        </Button>
      </div>
    </div>
  );
}
