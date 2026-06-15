import type { StaffView } from "@/api/types";
import { navGroupForView, VIEW_META } from "@/config/navigation";
import { useShell } from "./ShellContext";
import styles from "./AppHeader.module.css";

interface AppHeaderProps {
  activeView: StaffView;
}

export function AppHeader({ activeView }: AppHeaderProps) {
  const { toggleSidebar, openMobileNav } = useShell();
  const meta = VIEW_META[activeView];
  const group = navGroupForView(activeView);

  return (
    <header className={styles.header}>
      <div className={styles.left}>
        <button
          type="button"
          className={styles.menuButton}
          aria-label="Toggle sidebar"
          onClick={() => {
            if (window.matchMedia("(max-width: 900px)").matches) {
              openMobileNav();
            } else {
              toggleSidebar();
            }
          }}
        >
          ☰
        </button>
        <nav className={styles.breadcrumb} aria-label="Breadcrumb">
          <span className={styles.crumbMuted}>LMS-AI</span>
          {group ? (
            <>
              <span className={styles.separator}>/</span>
              <span className={styles.crumbMuted}>{group.label}</span>
            </>
          ) : null}
          <span className={styles.separator}>/</span>
          <span className={styles.crumbCurrent}>{meta.title}</span>
        </nav>
      </div>
      <div className={styles.titles}>
        <h1 className={styles.title}>{meta.title}</h1>
        <p className={styles.subtitle}>{meta.subtitle}</p>
      </div>
    </header>
  );
}
