// Personal event colors (must match COLORS in backend/app/calendar.py).
export const EVENT_COLORS = {
  blue: "#3f6fd8",
  green: "#2e8b57",
  red: "#d0453a",
  yellow: "#d9a21b",
  purple: "#8a4fbf",
  orange: "#e0762b",
  teal: "#1f9a9a",
  gray: "#6b7280",
};

const COURSE_PALETTE = [
  "#4f7cff", "#e8590c", "#2f9e44", "#ae3ec9", "#1098ad",
  "#d6336c", "#5c940d", "#f08c00", "#3b5bdb", "#c2255c",
];

export const courseColor = (courseId) => COURSE_PALETTE[courseId % COURSE_PALETTE.length];
