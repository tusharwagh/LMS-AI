import { formatPatronStatus, patronIdentifiers } from "@/lib/format";
import type { PatronSummary, ValidationReport } from "@/api/types";
import { ViolationList } from "@/components/ViolationList/ViolationList";
import styles from "./PatronSummary.module.css";

interface PatronSummaryProps {
  patron: PatronSummary;
  validation?: ValidationReport | null;
  extra?: React.ReactNode;
}

export function PatronSummaryView({ patron, validation, extra }: PatronSummaryProps) {
  const ids = patronIdentifiers(patron);
  const typeLine = [patron.patron_type_name, patron.class_section_label]
    .filter(Boolean)
    .join(" · ");

  return (
    <div className={styles.wrap}>
      <p className={styles.name}>{patron.display_name}</p>
      {ids ? <p className={styles.meta}>{ids}</p> : null}
      {typeLine ? <p className={styles.meta}>{typeLine}</p> : null}
      <p className={styles.meta}>
        Status: {formatPatronStatus(patron.status)}
        {patron.blocked ? " · Blocked from borrowing" : ""}
      </p>
      {validation ? <ViolationList report={validation} /> : null}
      {extra}
    </div>
  );
}
