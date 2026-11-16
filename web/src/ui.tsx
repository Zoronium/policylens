import type { ReactNode } from "react";

type IconName = "flag" | "check" | "x" | "arrow" | "file" | "chevron" | "minus";

const paths: Record<IconName, ReactNode> = {
  flag: (
    <>
      <path d="M8 2.2 14.2 13H1.8L8 2.2Z" />
      <path d="M8 6.6v3.2M8 11.6v.1" />
    </>
  ),
  check: <path d="m3 8.4 3.2 3.2L13 4.6" />,
  x: <path d="m3.6 3.6 8.8 8.8M12.4 3.6l-8.8 8.8" />,
  arrow: <path d="M3 8h10M9 4l4 4-4 4" />,
  file: (
    <>
      <path d="M4 1.8h5.2L12.4 5v9.2H4V1.8Z" />
      <path d="M9 1.8V5.2h3.4" />
    </>
  ),
  chevron: <path d="m5 6.2 3 3 3-3" />,
  minus: <path d="M3.5 8h9" />,
};

export function Icon({ name, size = 16 }: { name: IconName; size?: number }) {
  return (
    <svg
      className="icon"
      width={size}
      height={size}
      viewBox="0 0 16 16"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.5"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      {paths[name]}
    </svg>
  );
}

export function ReviewChip({ children = "Needs review" }: { children?: ReactNode }) {
  return (
    <span className="chip chip-review">
      <Icon name="flag" size={13} />
      {children}
    </span>
  );
}

export function Alert({ title, children }: { title: string; children?: ReactNode }) {
  return (
    <div className="alert" role="alert">
      <strong>{title}</strong>
      {children ? <p>{children}</p> : null}
    </div>
  );
}

export function Skeleton({ lines = 3 }: { lines?: number }) {
  return (
    <div className="skeleton" aria-hidden="true">
      {Array.from({ length: lines }, (_, i) => (
        <span key={i} style={{ width: `${92 - ((i * 17) % 40)}%` }} />
      ))}
    </div>
  );
}
