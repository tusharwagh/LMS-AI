import { Alert } from "@/components/Alert/Alert";
import { Button } from "@/components/Button/Button";
import { Card, ListRow } from "@/components/Card/Card";
import styles from "@/components/Card/Card.module.css";
import {
  FormField,
  inputClassName,
  selectClassName,
  textareaClassName,
  actionRowClassName,
} from "@/components/FormField/FormField";
import { PageShell } from "@/components/PageShell/PageShell";
import { useReturnWizardController } from "@/controllers/useReturnWizardController";
import returnStyles from "./ReturnWizard.module.css";

/** View — return wizard presentation (MVC). */
export function ReturnWizardView() {
  const {
    barcode,
    setBarcode,
    context,
    action,
    setAction,
    pickupNotes,
    setPickupNotes,
    doneMessage,
    error,
    busy,
    reset,
    lookup,
    commit,
  } = useReturnWizardController();

  return (
    <PageShell>
      <Card>
        {error ? <Alert variant="error">{error}</Alert> : null}
        {doneMessage ? (
          <Alert variant="success" role="status">
            {doneMessage}
          </Alert>
        ) : null}

        {!context && !doneMessage ? (
          <>
            <FormField id="return-barcode" label="Holding barcode">
              <input
                id="return-barcode"
                className={inputClassName()}
                placeholder="Scan book barcode"
                value={barcode}
                onChange={(e) => setBarcode(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter") void lookup();
                }}
              />
            </FormField>
            <Button onClick={() => void lookup()} disabled={busy}>
              Look up loan
            </Button>
          </>
        ) : null}

        {context ? (
          <>
            <ListRow>
              <strong>{context.catalog_title}</strong>
              <div className={styles.meta}>Copy barcode {context.holding_barcode}</div>
              <div className={styles.meta}>
                Borrower: <strong>{context.patron_display_name}</strong> · Due {context.due_date}
                {context.is_overdue ? (
                  <span className={returnStyles.overdue}> · OVERDUE</span>
                ) : null}
              </div>
              {context.open_loans_for_patron > 1 ? (
                <div className={styles.meta}>
                  {context.open_loans_for_patron - 1} other open loan
                  {context.open_loans_for_patron - 1 === 1 ? "" : "s"} for this patron
                </div>
              ) : null}
            </ListRow>
            <FormField id="return-action" label="Return method">
              <select
                id="return-action"
                className={selectClassName()}
                value={action}
                onChange={(e) => setAction(e.target.value)}
              >
                <option value="desk">Desk return — item at counter</option>
                <option value="pickup">Schedule pick-up collection</option>
              </select>
            </FormField>
            {action === "pickup" ? (
              <FormField id="return-pickup-notes" label="Pick-up notes">
                <textarea
                  id="return-pickup-notes"
                  className={textareaClassName()}
                  placeholder="Address, contact time"
                  value={pickupNotes}
                  onChange={(e) => setPickupNotes(e.target.value)}
                />
              </FormField>
            ) : null}
            <div className={actionRowClassName()}>
              <Button onClick={() => void commit()} disabled={busy}>
                Complete return
              </Button>
              <Button variant="secondary" onClick={reset} disabled={busy}>
                Scan another
              </Button>
            </div>
          </>
        ) : null}

        {doneMessage ? (
          <div className={actionRowClassName()}>
            <Button variant="secondary" onClick={reset}>
              Scan another
            </Button>
          </div>
        ) : null}
      </Card>
    </PageShell>
  );
}
