import { useCallback, useState } from "react";

import { fetchPatron } from "@/models";
import type {
  IssueCommitResponse,
  IssueSearchHit,
  LendableCopy,
  PatronSummary,
  ValidationReport,
} from "@/models";
import {
  issueBack,
  issueCancel,
  issueCommit,
  issueSearchPatrons,
  issueStart,
  issueValidate,
} from "@/models";
import { newIdempotencyKey } from "@/lib/uuid";

export interface IssueWizardState {
  step: number;
  patronId: string | null;
  patronName: string;
  patronMeta: PatronSummary | null;
  searchResults: IssueSearchHit[];
  selectedHit: IssueSearchHit | null;
  selectedCopy: LendableCopy | null;
  loanId: string | null;
  validation: ValidationReport | null;
  canCommit: boolean;
  doneKind: "issued" | "cancelled" | null;
  commitResult: IssueCommitResponse | null;
  cancelHidden: boolean;
  alert: { variant: "error" | "warn"; message: string } | null;
  busy: boolean;
}

const initialState = (): IssueWizardState => ({
  step: 1,
  patronId: null,
  patronName: "",
  patronMeta: null,
  searchResults: [],
  selectedHit: null,
  selectedCopy: null,
  loanId: null,
  validation: null,
  canCommit: false,
  doneKind: null,
  commitResult: null,
  cancelHidden: false,
  alert: null,
  busy: false,
});

export function useIssueWizardController() {
  const [state, setState] = useState<IssueWizardState>(initialState);
  const [card, setCard] = useState("");
  const [admission, setAdmission] = useState("");
  const [name, setName] = useState("");
  const [searchQuery, setSearchQuery] = useState("");
  const [mode, setMode] = useState("DESK");
  const [destNotes, setDestNotes] = useState("");
  const [destContact, setDestContact] = useState("");
  const [candidates, setCandidates] = useState<PatronSummary[]>([]);

  const reset = useCallback(() => {
    setState(initialState());
    setCard("");
    setAdmission("");
    setName("");
    setSearchQuery("");
    setMode("DESK");
    setDestNotes("");
    setDestContact("");
    setCandidates([]);
  }, []);

  const buildStartBody = useCallback(
    (extra: Record<string, unknown> = {}) => {
      const body: Record<string, unknown> = { ...extra };
      if (state.patronId) body.patron_id = state.patronId;
      else if (card.trim()) body.card_barcode = card.trim();
      else if (admission.trim()) body.external_ref = admission.trim();
      else if (name.trim()) body.display_name = name.trim();
      return body;
    },
    [state.patronId, card, admission, name],
  );

  const startWithPatron = useCallback(
    async (body: Record<string, unknown>, patronMeta?: PatronSummary | null) => {
      setState((s) => ({ ...s, busy: true, alert: null }));
      try {
        const res = await issueStart(body);
        let meta = patronMeta;
        if (!meta) {
          try {
            meta = await fetchPatron(res.patron_id);
          } catch {
            meta = {
              id: res.patron_id,
              display_name: res.patron_display_name,
              external_ref: admission.trim() || null,
              card_barcode: card.trim() || null,
              status: "ACTIVE",
              blocked: false,
            };
          }
        }
        setCandidates([]);
        setState((s) => ({
          ...s,
          busy: false,
          step: 2,
          patronId: res.patron_id,
          patronName: res.patron_display_name,
          patronMeta: meta ?? null,
          searchResults: res.search_results,
          validation: res.patron_validation,
          alert: res.patron_validation.is_valid
            ? null
            : {
                variant: "warn",
                message: "Patron cannot borrow until validation issues are resolved.",
              },
        }));
      } catch (err) {
        setState((s) => ({
          ...s,
          busy: false,
          alert: { variant: "error", message: err instanceof Error ? err.message : "Request failed" },
        }));
      }
    },
    [admission, card],
  );

  const findPatron = useCallback(async () => {
    const body = buildStartBody({
      search_query: searchQuery.trim() || undefined,
    });
    if (!body.patron_id && !body.card_barcode && !body.external_ref && !body.display_name) {
      setState((s) => ({
        ...s,
        alert: { variant: "error", message: "Enter card, admission number, or patron name." },
      }));
      return;
    }
    await startWithPatron(body);
  }, [buildStartBody, searchQuery, startWithPatron]);

  const searchPatronsByName = useCallback(async () => {
    const trimmed = name.trim();
    if (!trimmed) {
      setState((s) => ({
        ...s,
        alert: { variant: "error", message: "Enter a patron name." },
      }));
      return;
    }
    setState((s) => ({ ...s, busy: true, alert: null }));
    try {
      const res = await issueSearchPatrons(trimmed);
      setCandidates(res.patrons);
      setState((s) => ({ ...s, busy: false }));
    } catch (err) {
      setState((s) => ({
        ...s,
        busy: false,
        alert: { variant: "error", message: err instanceof Error ? err.message : "Request failed" },
      }));
    }
  }, [name]);

  const pickCandidate = useCallback(
    async (patron: PatronSummary) => {
      setCard(patron.card_barcode ?? "");
      setAdmission(patron.external_ref ?? "");
      await startWithPatron(
        {
          patron_id: patron.id,
          search_query: searchQuery.trim() || undefined,
        },
        {
          ...patron,
          blocked: patron.blocked ?? false,
        },
      );
    },
    [searchQuery, startWithPatron],
  );

  const searchCatalog = useCallback(async () => {
    if (!state.patronId) return;
    const q = searchQuery.trim();
    if (!q) {
      setState((s) => ({
        ...s,
        alert: { variant: "error", message: "Enter a search term." },
      }));
      return;
    }
    setState((s) => ({ ...s, busy: true, alert: null }));
    try {
      const res = await issueStart({
        patron_id: state.patronId,
        search_query: q,
      });
      setState((s) => ({
        ...s,
        busy: false,
        searchResults: res.search_results,
      }));
    } catch (err) {
      setState((s) => ({
        ...s,
        busy: false,
        alert: { variant: "error", message: err instanceof Error ? err.message : "Request failed" },
      }));
    }
  }, [state.patronId, searchQuery]);

  const selectHit = useCallback((hit: IssueSearchHit) => {
    setState((s) => ({
      ...s,
      step: 3,
      selectedHit: hit,
      selectedCopy: null,
      validation: null,
      canCommit: false,
    }));
  }, []);

  const selectCopy = useCallback(
    async (copy: LendableCopy) => {
      if (!state.patronId || !state.selectedHit) return;
      setState((s) => ({
        ...s,
        step: 4,
        selectedCopy: copy,
        busy: true,
        alert: null,
      }));
      try {
        const report = await issueValidate(state.patronId, copy.holding_id);
        setState((s) => ({
          ...s,
          busy: false,
          validation: report,
          canCommit: report.is_valid,
        }));
      } catch (err) {
        setState((s) => ({
          ...s,
          busy: false,
          canCommit: false,
          alert: { variant: "error", message: err instanceof Error ? err.message : "Request failed" },
        }));
      }
    },
    [state.patronId, state.selectedHit],
  );

  const goBack = useCallback(
    async (targetStep: number) => {
      if (state.loanId) {
        setState((s) => ({
          ...s,
          alert: {
            variant: "warn",
            message: "Issue already committed — use Cancel issuance to roll back.",
          },
        }));
        return;
      }
      setState((s) => ({ ...s, busy: true, alert: null }));
      try {
        await issueBack(targetStep);
        setState((s) => ({
          ...s,
          busy: false,
          step: targetStep,
          selectedHit: targetStep <= 2 ? null : s.selectedHit,
          selectedCopy: targetStep <= 3 ? null : s.selectedCopy,
          validation: targetStep <= 3 ? null : s.validation,
          canCommit: targetStep <= 3 ? false : s.canCommit,
        }));
      } catch (err) {
        setState((s) => ({
          ...s,
          busy: false,
          alert: { variant: "error", message: err instanceof Error ? err.message : "Request failed" },
        }));
      }
    },
    [state.loanId],
  );

  const commit = useCallback(async () => {
    if (!state.patronId || !state.selectedCopy) return;
    const body: Record<string, unknown> = {
      patron_id: state.patronId,
      holding_id: state.selectedCopy.holding_id,
      fulfillment_mode: mode,
    };
    if (mode !== "DESK") {
      body.destination = {
        notes: destNotes.trim() || null,
        contact: destContact.trim() || null,
      };
    }
    setState((s) => ({ ...s, busy: true, alert: null }));
    try {
      const res = await issueCommit(body, newIdempotencyKey());
      setState((s) => ({
        ...s,
        busy: false,
        step: 0,
        loanId: res.loan_id,
        doneKind: "issued",
        commitResult: res,
        cancelHidden: false,
      }));
    } catch (err) {
      setState((s) => ({
        ...s,
        busy: false,
        alert: { variant: "error", message: err instanceof Error ? err.message : "Request failed" },
      }));
    }
  }, [state.patronId, state.selectedCopy, mode, destNotes, destContact]);

  const cancelIssuance = useCallback(async () => {
    if (!state.loanId) return;
    if (!window.confirm("Cancel this issuance and return the holding to available?")) return;
    setState((s) => ({ ...s, busy: true, alert: null }));
    try {
      await issueCancel(state.loanId, newIdempotencyKey());
      setState((s) => ({
        ...s,
        busy: false,
        doneKind: "cancelled",
        commitResult: null,
        cancelHidden: true,
        loanId: null,
      }));
    } catch (err) {
      setState((s) => ({
        ...s,
        busy: false,
        alert: { variant: "error", message: err instanceof Error ? err.message : "Request failed" },
      }));
    }
  }, [state.loanId]);

  return {
    state,
    card,
    setCard,
    admission,
    setAdmission,
    name,
    setName,
    searchQuery,
    setSearchQuery,
    mode,
    setMode,
    destNotes,
    setDestNotes,
    destContact,
    setDestContact,
    candidates,
    reset,
    findPatron,
    searchPatronsByName,
    pickCandidate,
    searchCatalog,
    selectHit,
    selectCopy,
    goBack,
    commit,
    cancelIssuance,
  };
}
