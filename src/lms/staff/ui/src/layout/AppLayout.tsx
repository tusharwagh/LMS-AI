import type { ReactNode } from "react";

import type { StaffView } from "@/api/types";
import { AppHeader } from "./AppHeader";
import { AppSidebar } from "./AppSidebar";
import { ShellProvider } from "./ShellContext";
import styles from "./AppLayout.module.css";

interface AppLayoutProps {
  activeView: StaffView;
  userLabel: string;
  isAdmin: boolean;
  onNavigate: (view: StaffView) => void;
  onLogout: () => void;
  children: ReactNode;
}

export function AppLayout(props: AppLayoutProps) {
  return (
    <ShellProvider>
      <div className={styles.shell}>
        <AppSidebar {...props} />
        <div className={styles.workspace}>
          <AppHeader activeView={props.activeView} />
          <main className={styles.main}>{props.children}</main>
        </div>
      </div>
    </ShellProvider>
  );
}
