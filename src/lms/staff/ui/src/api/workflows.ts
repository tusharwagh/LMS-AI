import { api, apiWithIdempotency } from "./client";
import type {
  IssueCommitResponse,
  IssueSearchHit,
  IssueSearchPatronsResponse,
  IssueStartResponse,
  ReturnContext,
  ValidationReport,
} from "./types";

export async function issueStart(body: Record<string, unknown>): Promise<IssueStartResponse> {
  return api<IssueStartResponse>("/api/v1/workflows/issue/start", { method: "POST", body });
}

export async function issueSearchPatrons(displayName: string): Promise<IssueSearchPatronsResponse> {
  return api<IssueSearchPatronsResponse>("/api/v1/workflows/issue/search-patrons", {
    method: "POST",
    body: { display_name: displayName },
  });
}

export async function issueBack(targetStep: number): Promise<void> {
  await api("/api/v1/workflows/issue/back", {
    method: "POST",
    body: { target_step: targetStep },
  });
}

export async function issueValidate(
  patronId: string,
  holdingId: string,
): Promise<ValidationReport> {
  return api<ValidationReport>("/api/v1/workflows/issue/validate", {
    method: "POST",
    body: { patron_id: patronId, holding_id: holdingId },
  });
}

export async function issueCommit(
  body: Record<string, unknown>,
  idempotencyKey: string,
): Promise<IssueCommitResponse> {
  return apiWithIdempotency<IssueCommitResponse>(
    "/api/v1/workflows/issue/commit",
    body,
    idempotencyKey,
  );
}

export async function issueCancel(loanId: string, idempotencyKey: string): Promise<void> {
  await apiWithIdempotency(
    "/api/v1/workflows/issue/cancel",
    { loan_id: loanId },
    idempotencyKey,
  );
}

export async function returnStart(barcode: string): Promise<ReturnContext> {
  return api<ReturnContext>("/api/v1/workflows/return/start", {
    method: "POST",
    body: { barcode },
  });
}

export async function returnCommit(barcode: string, idempotencyKey: string): Promise<void> {
  await apiWithIdempotency(
    "/api/v1/workflows/return/commit",
    { barcode },
    idempotencyKey,
  );
}

export async function returnPickupInitiate(
  loanId: string,
  notes: string | null,
  idempotencyKey: string,
): Promise<void> {
  await apiWithIdempotency(
    "/api/v1/workflows/return/pickup/initiate",
    { loan_id: loanId, destination: { notes } },
    idempotencyKey,
  );
}

export type { IssueSearchHit };
