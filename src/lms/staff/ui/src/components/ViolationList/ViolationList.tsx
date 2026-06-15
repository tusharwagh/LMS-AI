import type { ValidationReport } from "@/api/types";
import { Alert } from "@/components/Alert/Alert";

interface ViolationListProps {
  report: ValidationReport;
  successMessage?: string;
}

export function ViolationList({ report, successMessage = "Ready to issue." }: ViolationListProps) {
  if (report.is_valid) {
    return (
      <Alert variant="success" role="status">
        {successMessage}
      </Alert>
    );
  }

  return (
    <Alert variant="warn">
      <p>Validation issues:</p>
      <ul>
        {report.violations.map((v) => (
          <li key={v.rule_id}>{v.message}</li>
        ))}
      </ul>
    </Alert>
  );
}
