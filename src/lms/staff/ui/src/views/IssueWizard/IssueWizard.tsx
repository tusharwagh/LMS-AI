import { Alert } from "@/components/Alert/Alert";
import { Button } from "@/components/Button/Button";
import { Card, SelectableCard } from "@/components/Card/Card";
import styles from "@/components/Card/Card.module.css";
import {
  FormField,
  FieldRow,
  inputClassName,
  selectClassName,
  textareaClassName,
  actionRowClassName,
  mutedClassName,
} from "@/components/FormField/FormField";
import { PatronSummaryView } from "@/components/PatronSummary/PatronSummary";
import { StepIndicator } from "@/components/StepIndicator/StepIndicator";
import { ViolationList } from "@/components/ViolationList/ViolationList";
import { formatFulfillmentMode, formatFulfillmentStatus } from "@/lib/format";
import { useIssueWizard } from "./useIssueWizard";
import wizardStyles from "./IssueWizard.module.css";

export function IssueWizard() {
  const wizard = useIssueWizard();
  const {
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
  } = wizard;

  const showDone = state.step === 0 && state.doneKind;

  return (
    <Card title="Issue a book">
      {!showDone ? <StepIndicator currentStep={state.step} /> : null}
      {state.alert ? <Alert variant={state.alert.variant}>{state.alert.message}</Alert> : null}

      {showDone ? (
        <div className={wizardStyles.done}>
          <Alert variant="success" role="status">
            {state.doneKind === "cancelled" ? (
              <>
                <strong>{state.selectedHit?.title ?? "Book"}</strong> issuance cancelled. The copy
                is available again.
              </>
            ) : (
              <>
                <strong>{state.selectedHit?.title ?? "Book"}</strong> issued to{" "}
                <strong>{state.patronName}</strong>. Due {state.commitResult?.due_date}.
                {state.selectedCopy ? (
                  <> Copy barcode: {state.selectedCopy.barcode}.</>
                ) : null}
                {state.commitResult?.fulfillment ? (
                  <>
                    {" "}
                    {formatFulfillmentMode(state.commitResult.fulfillment.mode)} —{" "}
                    {formatFulfillmentStatus(state.commitResult.fulfillment.status)}.
                  </>
                ) : null}
              </>
            )}
          </Alert>
          <div className={actionRowClassName()}>
            <Button variant="secondary" onClick={reset}>
              Issue another
            </Button>
            {!state.cancelHidden && state.loanId ? (
              <Button variant="danger" onClick={cancelIssuance} disabled={state.busy}>
                Cancel issuance
              </Button>
            ) : null}
          </div>
        </div>
      ) : null}

      {state.step === 1 ? (
        <>
          <FieldRow>
            <FormField id="issue-card" label="Card barcode">
              <input
                id="issue-card"
                className={inputClassName()}
                placeholder="Scan or type card barcode"
                value={card}
                onChange={(e) => setCard(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter") void findPatron();
                }}
              />
            </FormField>
            <FormField id="issue-admission" label="Admission no.">
              <input
                id="issue-admission"
                className={inputClassName()}
                placeholder="External reference"
                value={admission}
                onChange={(e) => setAdmission(e.target.value)}
              />
            </FormField>
          </FieldRow>
          <FormField id="issue-name" label="Patron name">
            <input
              id="issue-name"
              className={inputClassName()}
              placeholder="Search by display name"
              value={name}
              onChange={(e) => setName(e.target.value)}
            />
          </FormField>
          <div className={actionRowClassName()}>
            <Button onClick={() => void findPatron()} disabled={state.busy}>
              Find patron
            </Button>
            <Button variant="secondary" onClick={() => void searchPatronsByName()} disabled={state.busy}>
              Search by name
            </Button>
          </div>
          {candidates.length === 0 && !state.patronMeta ? null : (
            <div className={wizardStyles.candidates}>
              {candidates.map((p) => (
                <SelectableCard key={p.id} onClick={() => void pickCandidate(p)}>
                  <strong>{p.display_name}</strong>
                  <div className={styles.meta}>
                    {p.external_ref ? `Admission ${p.external_ref}` : ""}
                    {p.external_ref && p.card_barcode ? " · " : ""}
                    {p.card_barcode ? `Card ${p.card_barcode}` : ""}
                  </div>
                </SelectableCard>
              ))}
            </div>
          )}
          {state.patronMeta ? (
            <PatronSummaryView patron={state.patronMeta} validation={state.validation} />
          ) : null}
        </>
      ) : null}

      {state.step === 2 ? (
        <>
          {state.patronMeta ? (
            <PatronSummaryView patron={state.patronMeta} validation={state.validation} />
          ) : null}
          <FormField id="issue-search" label="Search title / ISBN / call no.">
            <input
              id="issue-search"
              className={inputClassName()}
              placeholder="e.g. Python, 978..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
            />
          </FormField>
          <div className={actionRowClassName()}>
            <Button onClick={() => void searchCatalog()} disabled={state.busy}>
              Search lendable copies
            </Button>
            <Button variant="secondary" onClick={() => void goBack(1)} disabled={state.busy}>
              Back
            </Button>
          </div>
          <div className={wizardStyles.results}>
            {state.searchResults.length === 0 ? (
              <p className={mutedClassName()}>No lendable copies found.</p>
            ) : (
              state.searchResults.map((hit) => (
                <SelectableCard key={hit.catalog_id} onClick={() => selectHit(hit)}>
                  <strong>{hit.title}</strong>
                  <div className={styles.meta}>
                    {hit.lendable_copies.length} available cop
                    {hit.lendable_copies.length === 1 ? "y" : "ies"}
                  </div>
                </SelectableCard>
              ))
            )}
          </div>
        </>
      ) : null}

      {state.step === 3 && state.selectedHit ? (
        <>
          <p className={mutedClassName()}>{state.selectedHit.title}</p>
          {state.selectedHit.lendable_copies.map((copy) => (
            <SelectableCard
              key={copy.holding_id}
              selected={state.selectedCopy?.holding_id === copy.holding_id}
              onClick={() => void selectCopy(copy)}
            >
              <strong>{copy.barcode}</strong>
              <div className={styles.meta}>{state.selectedHit?.title}</div>
              <div className={styles.meta}>
                Accession {copy.accession_number}
                {copy.shelf_location ? ` · Shelf ${copy.shelf_location}` : ""}
              </div>
            </SelectableCard>
          ))}
          <div className={actionRowClassName()}>
            <Button variant="secondary" onClick={() => void goBack(2)} disabled={state.busy}>
              Back
            </Button>
          </div>
        </>
      ) : null}

      {state.step === 4 && state.selectedHit && state.selectedCopy ? (
        <>
          <p>
            Issue <strong>{state.selectedHit.title}</strong> (copy{" "}
            <strong>{state.selectedCopy.barcode}</strong>) to{" "}
            <strong>{state.patronName}</strong>
          </p>
          <FormField id="issue-mode" label="Fulfillment">
            <select
              id="issue-mode"
              className={selectClassName()}
              value={mode}
              onChange={(e) => setMode(e.target.value)}
            >
              <option value="DESK">Desk — hand to patron now</option>
              <option value="DELIVERY">Delivery to class / home</option>
              <option value="PICKUP_POINT">Pick-up point</option>
            </select>
          </FormField>
          {mode !== "DESK" ? (
            <>
              <FormField id="issue-dest-notes" label="Destination notes">
                <textarea
                  id="issue-dest-notes"
                  className={textareaClassName()}
                  placeholder="Class, room, address"
                  value={destNotes}
                  onChange={(e) => setDestNotes(e.target.value)}
                />
              </FormField>
              <FormField id="issue-dest-contact" label="Contact">
                <input
                  id="issue-dest-contact"
                  className={inputClassName()}
                  placeholder="Phone or email"
                  value={destContact}
                  onChange={(e) => setDestContact(e.target.value)}
                />
              </FormField>
            </>
          ) : null}
          {state.validation ? <ViolationList report={state.validation} /> : null}
          <div className={actionRowClassName()}>
            <Button onClick={() => void commit()} disabled={!state.canCommit || state.busy}>
              Commit issue
            </Button>
            <Button variant="secondary" onClick={() => void goBack(3)} disabled={state.busy}>
              Back
            </Button>
          </div>
        </>
      ) : null}
    </Card>
  );
}
