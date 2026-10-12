import { courseColor } from "../lib/colors";
import { DAY_SHORT, formatMinutes, hhmmToMinutes } from "../lib/dates";
import { layoutOverlaps } from "../lib/layout";
import { courseCode } from "../lib/sections";

/**
 * The planner's weekly grid for one candidate schedule.
 * sections: schedule sections (with meetings, has_conflict)
 * preview:  a section being hovered in the course list, drawn as a ghost
 */
export default function WeekGrid({ sections, preview = null, compact = false }) {
  const blocks = [];
  const add = (section, isPreview) => {
    for (const m of section.meetings) {
      blocks.push({
        key: `${isPreview ? "p" : "s"}-${section.id}-${m.id}`,
        day: m.day_of_week,
        start: hhmmToMinutes(m.start_time),
        end: hhmmToMinutes(m.end_time),
        section,
        meeting: m,
        preview: isPreview,
      });
    }
  };
  sections.forEach((s) => add(s, false));
  if (preview && !sections.some((s) => s.id === preview.id)) add(preview, true);

  // A preview block that would overlap a real one is flagged too.
  for (const b of blocks) {
    b.conflict = b.preview
      ? blocks.some((o) => !o.preview && o.day === b.day && o.start < b.end && b.start < o.end)
      : b.section.has_conflict &&
        blocks.some((o) => !o.preview && o.section.id !== b.section.id && o.day === b.day && o.start < b.end && b.start < o.end);
  }

  const days = [0, 1, 2, 3, 4];
  if (blocks.some((b) => b.day === 5 || b.day === 6)) days.push(5, 6);
  const startHour = Math.min(8, ...blocks.map((b) => Math.floor(b.start / 60)));
  const endHour = Math.max(18, ...blocks.map((b) => Math.ceil(b.end / 60)));
  const hourHeight = compact ? 30 : 52;
  const pxPerMinute = hourHeight / 60;
  const hours = Array.from({ length: endHour - startHour }, (_, i) => startHour + i);

  return (
    <div className={`weekgrid ${compact ? "weekgrid-compact" : ""}`}>
      <div className="weekgrid-head" style={{ gridTemplateColumns: `48px repeat(${days.length}, 1fr)` }}>
        <div />
        {days.map((d) => <div key={d} className="weekgrid-dayname">{DAY_SHORT[d]}</div>)}
      </div>
      <div className="weekgrid-body" style={{ gridTemplateColumns: `48px repeat(${days.length}, 1fr)` }}>
        <div className="weekgrid-hours">
          {hours.map((h) => (
            <div key={h} className="weekgrid-hour" style={{ height: hourHeight }}>
              {formatMinutes(h * 60)}
            </div>
          ))}
        </div>
        {days.map((d) => (
          <div key={d} className="weekgrid-day" style={{ height: hours.length * hourHeight }}>
            {hours.map((h) => <div key={h} className="weekgrid-line" style={{ height: hourHeight }} />)}
            {layoutOverlaps(blocks.filter((b) => b.day === d)).map((b) => {
              const color = courseColor(b.section.course_id);
              return (
                <div
                  key={b.key}
                  className={`weekgrid-block ${b.preview ? "is-preview" : ""} ${b.conflict ? "is-conflict" : ""}`}
                  style={{
                    top: (b.start - startHour * 60) * pxPerMinute,
                    height: Math.max((b.end - b.start) * pxPerMinute, 14),
                    left: `calc(${(b.col / b.cols) * 100}% + 2px)`,
                    width: `calc(${100 / b.cols}% - 4px)`,
                    "--block-color": color,
                  }}
                  title={`${courseCode(b.section)} ${b.meeting.kind} · ${b.section.title}\n` +
                    `${formatMinutes(b.start, { compact: false })}–${formatMinutes(b.end, { compact: false })}` +
                    `${b.section.location ? ` · ${b.section.location}` : ""}`}
                >
                  <div className="weekgrid-block-title">
                    {b.conflict && <span aria-label="Time conflict">⚠ </span>}
                    {courseCode(b.section)}
                    {b.meeting.kind !== "Lecture" && ` ${b.meeting.kind}`}
                  </div>
                  {!compact && (
                    <div className="weekgrid-block-meta">
                      {formatMinutes(b.start, { compact: false })}–{formatMinutes(b.end, { compact: false })}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        ))}
      </div>
    </div>
  );
}
