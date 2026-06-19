import type { StaffView } from "@/api/types";
import styles from "./Sidebar.module.css";

const NAV_ITEMS: Array<{ view: StaffView; label: string; adminOnly?: boolean }> = [
  { view: "issue", label: "Issue book" },
  { view: "agent", label: "AI assist" },
  { view: "return", label: "Return book" },
  { view: "search", label: "Catalog search" },
  { view: "overdue", label: "Overdue" },
  { view: "patron", label: "Patron lookup" },
  { view: "spend", label: "LLM costs" },
  { view: "admin", label: "Admin", adminOnly: true },
];

interface SidebarProps {
  activeView: StaffView;
  userLabel: string;
  isAdmin: boolean;
  onNavigate: (view: StaffView) => void;
  onLogout: () => void;
}

export function Sidebar({
  activeView,
  userLabel,
  isAdmin,
  onNavigate,
  onLogout,
}: SidebarProps) {
  return (
    <nav className={styles.nav} aria-label="Staff desk navigation">
      <div className={styles.brand}>LMS-AI Staff</div>
      <div className={styles.user}>{userLabel}</div>
      <ul className={styles.list}>
        {NAV_ITEMS.filter((item) => !item.adminOnly || isAdmin).map((item) => (
          <li key={item.view}>
            <button
              type="button"
              className={`${styles.link} ${activeView === item.view ? styles.active : ""}`}
              aria-current={activeView === item.view ? "page" : undefined}
              onClick={() => onNavigate(item.view)}
            >
              {item.label}
            </button>
          </li>
        ))}
      </ul>
      <button type="button" className={styles.logout} onClick={onLogout}>
        Sign out
      </button>
    </nav>
  );
}
