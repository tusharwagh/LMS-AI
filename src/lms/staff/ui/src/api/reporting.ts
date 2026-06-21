import { api } from "./client";
import type {
  DashboardResponse,
  ReportGenerateRequest,
  ReportGenerateResponse,
  ReportPresetsResponse,
} from "./types";

export interface DashboardQueryParams {
  days?: number;
  from_date?: string;
  to_date?: string;
}

function buildQuery(params: Record<string, string | number | undefined>): string {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== "") {
      search.set(key, String(value));
    }
  }
  const qs = search.toString();
  return qs ? `?${qs}` : "";
}

export async function fetchDashboard(
  params: DashboardQueryParams = {},
): Promise<DashboardResponse> {
  return api<DashboardResponse>(
    `/api/v1/reporting/dashboard${buildQuery(params as Record<string, string | number | undefined>)}`,
  );
}

export async function fetchReportPresets(): Promise<ReportPresetsResponse> {
  return api<ReportPresetsResponse>("/api/v1/reporting/reports/presets");
}

export async function generateReportJson(
  body: ReportGenerateRequest,
): Promise<ReportGenerateResponse> {
  return api<ReportGenerateResponse>("/api/v1/reporting/reports/generate", {
    method: "POST",
    body: { ...body, format: "json" },
  });
}

export async function generateReportCsv(body: ReportGenerateRequest): Promise<Blob> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
  };
  const token = sessionStorage.getItem("lms_staff_token");
  if (token) headers.Authorization = `Bearer ${token}`;

  const res = await fetch("/api/v1/reporting/reports/generate", {
    method: "POST",
    headers,
    body: JSON.stringify({ ...body, format: "csv" }),
  });

  if (!res.ok) {
    const text = await res.text();
    throw new Error(text || "Report generation failed");
  }

  return res.blob();
}
