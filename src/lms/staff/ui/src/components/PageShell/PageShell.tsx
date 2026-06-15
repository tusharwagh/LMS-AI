import type { ReactNode } from "react";

import styles from "./PageShell.module.css";

interface PageShellProps {
  children: ReactNode;
}

/** CRM-style content panel — wraps view forms below the app header. */
export function PageShell({ children }: PageShellProps) {
  return <div className={styles.panel}>{children}</div>;
}
