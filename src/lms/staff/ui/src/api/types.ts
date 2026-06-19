export type Role = "ADMIN" | "LIBRARIAN";

export interface User {
  id: string;
  username: string;
  role: Role;
  display_name?: string | null;
  tenant_id?: string | null;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
  expires_in: number;
}

export interface RuleViolation {
  rule_id: string;
  message: string;
}

export interface ValidationReport {
  is_valid: boolean;
  violations: RuleViolation[];
}

export interface PatronSummary {
  id: string;
  display_name: string;
  external_ref?: string | null;
  card_barcode?: string | null;
  status: string;
  patron_type_name?: string | null;
  class_section_label?: string | null;
  blocked?: boolean;
}

export interface LendableCopy {
  holding_id: string;
  barcode: string;
  accession_number: string;
  shelf_location?: string | null;
}

export interface IssueSearchHit {
  catalog_id: string;
  title: string;
  lendable_copies: LendableCopy[];
}

export interface IssueSearchPatronsResponse {
  patrons: PatronSummary[];
}

export interface IssueStartResponse {
  patron_id: string;
  patron_display_name: string;
  patron_validation: ValidationReport;
  search_results: IssueSearchHit[];
}

export interface IssueCommitResponse {
  loan_id: string;
  holding_id: string;
  due_date: string;
  fulfillment?: {
    mode: string;
    status: string;
  } | null;
}

export interface ReturnContext {
  loan_id: string;
  catalog_title: string;
  holding_barcode: string;
  patron_display_name: string;
  due_date: string;
  is_overdue: boolean;
  open_loans_for_patron: number;
}

export interface OverdueLoan {
  patron_display_name: string;
  catalog_title: string;
  holding_barcode: string;
  due_date: string;
}

export interface OpenLoan {
  catalog_title: string;
  holding_barcode: string;
  due_date: string;
}

export interface CatalogSearchHit {
  catalog: { title: string };
  lendable_holdings: Array<{
    barcode: string;
    shelf_location?: string | null;
  }>;
}

export interface LoanRuleSet {
  name: string;
  max_active_loans: number;
  loan_period_days: number;
}

export interface PatronType {
  code: string;
  name: string;
}

export interface ClassSection {
  grade: string;
  section: string;
  academic_year: string;
}

export interface PendingApproval {
  kind: string;
  summary: string;
  details: Record<string, unknown>;
}

export interface AgentMessageResponse {
  session_id: string;
  assistant_message: string;
  pending_approval?: PendingApproval | null;
  session_summary: Record<string, unknown>;
  agent_disclosure: string;
}

export interface AgentSessionResponse {
  session_id: string;
  operator_id: string;
  session_summary: Record<string, unknown>;
}

export interface ApiErrorBody {
  message?: string;
  code?: string;
  detail?: string | { message?: string; details?: { violations?: RuleViolation[] } };
  details?: { violations?: RuleViolation[] };
}

export type StaffView =
  | "issue"
  | "agent"
  | "return"
  | "search"
  | "overdue"
  | "patron"
  | "admin"
  | "spend";

export interface LlmSpendLog {
  id: string;
  purpose: string;
  model: string;
  provider: string;
  prompt_tokens: number;
  completion_tokens: number;
  total_tokens: number;
  cost_usd: number | null;
  cached: boolean;
  session_id: string | null;
  operator_id: string | null;
  created_at: string;
}

export interface LlmSpendLogListResponse {
  items: LlmSpendLog[];
  total: number;
  limit: number;
  offset: number;
}

export interface LlmSpendSummaryGroup {
  purpose: string;
  model: string;
  provider: string;
  request_count: number;
  prompt_tokens: number;
  completion_tokens: number;
  total_tokens: number;
  cost_usd: number;
}

export interface LlmSpendSummaryResponse {
  groups: LlmSpendSummaryGroup[];
  total_cost_usd: number;
  total_requests: number;
  total_tokens: number;
}
