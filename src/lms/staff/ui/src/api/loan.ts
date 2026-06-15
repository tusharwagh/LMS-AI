import { api } from "./client";
import type { LoanRuleSet, OpenLoan, OverdueLoan } from "./types";

export async function fetchOverdueLoans(): Promise<OverdueLoan[]> {
  return api<OverdueLoan[]>("/api/v1/loan/loans/overdue");
}

export async function fetchOpenLoans(patronId: string): Promise<OpenLoan[]> {
  return api<OpenLoan[]>(`/api/v1/loan/loans/open?patron_id=${patronId}`);
}

export async function fetchLoanRuleSets(): Promise<LoanRuleSet[]> {
  return api<LoanRuleSet[]>("/api/v1/loan/loan-rule-sets");
}

export async function createLoanRuleSet(body: {
  name: string;
  max_active_loans: number;
  loan_period_days: number;
}): Promise<void> {
  await api("/api/v1/loan/loan-rule-sets", { method: "POST", body });
}
