import styles from "./Card.module.css";

interface CardProps {
  title?: string;
  children: React.ReactNode;
  className?: string;
}

export function Card({ title, children, className }: CardProps) {
  return (
    <section className={`${styles.card} ${className ?? ""}`.trim()}>
      {title ? <h2 className={styles.title}>{title}</h2> : null}
      {children}
    </section>
  );
}

interface SelectableCardProps {
  selected?: boolean;
  onClick?: () => void;
  children: React.ReactNode;
  className?: string;
}

export function SelectableCard({
  selected = false,
  onClick,
  children,
  className,
}: SelectableCardProps) {
  const Tag = onClick ? "button" : "div";
  return (
    <Tag
      type={onClick ? "button" : undefined}
      className={`${styles.selectable} ${selected ? styles.selected : ""} ${className ?? ""}`.trim()}
      onClick={onClick}
    >
      {children}
    </Tag>
  );
}

export function ListRow({ children }: { children: React.ReactNode }) {
  return <div className={styles.listRow}>{children}</div>;
}
