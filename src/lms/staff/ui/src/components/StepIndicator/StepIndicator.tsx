import styles from "./StepIndicator.module.css";

const ISSUE_STEPS = [
  { step: 1, label: "Patron" },
  { step: 2, label: "Search" },
  { step: 3, label: "Copy" },
  { step: 4, label: "Fulfillment" },
] as const;

interface StepIndicatorProps {
  currentStep: number;
}

export function StepIndicator({ currentStep }: StepIndicatorProps) {
  return (
    <ol className={styles.steps} aria-label="Issue workflow steps">
      {ISSUE_STEPS.map(({ step, label }) => {
        const state =
          step === currentStep ? "active" : step < currentStep ? "done" : "upcoming";
        return (
          <li key={step} className={`${styles.step} ${styles[state]}`}>
            {step}. {label}
          </li>
        );
      })}
    </ol>
  );
}
