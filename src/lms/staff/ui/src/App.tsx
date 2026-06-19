import { useState, type ReactNode } from "react";

import type { StaffView } from "@/api/types";
import { AuthProvider, useAuth } from "@/auth/AuthContext";
import { LoginView } from "@/auth/LoginView";
import { AppLayout } from "@/layout/AppLayout";
import { AdminPanel } from "@/views/AdminPanel/AdminPanel";
import { AgentChatView } from "@/views/AgentChat/AgentChatView";
import { CatalogSearch } from "@/views/CatalogSearch/CatalogSearch";
import { IssueWizardView } from "@/views/IssueWizard/IssueWizardView";
import { LlmSpendPanel } from "@/views/LlmSpendPanel/LlmSpendPanel";
import { OverdueList } from "@/views/OverdueList/OverdueList";
import { PatronLookup } from "@/views/PatronLookup/PatronLookup";
import { ReturnWizardView } from "@/views/ReturnWizard/ReturnWizardView";

const VIEW_COMPONENTS: Record<StaffView, (props: { active?: boolean }) => ReactNode> = {
  issue: () => <IssueWizardView />,
  agent: () => <AgentChatView />,
  return: () => <ReturnWizardView />,
  search: () => <CatalogSearch />,
  overdue: ({ active }) => <OverdueList active={active ?? false} />,
  patron: () => <PatronLookup />,
  spend: ({ active }) => <LlmSpendPanel active={active ?? false} />,
  admin: ({ active }) => <AdminPanel active={active ?? false} />,
};

function StaffApp() {
  const { user, loading, logout } = useAuth();
  const [view, setView] = useState<StaffView>("issue");

  if (loading) {
    return (
      <div className="app-loading">
        <p>Loading…</p>
      </div>
    );
  }

  if (!user) {
    return <LoginView />;
  }

  const userLabel = `${user.display_name || user.username} (${user.role})`;
  const ViewComponent = VIEW_COMPONENTS[view];

  return (
    <AppLayout
      activeView={view}
      userLabel={userLabel}
      isAdmin={user.role === "ADMIN"}
      onNavigate={setView}
      onLogout={logout}
    >
      <ViewComponent active={view === "overdue" || view === "admin" || view === "spend"} />
    </AppLayout>
  );
}

export function App() {
  return (
    <AuthProvider>
      <StaffApp />
    </AuthProvider>
  );
}
