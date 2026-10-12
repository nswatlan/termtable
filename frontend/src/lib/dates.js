// Date helpers. The API speaks naive local ISO strings ("2026-10-04T09:00:00"),
// so everything here works in the browser's local time.

export const pad = (n) => String(n).padStart(2, "0");

// Backend day_of_week: 0 = Monday ... 6 = Sunday.
export const DAY_SHORT = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
export const DAY_LETTER = ["M", "T", "W", "Th", "F", "Sa", "Su"];
// JS getDay(): 0 = Sunday. RFC 5545 weekday codes indexed the same way.
export const JS_DAY_CODES = ["SU", "MO", "TU", "WE", "TH", "FR", "SA"];
export const JS_DAY_SHORT = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];
export const MONTHS = [
  "January", "February", "March", "April", "May", "June",
  "July", "August", "September", "October", "November", "December",
];

/** Parse "YYYY-MM-DD" or "YYYY-MM-DDTHH:MM[:SS]" as a local time. */
export function parseLocal(value) {
  const [datePart, timePart = "00:00:00"] = value.split("T");
  const [y, m, d] = datePart.split("-").map(Number);
  const [hh, mm, ss = 0] = timePart.split(":").map(Number);
  return new Date(y, m - 1, d, hh, mm, ss);
}

export const toISODate = (d) => `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
export const toISOTime = (d) => `${pad(d.getHours())}:${pad(d.getMinutes())}`;
export const toISODateTime = (d) => `${toISODate(d)}T${toISOTime(d)}:00`;

export function addDays(d, n) {
  const r = new Date(d);
  r.setDate(r.getDate() + n);
  return r;
}

export function addMonths(d, n) {
  return new Date(d.getFullYear(), d.getMonth() + n, 1);
}

export const startOfDay = (d) => new Date(d.getFullYear(), d.getMonth(), d.getDate());
export const startOfWeek = (d) => addDays(startOfDay(d), -d.getDay()); // Sunday
export const startOfMonth = (d) => new Date(d.getFullYear(), d.getMonth(), 1);

export const sameDay = (a, b) =>
  a.getFullYear() === b.getFullYear() && a.getMonth() === b.getMonth() && a.getDate() === b.getDate();

export const minutesSinceMidnight = (d) => d.getHours() * 60 + d.getMinutes();

/** "HH:MM" -> minutes since midnight */
export function hhmmToMinutes(value) {
  const [h, m] = value.split(":").map(Number);
  return h * 60 + m;
}

/** Minutes since midnight -> "9am" / "9:30am" */
export function formatMinutes(total, { compact = true } = {}) {
  const h = Math.floor(total / 60) % 24;
  const m = total % 60;
  const suffix = h < 12 ? "am" : "pm";
  const h12 = h % 12 === 0 ? 12 : h % 12;
  if (compact && m === 0) return `${h12}${suffix}`;
  return `${h12}:${pad(m)}${suffix}`;
}

export const formatTime = (d, opts) => formatMinutes(minutesSinceMidnight(d), opts);
export const formatHHMM = (value, opts) => formatMinutes(hhmmToMinutes(value), opts);

export function formatShortDate(d) {
  return `${JS_DAY_SHORT[d.getDay()]}, ${MONTHS[d.getMonth()].slice(0, 3)} ${d.getDate()}`;
}

export function formatDue(value) {
  const d = parseLocal(value);
  return `${formatShortDate(d)} · ${formatTime(d)}`;
}
