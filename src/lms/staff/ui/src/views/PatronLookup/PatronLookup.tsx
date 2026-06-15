import { useState } from "react";

import { fetchOpenLoans } from "@/api/loan";
import {
  fetchPatronByCard,
  fetchPatronByExternalRef,
  searchPatrons,
} from "@/api/reference";
import type { OpenLoan, PatronSummary } from "@/api/types";
import { Alert } from "@/components/Alert/Alert";
import { Button } from "@/components/Button/Button";
import { Card, ListRow, SelectableCard } from "@/components/Card/Card";
import styles from "@/components/Card/Card.module.css";
import {
  FormField,
  FieldRow,
  inputClassName,
  mutedClassName,
} from "@/components/FormField/FormField";
import { PatronSummaryView } from "@/components/PatronSummary/PatronSummary";
import { PageShell } from "@/components/PageShell/PageShell";
import { patronIdentifiers } from "@/lib/format";

export function PatronLookup() {
  const [card, setCard] = useState("");
  const [ref, setRef] = useState("");
  const [name, setName] = useState("");
  const [patron, setPatron] = useState<PatronSummary | null>(null);
  const [loans, setLoans] = useState<OpenLoan[]>([]);
  const [matches, setMatches] = useState<PatronSummary[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [warn, setWarn] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function showDetail(selected: PatronSummary) {
    const openLoans = await fetchOpenLoans(selected.id);
    setPatron(selected);
    setLoans(openLoans);
    setMatches([]);
    setWarn(null);
  }

  async function lookup() {
    const cardValue = card.trim();
    const refValue = ref.trim();
    const nameValue = name.trim();
    if (!cardValue && !refValue && !nameValue) {
      setError("Enter card, admission number, or patron name.");
      return;
    }
    setBusy(true);
    setError(null);
    setWarn(null);
    setPatron(null);
    setMatches([]);
    try {
      if (nameValue && !cardValue && !refValue) {
        const results = await searchPatrons(nameValue);
        if (results.length === 0) {
          setPatron(null);
          setLoans([]);
          return;
        }
        if (results.length === 1) {
          await showDetail(results[0]);
          return;
        }
        setMatches(results);
        setWarn(`${results.length} patrons match — select one below.`);
        return;
      }
      const found =
        cardValue
          ? await fetchPatronByCard(cardValue)
          : refValue
            ? await fetchPatronByExternalRef(refValue)
            : await searchPatrons(nameValue).then((r) => {
                if (r.length !== 1) throw new Error("Patron not found");
                return r[0];
              });
      await showDetail(found);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Request failed");
      setPatron(null);
      setLoans([]);
    } finally {
      setBusy(false);
    }
  }

  return (
    <PageShell>
      <Card>
      {error ? <Alert variant="error">{error}</Alert> : null}
      {warn ? <Alert variant="warn">{warn}</Alert> : null}
      <FieldRow>
        <FormField id="patron-card" label="Card barcode">
          <input
            id="patron-card"
            className={inputClassName()}
            value={card}
            onChange={(e) => setCard(e.target.value)}
          />
        </FormField>
        <FormField id="patron-ref" label="Admission no.">
          <input
            id="patron-ref"
            className={inputClassName()}
            value={ref}
            onChange={(e) => setRef(e.target.value)}
          />
        </FormField>
      </FieldRow>
      <FormField id="patron-name" label="Patron name">
        <input
          id="patron-name"
          className={inputClassName()}
          placeholder="Search by display name"
          value={name}
          onChange={(e) => setName(e.target.value)}
        />
      </FormField>
      <Button onClick={() => void lookup()} disabled={busy}>
        Look up
      </Button>
      <div style={{ marginTop: "1rem" }}>
        {matches.map((p) => (
          <SelectableCard key={p.id} onClick={() => void showDetail(p)}>
            <strong>{p.display_name}</strong>
            <div className={styles.meta}>
              {patronIdentifiers(p) || "No card or admission on file"}
            </div>
            <div className={styles.meta}>
              {p.patron_type_name ?? ""}
              {p.class_section_label ? ` · ${p.class_section_label}` : ""}
            </div>
          </SelectableCard>
        ))}
        {patron ? (
          <ListRow>
            <PatronSummaryView patron={patron} />
            <h3 style={{ margin: "1rem 0 0.25rem", fontSize: "1rem" }}>
              Open loans ({loans.length})
            </h3>
            {loans.length ? (
              <ul className={mutedClassName()}>
                {loans.map((loan) => (
                  <li key={loan.holding_barcode}>
                    <strong>{loan.catalog_title}</strong> · copy {loan.holding_barcode} · due{" "}
                    {loan.due_date}
                  </li>
                ))}
              </ul>
            ) : (
              <p className={mutedClassName()}>No open loans.</p>
            )}
          </ListRow>
        ) : matches.length === 0 && !busy ? (
          !error && !warn ? null : null
        ) : null}
      </div>
      </Card>
    </PageShell>
  );
}
