import { useState } from "react";

/** Read-only star rating, e.g. ★★★★☆ 4.2 (12) */
export function Stars({ rating, count, showCount = true, size = "sm" }) {
  if (rating == null) {
    return <span className={`stars stars-${size} muted`}>No ratings yet</span>;
  }
  const rounded = Math.round(rating);
  return (
    <span className={`stars stars-${size}`} title={`${rating.toFixed(2)} out of 5`}>
      <span className="stars-glyphs" aria-hidden>
        {"★".repeat(rounded)}
        <span className="stars-empty">{"★".repeat(5 - rounded)}</span>
      </span>
      <span className="stars-value">{rating.toFixed(1)}</span>
      {showCount && count != null && <span className="muted"> ({count})</span>}
    </span>
  );
}

/** Clickable 1–5 star input. */
export function StarInput({ value, onChange }) {
  const [hover, setHover] = useState(null);
  const shown = hover ?? value ?? 0;
  return (
    <span className="star-input" onMouseLeave={() => setHover(null)} role="radiogroup" aria-label="Rating">
      {[1, 2, 3, 4, 5].map((n) => (
        <button
          key={n}
          type="button"
          role="radio"
          aria-checked={value === n}
          aria-label={`${n} star${n > 1 ? "s" : ""}`}
          className={n <= shown ? "on" : ""}
          onMouseEnter={() => setHover(n)}
          onClick={() => onChange(n)}
        >
          ★
        </button>
      ))}
    </span>
  );
}
