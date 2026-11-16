import "./mascot.css";

export type Mood = "idle" | "reading" | "thinking" | "done";

// Lens: the brand's magnifier with a face. Moods are CSS only (see mascot.css), so it costs nothing
// to render and respects prefers-reduced-motion.
export default function Mascot({ mood = "idle", size = 64, label }: { mood?: Mood; size?: number; label?: string }) {
  return (
    <svg
      className="lens"
      data-mood={mood}
      width={size}
      height={size}
      viewBox="0 0 64 64"
      role={label ? "img" : undefined}
      aria-label={label}
      aria-hidden={label ? undefined : true}
    >
      <g className="lens-body">
        <rect className="lens-handle" x="43" y="40" width="7" height="22" rx="3.5" transform="rotate(-45 46.5 51)" />
        <circle className="lens-glass" cx="27" cy="27" r="20" />
        <g className="lens-eyes">
          {/* the outer group places the eye; the inner one is what CSS animates (blink) */}
          <g transform="translate(20 25)">
            <g className="lens-eye">
              <circle className="lens-white" r="4.6" />
              <circle className="lens-pupil" r="2.4" />
            </g>
          </g>
          <g transform="translate(34 25)">
            <g className="lens-eye">
              <circle className="lens-white" r="4.6" />
              <circle className="lens-pupil" r="2.4" />
            </g>
          </g>
        </g>
        <path className="lens-mouth lens-mouth--smile" d="M21 35 Q27 40 33 35" />
        <ellipse className="lens-mouth lens-mouth--o" cx="27" cy="36.5" rx="2.4" ry="2.9" />
      </g>
      <g className="lens-dots">
        <circle cx="41" cy="6" r="2.2" />
        <circle cx="48" cy="6" r="2.2" />
        <circle cx="55" cy="6" r="2.2" />
      </g>
    </svg>
  );
}
