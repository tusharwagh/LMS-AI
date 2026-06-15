import styles from "./FormField.module.css";

interface FormFieldProps {
  id: string;
  label: string;
  children: React.ReactNode;
  hint?: string;
}

export function FormField({ id, label, children, hint }: FormFieldProps) {
  return (
    <div className={styles.field}>
      <label htmlFor={id}>{label}</label>
      {children}
      {hint ? <span className={styles.hint}>{hint}</span> : null}
    </div>
  );
}

export function FieldRow({ children }: { children: React.ReactNode }) {
  return <div className={styles.row}>{children}</div>;
}

export function inputClassName(): string {
  return styles.input;
}

export function textareaClassName(): string {
  return styles.textarea;
}

export function selectClassName(): string {
  return styles.select;
}

export function actionRowClassName(): string {
  return styles.actions;
}

export function mutedClassName(): string {
  return styles.muted;
}
