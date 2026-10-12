import { DAY_LETTER, DAY_SHORT, formatHHMM } from "./dates";

/**
 * Group a section's meetings into lines like "MWF 9–9:50am" / "Lab Tu 2–4:50pm".
 */
export function meetingSummary(meetings) {
  const groups = new Map();
  for (const m of meetings) {
    const key = `${m.kind}|${m.start_time}|${m.end_time}`;
    if (!groups.has(key)) groups.set(key, { ...m, days: [] });
    groups.get(key).days.push(m.day_of_week);
  }
  return [...groups.values()].map((g) => {
    const days = g.days.sort((a, b) => a - b).map((d) => DAY_LETTER[d]).join("");
    const label = g.kind === "Lecture" ? "" : `${g.kind} `;
    return `${label}${days} ${formatHHMM(g.start_time)}–${formatHHMM(g.end_time)}`;
  });
}

export const courseCode = (s) => `${s.department} ${s.number}`;

export function describeConflict(conflict, sectionsById) {
  const [a, b] = conflict.section_ids.map((id) => sectionsById[id]);
  const name = (s) => (s ? courseCode(s) : "A section");
  return `${name(a)} and ${name(b)} overlap on ${DAY_SHORT[conflict.day_of_week]} ` +
    `${formatHHMM(conflict.start)}–${formatHHMM(conflict.end)}`;
}
