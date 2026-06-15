const FULFILLMENT_MODE_LABELS: Record<string, string> = {
  DESK: "Desk handover",
  DELIVERY: "Delivery to class / home",
  PICKUP_POINT: "Pick-up point",
};

const FULFILLMENT_STATUS_LABELS: Record<string, string> = {
  PENDING: "Pending",
  IN_TRANSIT: "In transit",
  COMPLETED: "Completed",
  CANCELLED: "Cancelled",
};

const PATRON_STATUS_LABELS: Record<string, string> = {
  ACTIVE: "Active",
  SUSPENDED: "Suspended",
  EXITED: "Exited",
};

export function formatFulfillmentMode(mode: string): string {
  return FULFILLMENT_MODE_LABELS[mode] ?? mode.replace(/_/g, " ").toLowerCase();
}

export function formatFulfillmentStatus(status: string): string {
  return FULFILLMENT_STATUS_LABELS[status] ?? status.replace(/_/g, " ").toLowerCase();
}

export function formatPatronStatus(status: string): string {
  return PATRON_STATUS_LABELS[status] ?? status;
}

export function patronIdentifiers(patron: {
  external_ref?: string | null;
  card_barcode?: string | null;
}): string {
  const parts: string[] = [];
  if (patron.external_ref) parts.push(`Admission ${patron.external_ref}`);
  if (patron.card_barcode) parts.push(`Card ${patron.card_barcode}`);
  return parts.join(" · ");
}
