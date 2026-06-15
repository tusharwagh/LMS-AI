import { useCallback, useEffect, useState } from "react";

import {
  createLoanRuleSet,
  fetchLoanRuleSets,
} from "@/api/loan";
import {
  createClassSection,
  createPatronType,
  fetchClassSections,
  fetchPatronTypes,
} from "@/api/reference";
import type { ClassSection, LoanRuleSet, PatronType } from "@/api/types";
import { Alert } from "@/components/Alert/Alert";
import { Button } from "@/components/Button/Button";
import { Card, ListRow } from "@/components/Card/Card";
import { PageShell } from "@/components/PageShell/PageShell";
import {
  FormField,
  FieldRow,
  inputClassName,
  mutedClassName,
} from "@/components/FormField/FormField";

interface AdminPanelProps {
  active: boolean;
}

export function AdminPanel({ active }: AdminPanelProps) {
  const [rules, setRules] = useState<LoanRuleSet[]>([]);
  const [types, setTypes] = useState<PatronType[]>([]);
  const [sections, setSections] = useState<ClassSection[]>([]);
  const [ruleName, setRuleName] = useState("");
  const [ruleMax, setRuleMax] = useState("3");
  const [ruleDays, setRuleDays] = useState("14");
  const [typeCode, setTypeCode] = useState("");
  const [typeName, setTypeName] = useState("");
  const [grade, setGrade] = useState("");
  const [section, setSection] = useState("");
  const [year, setYear] = useState("2025-26");
  const [message, setMessage] = useState<{ variant: "success" | "error"; text: string } | null>(
    null,
  );

  const load = useCallback(async () => {
    const [ruleData, typeData, sectionData] = await Promise.all([
      fetchLoanRuleSets(),
      fetchPatronTypes(),
      fetchClassSections(),
    ]);
    setRules(ruleData);
    setTypes(typeData);
    setSections(sectionData);
  }, []);

  useEffect(() => {
    if (active) {
      void load().catch((err) => {
        setMessage({
          variant: "error",
          text: err instanceof Error ? err.message : "Request failed",
        });
      });
    }
  }, [active, load]);

  async function addRule() {
    try {
      await createLoanRuleSet({
        name: ruleName.trim(),
        max_active_loans: Number(ruleMax),
        loan_period_days: Number(ruleDays),
      });
      setMessage({ variant: "success", text: "Rule set created." });
      await load();
    } catch (err) {
      setMessage({
        variant: "error",
        text: err instanceof Error ? err.message : "Request failed",
      });
    }
  }

  async function addType() {
    try {
      await createPatronType({ code: typeCode.trim(), name: typeName.trim() });
      setMessage({ variant: "success", text: "Patron type created." });
      await load();
    } catch (err) {
      setMessage({
        variant: "error",
        text: err instanceof Error ? err.message : "Request failed",
      });
    }
  }

  async function addSection() {
    try {
      await createClassSection({
        grade: grade.trim(),
        section: section.trim(),
        academic_year: year.trim(),
      });
      setMessage({ variant: "success", text: "Class section created." });
      await load();
    } catch (err) {
      setMessage({
        variant: "error",
        text: err instanceof Error ? err.message : "Request failed",
      });
    }
  }

  return (
    <PageShell>
      <Card>
      {message ? <Alert variant={message.variant}>{message.text}</Alert> : null}

      <h3>Loan rule sets</h3>
      <FieldRow>
        <FormField id="admin-rule-name" label="Name">
          <input
            id="admin-rule-name"
            className={inputClassName()}
            placeholder="Name"
            value={ruleName}
            onChange={(e) => setRuleName(e.target.value)}
          />
        </FormField>
        <FormField id="admin-rule-max" label="Max loans">
          <input
            id="admin-rule-max"
            type="number"
            min={0}
            className={inputClassName()}
            value={ruleMax}
            onChange={(e) => setRuleMax(e.target.value)}
          />
        </FormField>
        <FormField id="admin-rule-days" label="Loan days">
          <input
            id="admin-rule-days"
            type="number"
            min={1}
            className={inputClassName()}
            value={ruleDays}
            onChange={(e) => setRuleDays(e.target.value)}
          />
        </FormField>
      </FieldRow>
      <Button onClick={() => void addRule()}>Add rule set</Button>
      <div style={{ margin: "1rem 0" }}>
        {rules.length ? (
          rules.map((r) => (
            <ListRow key={r.name}>
              <span className={mutedClassName()}>
                {r.name} — max {r.max_active_loans}, {r.loan_period_days} days
              </span>
            </ListRow>
          ))
        ) : (
          <p className={mutedClassName()}>None yet.</p>
        )}
      </div>

      <h3>Patron types</h3>
      <FieldRow>
        <FormField id="admin-type-code" label="Code">
          <input
            id="admin-type-code"
            className={inputClassName()}
            placeholder="Code e.g. STUDENT"
            value={typeCode}
            onChange={(e) => setTypeCode(e.target.value)}
          />
        </FormField>
        <FormField id="admin-type-name" label="Display name">
          <input
            id="admin-type-name"
            className={inputClassName()}
            placeholder="Display name"
            value={typeName}
            onChange={(e) => setTypeName(e.target.value)}
          />
        </FormField>
      </FieldRow>
      <Button onClick={() => void addType()}>Add patron type</Button>
      <div style={{ margin: "1rem 0" }}>
        {types.length ? (
          types.map((t) => (
            <ListRow key={t.code}>
              <span className={mutedClassName()}>
                {t.code} — {t.name}
              </span>
            </ListRow>
          ))
        ) : (
          <p className={mutedClassName()}>None yet.</p>
        )}
      </div>

      <h3>Class sections</h3>
      <FieldRow>
        <FormField id="admin-grade" label="Grade">
          <input
            id="admin-grade"
            className={inputClassName()}
            placeholder="Grade"
            value={grade}
            onChange={(e) => setGrade(e.target.value)}
          />
        </FormField>
        <FormField id="admin-section" label="Section">
          <input
            id="admin-section"
            className={inputClassName()}
            placeholder="Section"
            value={section}
            onChange={(e) => setSection(e.target.value)}
          />
        </FormField>
        <FormField id="admin-year" label="Academic year">
          <input
            id="admin-year"
            className={inputClassName()}
            value={year}
            onChange={(e) => setYear(e.target.value)}
          />
        </FormField>
      </FieldRow>
      <Button onClick={() => void addSection()}>Add class section</Button>
      <div style={{ marginTop: "1rem" }}>
        {sections.length ? (
          sections.map((s) => (
            <ListRow key={`${s.grade}-${s.section}-${s.academic_year}`}>
              <span className={mutedClassName()}>
                Grade {s.grade} {s.section} ({s.academic_year})
              </span>
            </ListRow>
          ))
        ) : (
          <p className={mutedClassName()}>None yet.</p>
        )}
      </div>
      </Card>
    </PageShell>
  );
}
