import type { ReactNode } from "react";
import { Window } from "../stageshow/kit";

// Wide: a real desktop window. Compact (phone column): a plain card with a title line, because a
// desktop window squeezed into a phone column reads as a shrunk screenshot.
export default function Frame({ compact, title, className, children }: { compact: boolean; title: string; className: string; children: ReactNode }) {
  if (!compact)
    return (
      <Window title={title} className={className}>
        {children}
      </Window>
    );
  return (
    <div className={`${className} sc-card`} role="group" aria-label={title}>
      <div className="sc-card-bar">
        <span className="sc-card-title">{title}</span>
      </div>
      <div className="sc-card-body">{children}</div>
    </div>
  );
}
