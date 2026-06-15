import { useCallback, useState } from "react";

import type { ReturnContext } from "@/models";
import { returnCommit, returnPickupInitiate, returnStart } from "@/models";
import { newIdempotencyKey } from "@/lib/uuid";

/** Controller — return wizard state and actions (MVC). */
export function useReturnWizardController() {
  const [barcode, setBarcode] = useState("");
  const [context, setContext] = useState<ReturnContext | null>(null);
  const [action, setAction] = useState("desk");
  const [pickupNotes, setPickupNotes] = useState("");
  const [doneMessage, setDoneMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const reset = useCallback(() => {
    setBarcode("");
    setContext(null);
    setAction("desk");
    setPickupNotes("");
    setDoneMessage(null);
    setError(null);
  }, []);

  const lookup = useCallback(async () => {
    const value = barcode.trim();
    if (!value) {
      setError("Enter holding barcode.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const ctx = await returnStart(value);
      setContext(ctx);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Request failed");
    } finally {
      setBusy(false);
    }
  }, [barcode]);

  const commit = useCallback(async () => {
    if (!context) return;
    setBusy(true);
    setError(null);
    try {
      if (action === "desk") {
        await returnCommit(context.holding_barcode, newIdempotencyKey());
        setDoneMessage(
          `${context.catalog_title} returned. Copy ${context.holding_barcode} is available again.`,
        );
      } else {
        await returnPickupInitiate(
          context.loan_id,
          pickupNotes.trim() || null,
          newIdempotencyKey(),
        );
        setDoneMessage(
          `Pick-up collection scheduled for ${context.catalog_title}. Loan stays open until the item is collected from ${context.patron_display_name}.`,
        );
      }
      setContext(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Request failed");
    } finally {
      setBusy(false);
    }
  }, [action, context, pickupNotes]);

  return {
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
  };
}
