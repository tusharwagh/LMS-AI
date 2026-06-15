import styles from "./Alert.module.css";

export type AlertVariant = "error" | "success" | "warn" | "info";

interface AlertProps {
  variant: AlertVariant;
  children: React.ReactNode;
  role?: "alert" | "status";
}

export function Alert({ variant, children, role = "alert" }: AlertProps) {
  return (
    <div className={`${styles.alert} ${styles[variant]}`} role={role}>
      {children}
    </div>
  );
}
