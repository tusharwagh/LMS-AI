import { api } from "./client";
import type { LlmSpendLogListResponse, LlmSpendSummaryResponse } from "./types";

export interface LlmSpendQueryParams {
  limit?: number;
  offset?: number;
  from_date?: string;
  to_date?: string;
  purpose?: string;
  model?: string;
  session_id?: string;
  operator_id?: string;
}

function buildQuery(params: LlmSpendQueryParams): string {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== "") {
      search.set(key, String(value));
    }
  }
  const qs = search.toString();
  return qs ? `?${qs}` : "";
}

export async function fetchLlmSpendLogs(
  params: LlmSpendQueryParams = {},
): Promise<LlmSpendLogListResponse> {
  return api<LlmSpendLogListResponse>(`/api/v1/llm-spend/logs${buildQuery(params)}`);
}

export async function fetchLlmSpendSummary(
  params: Omit<LlmSpendQueryParams, "limit" | "offset"> = {},
): Promise<LlmSpendSummaryResponse> {
  return api<LlmSpendSummaryResponse>(`/api/v1/llm-spend/summary${buildQuery(params)}`);
}
