import { useCallback, useEffect, useState } from "react";

import { fetchLlmSpendLogs, fetchLlmSpendSummary } from "@/api/llmSpend";
import type { LlmSpendLogListResponse, LlmSpendSummaryResponse } from "@/api/types";
import { Alert } from "@/components/Alert/Alert";
import { Button } from "@/components/Button/Button";
import { Card } from "@/components/Card/Card";
import {
  FieldRow,
  FormField,
  inputClassName,
  mutedClassName,
} from "@/components/FormField/FormField";
import { PageShell } from "@/components/PageShell/PageShell";
import styles from "./LlmSpendPanel.module.css";

const PAGE_SIZE = 20;

interface LlmSpendPanelProps {
  active: boolean;
}

function formatCost(value: number | null | undefined): string {
  if (value == null) return "—";
  return `$${value.toFixed(4)}`;
}

function formatDateTime(iso: string): string {
  return new Date(iso).toLocaleString();
}

function toStartOfDayUtc(date: string): string {
  return new Date(`${date}T00:00:00`).toISOString();
}

function toEndOfDayUtc(date: string): string {
  return new Date(`${date}T23:59:59.999`).toISOString();
}

export function LlmSpendPanel({ active }: LlmSpendPanelProps) {
  const [fromDate, setFromDate] = useState("");
  const [toDate, setToDate] = useState("");
  const [purpose, setPurpose] = useState("");
  const [offset, setOffset] = useState(0);
  const [summary, setSummary] = useState<LlmSpendSummaryResponse | null>(null);
  const [logs, setLogs] = useState<LlmSpendLogListResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const queryParams = useCallback(() => {
    const params: Record<string, string> = {};
    if (fromDate) params.from_date = toStartOfDayUtc(fromDate);
    if (toDate) params.to_date = toEndOfDayUtc(toDate);
    if (purpose.trim()) params.purpose = purpose.trim();
    return params;
  }, [fromDate, purpose, toDate]);

  const load = useCallback(
    async (pageOffset = offset) => {
      setBusy(true);
      setError(null);
      try {
        const filters = queryParams();
        const [summaryData, logsData] = await Promise.all([
          fetchLlmSpendSummary(filters),
          fetchLlmSpendLogs({ ...filters, limit: PAGE_SIZE, offset: pageOffset }),
        ]);
        setSummary(summaryData);
        setLogs(logsData);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Request failed");
        setSummary(null);
        setLogs(null);
      } finally {
        setBusy(false);
      }
    },
    [offset, queryParams],
  );

  useEffect(() => {
    if (active) void load();
  }, [active, load]);

  function applyFilters() {
    setOffset(0);
    void load(0);
  }

  const canPrev = offset > 0;
  const canNext = logs != null && offset + PAGE_SIZE < logs.total;

  return (
    <PageShell>
      <Card>
        {error ? <Alert variant="error">{error}</Alert> : null}

        <div className={styles.toolbar}>
          <FieldRow>
            <FormField id="spend-from" label="From">
              <input
                id="spend-from"
                type="date"
                className={inputClassName()}
                value={fromDate}
                onChange={(e) => setFromDate(e.target.value)}
              />
            </FormField>
            <FormField id="spend-to" label="To">
              <input
                id="spend-to"
                type="date"
                className={inputClassName()}
                value={toDate}
                onChange={(e) => setToDate(e.target.value)}
              />
            </FormField>
            <FormField id="spend-purpose" label="Purpose">
              <input
                id="spend-purpose"
                type="text"
                className={inputClassName()}
                placeholder="e.g. intent_parse"
                value={purpose}
                onChange={(e) => setPurpose(e.target.value)}
              />
            </FormField>
          </FieldRow>
          <Button variant="secondary" onClick={() => applyFilters()} disabled={busy}>
            Apply
          </Button>
          <Button variant="secondary" onClick={() => void load()} disabled={busy}>
            Refresh
          </Button>
        </div>

        {summary === null ? (
          <p className={mutedClassName()}>Loading…</p>
        ) : (
          <>
            <div className={styles.summaryGrid}>
              <div className={styles.summaryCard}>
                <div className={styles.summaryLabel}>Total cost</div>
                <div className={styles.summaryValue}>
                  {formatCost(summary.total_cost_usd)}
                </div>
              </div>
              <div className={styles.summaryCard}>
                <div className={styles.summaryLabel}>Requests</div>
                <div className={styles.summaryValue}>{summary.total_requests}</div>
              </div>
              <div className={styles.summaryCard}>
                <div className={styles.summaryLabel}>Tokens</div>
                <div className={styles.summaryValue}>
                  {summary.total_tokens.toLocaleString()}
                </div>
              </div>
            </div>

            <h3 className={styles.sectionTitle}>By purpose / model</h3>
            {summary.groups.length === 0 ? (
              <p className={mutedClassName()}>No spend in this period.</p>
            ) : (
              <div className={styles.wrap}>
                <table className={styles.table}>
                  <thead>
                    <tr>
                      <th scope="col">Purpose</th>
                      <th scope="col">Model</th>
                      <th scope="col">Provider</th>
                      <th scope="col" className={styles.num}>
                        Requests
                      </th>
                      <th scope="col" className={styles.num}>
                        Tokens
                      </th>
                      <th scope="col" className={styles.num}>
                        Cost
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    {summary.groups.map((group) => (
                      <tr key={`${group.purpose}-${group.model}-${group.provider}`}>
                        <td>{group.purpose}</td>
                        <td className={styles.meta}>{group.model}</td>
                        <td>{group.provider}</td>
                        <td className={styles.num}>{group.request_count}</td>
                        <td className={styles.num}>
                          {group.total_tokens.toLocaleString()}
                        </td>
                        <td className={styles.num}>{formatCost(group.cost_usd)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}

            <h3 className={styles.sectionTitle}>Recent requests</h3>
            {logs === null ? (
              <p className={mutedClassName()}>Loading logs…</p>
            ) : logs.items.length === 0 ? (
              <p className={mutedClassName()}>No log entries match the filters.</p>
            ) : (
              <>
                <div className={styles.wrap}>
                  <table className={styles.table}>
                    <thead>
                      <tr>
                        <th scope="col">Time</th>
                        <th scope="col">Purpose</th>
                        <th scope="col">Model</th>
                        <th scope="col" className={styles.num}>
                          Tokens
                        </th>
                        <th scope="col" className={styles.num}>
                          Cost
                        </th>
                        <th scope="col">Session</th>
                        <th scope="col">Operator</th>
                      </tr>
                    </thead>
                    <tbody>
                      {logs.items.map((row) => (
                        <tr key={row.id}>
                          <td className={styles.meta}>{formatDateTime(row.created_at)}</td>
                          <td>
                            {row.purpose}
                            {row.cached ? (
                              <span className={`${styles.badge} ${styles.badgeCached}`}>
                                cached
                              </span>
                            ) : null}
                          </td>
                          <td className={styles.meta}>{row.model}</td>
                          <td className={styles.num}>{row.total_tokens}</td>
                          <td className={styles.num}>{formatCost(row.cost_usd)}</td>
                          <td className={styles.meta}>{row.session_id ?? "—"}</td>
                          <td className={styles.meta}>{row.operator_id ?? "—"}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                <div className={styles.pagination}>
                  <Button
                    variant="secondary"
                    disabled={!canPrev || busy}
                    onClick={() => {
                      const next = Math.max(0, offset - PAGE_SIZE);
                      setOffset(next);
                      void load(next);
                    }}
                  >
                    Previous
                  </Button>
                  <span className={mutedClassName()}>
                    {offset + 1}–{Math.min(offset + PAGE_SIZE, logs.total)} of {logs.total}
                  </span>
                  <Button
                    variant="secondary"
                    disabled={!canNext || busy}
                    onClick={() => {
                      const next = offset + PAGE_SIZE;
                      setOffset(next);
                      void load(next);
                    }}
                  >
                    Next
                  </Button>
                </div>
              </>
            )}
          </>
        )}
      </Card>
    </PageShell>
  );
}
