import type { StaffView } from "@/api/types";

export interface NavItem {
  view: StaffView;
  label: string;
  shortLabel: string;
  adminOnly?: boolean;
}

export interface NavGroup {
  id: string;
  label: string;
  items: NavItem[];
}

/** CRM-style grouped navigation — single source for sidebar and view registry. */
export const NAV_GROUPS: NavGroup[] = [
  {
    id: "circulation",
    label: "Circulation",
    items: [
      { view: "issue", label: "Issue book", shortLabel: "Issue" },
      { view: "return", label: "Return book", shortLabel: "Return" },
      { view: "agent", label: "AI assist", shortLabel: "AI" },
    ],
  },
  {
    id: "catalog",
    label: "Catalog",
    items: [
      { view: "search", label: "Catalog search", shortLabel: "Search" },
      { view: "overdue", label: "Overdue loans", shortLabel: "Overdue" },
    ],
  },
  {
    id: "people",
    label: "Patrons",
    items: [{ view: "patron", label: "Patron lookup", shortLabel: "Patron" }],
  },
  {
    id: "admin",
    label: "Administration",
    items: [
      { view: "dashboard", label: "Dashboard", shortLabel: "Dashboard" },
      { view: "spend", label: "LLM costs", shortLabel: "Costs" },
      { view: "admin", label: "Admin panel", shortLabel: "Admin", adminOnly: true },
    ],
  },
];

export interface ViewMeta {
  title: string;
  subtitle: string;
  groupId: string;
}

export const VIEW_META: Record<StaffView, ViewMeta> = {
  issue: {
    title: "Issue a book",
    subtitle: "Identify patron, select a lendable copy, and commit the loan.",
    groupId: "circulation",
  },
  return: {
    title: "Return a book",
    subtitle: "Scan the copy barcode to complete a desk return or schedule pick-up.",
    groupId: "circulation",
  },
  agent: {
    title: "AI-assisted issue",
    subtitle: "Describe the transaction in plain language; approve before any commit.",
    groupId: "circulation",
  },
  search: {
    title: "Catalog search",
    subtitle: "Find titles and holdings across the library catalog.",
    groupId: "catalog",
  },
  overdue: {
    title: "Overdue loans",
    subtitle: "Review loans past due date for follow-up with patrons.",
    groupId: "catalog",
  },
  patron: {
    title: "Patron lookup",
    subtitle: "Search patrons by card, admission number, or display name.",
    groupId: "people",
  },
  admin: {
    title: "Administration",
    subtitle: "Seed data and operational tools for librarians and admins.",
    groupId: "admin",
  },
  spend: {
    title: "LLM costs",
    subtitle: "Review AI gateway spend, token usage, and request logs.",
    groupId: "admin",
  },
  dashboard: {
    title: "Dashboard & reports",
    subtitle: "Circulation statistics, holdings status, and customizable reports.",
    groupId: "admin",
  },
};

export function navGroupForView(view: StaffView): NavGroup | undefined {
  const meta = VIEW_META[view];
  return NAV_GROUPS.find((g) => g.id === meta.groupId);
}

export function flattenNavItems(isAdmin: boolean): NavItem[] {
  return NAV_GROUPS.flatMap((group) =>
    group.items.filter((item) => !item.adminOnly || isAdmin),
  );
}
