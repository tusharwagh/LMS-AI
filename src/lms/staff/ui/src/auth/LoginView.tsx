import { useState, type FormEvent } from "react";

import { Alert } from "@/components/Alert/Alert";
import { Button } from "@/components/Button/Button";
import {
  FormField,
  inputClassName,
  actionRowClassName,
} from "@/components/FormField/FormField";
import { useAuth } from "./AuthContext";
import styles from "./LoginView.module.css";

export function LoginView() {
  const { login } = useAuth();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setError(null);
    setBusy(true);
    try {
      await login(username.trim(), password);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Sign in failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className={styles.page}>
      <section className={styles.hero} aria-hidden>
        <div className={styles.heroInner}>
          <div className={styles.heroMark}>L</div>
          <h2 className={styles.heroTitle}>Library circulation desk</h2>
          <p className={styles.heroText}>
            Issue, return, and search — built for K‑12 staff workflows with clear patron and copy
            context at every step.
          </p>
          <ul className={styles.heroList}>
            <li>Guided issue and return wizards</li>
            <li>AI assist with human approval before commits</li>
            <li>Catalog search and overdue follow-up</li>
          </ul>
        </div>
      </section>
      <section className={styles.formPanel}>
        <div className={styles.card}>
          <h1>LMS-AI Staff Desk</h1>
          <p className={styles.subtitle}>Sign in to continue</p>
          {error ? <Alert variant="error">{error}</Alert> : null}
          <form onSubmit={handleSubmit}>
            <FormField id="username" label="Username">
              <input
                id="username"
                name="username"
                className={inputClassName()}
                autoComplete="username"
                required
                value={username}
                onChange={(e) => setUsername(e.target.value)}
              />
            </FormField>
            <FormField id="password" label="Password">
              <input
                id="password"
                name="password"
                type="password"
                className={inputClassName()}
                autoComplete="current-password"
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
              />
            </FormField>
            <div className={actionRowClassName()}>
              <Button type="submit" fullWidth disabled={busy}>
                {busy ? "Signing in…" : "Sign in"}
              </Button>
            </div>
          </form>
        </div>
      </section>
    </div>
  );
}
