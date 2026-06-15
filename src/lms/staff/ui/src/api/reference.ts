import { api } from "./client";
import type { ClassSection, PatronSummary, PatronType } from "./types";

export async function fetchPatron(patronId: string): Promise<PatronSummary> {
  return api<PatronSummary>(`/api/v1/reference/patrons/${patronId}`);
}

export async function searchPatrons(query: string): Promise<PatronSummary[]> {
  return api<PatronSummary[]>(`/api/v1/reference/patrons/search?q=${encodeURIComponent(query)}`);
}

export async function fetchPatronByCard(card: string): Promise<PatronSummary> {
  return api<PatronSummary>(`/api/v1/reference/patrons/by-card/${encodeURIComponent(card)}`);
}

export async function fetchPatronByExternalRef(ref: string): Promise<PatronSummary> {
  return api<PatronSummary>(
    `/api/v1/reference/patrons/by-external-ref/${encodeURIComponent(ref)}`,
  );
}

export async function fetchPatronTypes(): Promise<PatronType[]> {
  return api<PatronType[]>("/api/v1/reference/patron-types");
}

export async function createPatronType(body: { code: string; name: string }): Promise<void> {
  await api("/api/v1/reference/patron-types", { method: "POST", body });
}

export async function fetchClassSections(): Promise<ClassSection[]> {
  return api<ClassSection[]>("/api/v1/reference/class-sections");
}

export async function createClassSection(body: {
  grade: string;
  section: string;
  academic_year: string;
}): Promise<void> {
  await api("/api/v1/reference/class-sections", { method: "POST", body });
}
