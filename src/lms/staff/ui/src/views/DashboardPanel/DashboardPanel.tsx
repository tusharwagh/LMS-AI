import { useCallback, useEffect, useState } from "react";

import {
  fetchDashboard,
  fetchReportPresets,
  generateReportCsv,
  generateReportJson,
} from "@/api/reporting";
import type {
  DashboardResponse,
  ReportMetric,
  ReportPreset,
} from "@/api/types";
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
import styles from "./DashboardPanel.module.css";

const ALL_METRICS: { value: ReportMetric; label: string }[] = [
  { value: "daily_issues", label: "Daily issues" },
  { value: "daily_returns", label: "Daily returns" },
  { value: "holdings_by_status", label: "Holdings by status" },
  { value: "total_active_loans", label: "Active loans" },
  { value: "overdue_loans", label: "Overdue loans" },
];

interface DashboardPanelProps {
  active: boolean;
}

export function DashboardPanel({ active }: DashboardPanelProps) {
  const [days, setDays] = useState(30);
  const [dashboard, setDashboard] = useState<DashboardResponse | null>(null);
  const [presets, setPresets] = useState<ReportPreset[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const [reportFrom, setReportFrom] = useState("");
  const [reportTo, setReportTo] = useState("");
  const [selectedMetrics, setSelectedMetrics] = useState<ReportMetric[]>([
    "daily_issues",
    "daily_returns",
  ]);
  const [reportFormat, setReportFormat] = useState<"json" | "csv">("json");
  const [reportOutput, setReportOutput] = useState<string | null>(null);

  const loadDashboard = useCallback(async () => {
    setBusy(true);
    setError(null);
    try {
      const data = await fetchDashboard({ days });
      setDashboard(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Request failed");
      setDashboard(null);
    } finally {
      setBusy(false);
    }
  }, [days]);

  useEffect(() => {
    if (!active) return;
    void loadDashboard();
    void fetchReportPresets()
      .then((res) => setPresets(res.presets))
      .catch(() => setPresets([]));
  }, [active, loadDashboard]);

  function toggleMetric(metric: ReportMetric) {
    setSelectedMetrics((prev) =>
      prev.includes(metric) ? prev.filter((m) => m !== metric) : [...prev, metric],
    );
  }

  function applyPreset(preset: ReportPreset) {
    setSelectedMetrics(preset.metrics);
    if (dashboard) {
      setReportFrom(dashboard.from_date);
      setReportTo(dashboard.to_date);
    }
  }

  async function handleGenerateReport() {
    if (!reportFrom || !reportTo || selectedMetrics.length === 0) {
      setError("Select a date range and at least one metric.");
      return;
    }
    setBusy(true);
    setError(null);
    setReportOutput(null);
    try {
      const body = {
        metrics: selectedMetrics,
        from_date: reportFrom,
        to_date: reportTo,
        group_by: "day" as const,
        format: reportFormat,
      };
      if (reportFormat === "csv") {
        const blob = await generateReportCsv(body);
        const url = URL.createObjectURL(blob);
        const anchor = document.createElement("a");
        anchor.href = url;
        anchor.download = `report-${reportFrom}-${reportTo}.csv`;
        anchor.click();
        URL.revokeObjectURL(url);
        setReportOutput("CSV downloaded.");
      } else {
        const result = await generateReportJson(body);
        setReportOutput(JSON.stringify(result, null, 2));
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Report generation failed");
    } finally {
      setBusy(false);
    }
  }

  const holdings = dashboard?.holdings_by_status ?? {};

  return (
    <PageShell>
      <Card>
        {error ? <Alert variant="error">{error}</Alert> : null}

        <div className={styles.toolbar}>
          <FormField id="dash-days" label="Series days">
            <input
              id="dash-days"
              type="number"
              min={7}
              max={90}
              className={inputClassName()}
              value={days}
              onChange={(e) => setDays(Number(e.target.value))}
            />
          </FormField>
          <Button variant="secondary" onClick={() => void loadDashboard()} disabled={busy}>
            Refresh
          </Button>
        </div>

        {dashboard === null ? (
          <p className={mutedClassName()}>Loading…</p>
        ) : (
          <>
            <div className={styles.summaryGrid}>
              <div className={styles.summaryCard}>
                <div className={styles.summaryLabel}>Issues today</div>
                <div className={styles.summaryValue}>{dashboard.today.issues_today}</div>
              </div>
              <div className={styles.summaryCard}>
                <div className={styles.summaryLabel}>Returns today</div>
                <div className={styles.summaryValue}>{dashboard.today.returns_today}</div>
              </div>
              <div className={styles.summaryCard}>
                <div className={styles.summaryLabel}>Active loans</div>
                <div className={styles.summaryValue}>
                  {dashboard.circulation.total_active_loans}
                </div>
              </div>
              <div className={styles.summaryCard}>
                <div className={styles.summaryLabel}>Overdue</div>
                <div className={styles.summaryValue}>
                  {dashboard.circulation.overdue_loans}
                </div>
              </div>
              <div className={styles.summaryCard}>
                <div className={styles.summaryLabel}>On loan (holdings)</div>
                <div className={styles.summaryValue}>{holdings.ON_LOAN ?? 0}</div>
              </div>
              <div className={styles.summaryCard}>
                <div className={styles.summaryLabel}>Available</div>
                <div className={styles.summaryValue}>{holdings.AVAILABLE ?? 0}</div>
              </div>
              <div className={styles.summaryCard}>
                <div className={styles.summaryLabel}>Damaged</div>
                <div className={styles.summaryValue}>{holdings.DAMAGED ?? 0}</div>
              </div>
              <div className={styles.summaryCard}>
                <div className={styles.summaryLabel}>Lost</div>
                <div className={styles.summaryValue}>{holdings.LOST ?? 0}</div>
              </div>
            </div>

            <h3 className={styles.sectionTitle}>
              Daily circulation ({dashboard.from_date} – {dashboard.to_date})
            </h3>
            <div className={styles.wrap}>
              <table className={styles.table}>
                <thead>
                  <tr>
                    <th scope="col">Date</th>
                    <th scope="col" className={styles.num}>
                      Issues
                    </th>
                    <th scope="col" className={styles.num}>
                      Returns
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {dashboard.daily_series.map((row) => (
                    <tr key={row.date}>
                      <td>{row.date}</td>
                      <td className={styles.num}>{row.issues}</td>
                      <td className={styles.num}>{row.returns}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </>
        )}
      </Card>

      <Card>
        <h3 className={styles.sectionTitle}>Report builder</h3>
        {presets.length > 0 ? (
          <FieldRow>
            {presets.map((preset) => (
              <Button
                key={preset.id}
                variant="secondary"
                onClick={() => applyPreset(preset)}
                disabled={busy}
              >
                {preset.name}
              </Button>
            ))}
          </FieldRow>
        ) : null}

        <FieldRow>
          <FormField id="report-from" label="From">
            <input
              id="report-from"
              type="date"
              className={inputClassName()}
              value={reportFrom}
              onChange={(e) => setReportFrom(e.target.value)}
            />
          </FormField>
          <FormField id="report-to" label="To">
            <input
              id="report-to"
              type="date"
              className={inputClassName()}
              value={reportTo}
              onChange={(e) => setReportTo(e.target.value)}
            />
          </FormField>
          <FormField id="report-format" label="Format">
            <select
              id="report-format"
              className={inputClassName()}
              value={reportFormat}
              onChange={(e) => setReportFormat(e.target.value as "json" | "csv")}
            >
              <option value="json">JSON</option>
              <option value="csv">CSV</option>
            </select>
          </FormField>
        </FieldRow>

        <div className={styles.metricList}>
          {ALL_METRICS.map((metric) => (
            <label key={metric.value} className={styles.checkboxRow}>
              <input
                type="checkbox"
                checked={selectedMetrics.includes(metric.value)}
                onChange={() => toggleMetric(metric.value)}
              />
              {metric.label}
            </label>
          ))}
        </div>

        <Button variant="secondary" onClick={() => void handleGenerateReport()} disabled={busy}>
          Generate report
        </Button>

        {reportOutput ? <pre className={styles.reportOutput}>{reportOutput}</pre> : null}
      </Card>
    </PageShell>
  );
}
