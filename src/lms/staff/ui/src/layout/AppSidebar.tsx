import type { StaffView } from "@/api/types";
import { NAV_GROUPS } from "@/config/navigation";
import { useShell } from "./ShellContext";
import styles from "./AppSidebar.module.css";

const VIEW_ICONS: Record<StaffView, string> = {
  issue: "📖",
  return: "↩",
  agent: "✦",
  search: "🔍",
  overdue: "⏱",
  patron: "👤",
  spend: "💰",
  dashboard: "📊",
  admin: "⚙",
};

interface AppSidebarProps {
  activeView: StaffView;
  userLabel: string;
  isAdmin: boolean;
  onNavigate: (view: StaffView) => void;
  onLogout: () => void;
}

export function AppSidebar({
  activeView,
  userLabel,
  isAdmin,
  onNavigate,
  onLogout,
}: AppSidebarProps) {
  const { sidebarCollapsed, mobileNavOpen, closeMobileNav } = useShell();

  function handleNavigate(view: StaffView) {
    onNavigate(view);
    closeMobileNav();
  }

  return (
    <>
      {mobileNavOpen ? (
        <button
          type="button"
          className={styles.backdrop}
          aria-label="Close navigation"
          onClick={closeMobileNav}
        />
      ) : null}
      <aside
        className={`${styles.sidebar} ${sidebarCollapsed ? styles.collapsed : ""} ${
          mobileNavOpen ? styles.mobileOpen : ""
        }`}
        role="navigation"
        aria-label="Staff desk navigation"
      >
        <div className={styles.header}>
          <div className={styles.brandMark}>L</div>
          {!sidebarCollapsed ? (
            <div>
              <div className={styles.brand}>LMS-AI</div>
              <div className={styles.brandSub}>Staff desk</div>
            </div>
          ) : null}
        </div>

        <nav className={styles.content}>
          {NAV_GROUPS.map((group) => {
            const items = group.items.filter((item) => !item.adminOnly || isAdmin);
            if (items.length === 0) return null;
            return (
              <div key={group.id} className={styles.group}>
                {!sidebarCollapsed ? (
                  <div className={styles.groupLabel}>{group.label}</div>
                ) : null}
                <ul className={styles.menu}>
                  {items.map((item) => (
                    <li key={item.view}>
                      <button
                        type="button"
                        className={`${styles.menuButton} ${
                          activeView === item.view ? styles.active : ""
                        }`}
                        aria-current={activeView === item.view ? "page" : undefined}
                        title={sidebarCollapsed ? item.label : undefined}
                        onClick={() => handleNavigate(item.view)}
                      >
                        <span className={styles.icon} aria-hidden>
                          {VIEW_ICONS[item.view]}
                        </span>
                        {!sidebarCollapsed ? (
                          <span className={styles.label}>{item.label}</span>
                        ) : null}
                      </button>
                    </li>
                  ))}
                </ul>
              </div>
            );
          })}
        </nav>

        <div className={styles.footer}>
          {!sidebarCollapsed ? <div className={styles.user}>{userLabel}</div> : null}
          <button type="button" className={styles.logout} onClick={onLogout}>
            {sidebarCollapsed ? "⎋" : "Sign out"}
          </button>
        </div>
      </aside>
    </>
  );
}
