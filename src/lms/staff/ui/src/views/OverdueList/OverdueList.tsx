import { useCallback, useEffect, useState } from "react";

import { fetchOverdueLoans } from "@/api/loan";
import type { OverdueLoan } from "@/api/types";
import { Alert } from "@/components/Alert/Alert";
import { Button } from "@/components/Button/Button";
import { Card } from "@/components/Card/Card";
import { PageShell } from "@/components/PageShell/PageShell";
import { mutedClassName } from "@/components/FormField/FormField";
import styles from "./OverdueList.module.css";

interface OverdueListProps {
  active: boolean;
}

export function OverdueList({ active }: OverdueListProps) {
  const [loans, setLoans] = useState<OverdueLoan[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    setBusy(true);
    setError(null);
    try {
      const data = await fetchOverdueLoans();
      setLoans(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Request failed");
      setLoans([]);
    } finally {
      setBusy(false);
    }
  }, []);

  useEffect(() => {
    if (active) void load();
  }, [active, load]);

  return (
    <PageShell>
      <Card>
      {error ? <Alert variant="error">{error}</Alert> : null}
      <Button variant="secondary" onClick={() => void load()} disabled={busy}>
        Refresh
      </Button>
      <div className={styles.wrap}>
        {loans === null ? (
          <p className={mutedClassName()}>Loading…</p>
        ) : loans.length === 0 ? (
          <p className={mutedClassName()}>No overdue loans.</p>
        ) : (
          <table className={styles.table}>
            <thead>
              <tr>
                <th scope="col">Patron</th>
                <th scope="col">Book</th>
                <th scope="col">Copy</th>
                <th scope="col">Due</th>
              </tr>
            </thead>
            <tbody>
              {loans.map((loan) => (
                <tr key={`${loan.holding_barcode}-${loan.due_date}`}>
                  <td>
                    <strong>{loan.patron_display_name}</strong>
                  </td>
                  <td>{loan.catalog_title}</td>
                  <td className={styles.meta}>{loan.holding_barcode}</td>
                  <td>{loan.due_date}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
      </Card>
    </PageShell>
  );
}
