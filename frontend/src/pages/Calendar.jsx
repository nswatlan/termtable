import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { api, qs } from "../api";
import AssignmentDialog from "../components/AssignmentDialog";
import EventDialog from "../components/EventDialog";
import { EVENT_COLORS, courseColor } from "../lib/colors";
import {
  JS_DAY_SHORT, MONTHS, addDays, addMonths, formatMinutes, formatShortDate, formatTime,
  minutesSinceMidnight, parseLocal, sameDay, startOfDay, startOfMonth, startOfWeek, toISODate,
} from "../lib/dates";
import { layoutOverlaps } from "../lib/layout";

const HOUR_HEIGHT = 48;
const VIEWS = ["day", "week", "month"];
const CATEGORY_LABEL = { homework: "Homework", quiz: "Quiz", midterm: "Midterm", final: "Final" };

function readStoredView() {
  try {
    const v = localStorage.getItem("calendar.view");
    return VIEWS.includes(v) ? v : "week";
  } catch {
    return "week";
  }
}

function visibleRange(view, cursor) {
  if (view === "day") return [cursor, addDays(cursor, 1)];
  if (view === "week") {
    const start = startOfWeek(cursor);
    return [start, addDays(start, 7)];
  }
  const start = startOfWeek(startOfMonth(cursor));
  return [start, addDays(start, 42)];
}

function title(view, cursor) {
  if (view === "day") {
    return cursor.toLocaleDateString(undefined, { weekday: "long", month: "long", day: "numeric", year: "numeric" });
  }
  if (view === "month") return `${MONTHS[cursor.getMonth()]} ${cursor.getFullYear()}`;
  const start = startOfWeek(cursor);
  const end = addDays(start, 6);
  const m = (d) => MONTHS[d.getMonth()].slice(0, 3);
  if (start.getMonth() === end.getMonth()) return `${m(start)} ${start.getDate()} – ${end.getDate()}, ${end.getFullYear()}`;
  if (start.getFullYear() === end.getFullYear()) {
    return `${m(start)} ${start.getDate()} – ${m(end)} ${end.getDate()}, ${end.getFullYear()}`;
  }
  return `${m(start)} ${start.getDate()}, ${start.getFullYear()} – ${m(end)} ${end.getDate()}, ${end.getFullYear()}`;
}

const TASK_COLOR = "#5f6b7a";

function itemColor(item) {
  if (item.type === "event" || item.type === "shared") return EVENT_COLORS[item.color] ?? EVENT_COLORS.blue;
  if (item.type === "task") return item.course_id ? courseColor(item.course_id) : TASK_COLOR;
  return courseColor(item.course_id);
}

function itemLabel(item) {
  if (item.type === "assignment") return `${item.score != null ? "✓" : "📝"} ${item.course_code}: ${item.title}`;
  if (item.type === "task") return `${item.completed ? "☑" : "☐"} ${item.course_code ? `${item.course_code}: ` : ""}${item.title}`;
  if (item.type === "shared" && item.invitation_status === "pending") return `Invited: ${item.title}`;
  return item.title;
}

// Assignment due times are points in time, shown in the all-day row.
const isPoint = (item) => item.type === "assignment" || item.type === "task";
// Which filter checkbox controls an item.
const FILTER_KEY = { event: "event", shared: "shared", class: "class", assignment: "assignment", task: "assignment" };

function itemClass(item) {
  return `${item.type}${item.type === "shared" && item.invitation_status === "pending" ? " pending" : ""}${item.completed ? " completed" : ""}`;
}

// An item is on a day if it overlaps it; zero-length items (assignment due
// times) count on the day they fall.
function onDay(item, day) {
  const dayStart = startOfDay(day);
  const dayEnd = addDays(dayStart, 1);
  if (item.startDate.getTime() === item.endDate.getTime()) {
    return item.startDate >= dayStart && item.startDate < dayEnd;
  }
  return item.startDate < dayEnd && item.endDate > dayStart;
}

export default function Calendar() {
  const [view, setView] = useState(readStoredView);
  const [cursor, setCursor] = useState(() => startOfDay(new Date()));
  const [items, setItems] = useState([]);
  const [filters, setFilters] = useState({ event: true, shared: true, class: true, assignment: true });
  const [dialog, setDialog] = useState(null); // { event } or { defaults }
  const [taskDialog, setTaskDialog] = useState(null); // { task } or { defaults }
  const [detail, setDetail] = useState(null); // a class, assignment or shared item
  const [classes, setClasses] = useState([]);
  const [invites, setInvites] = useState([]);
  const [showInvites, setShowInvites] = useState(false);
  const [error, setError] = useState(null);

  const [rangeStart, rangeEnd] = visibleRange(view, cursor);
  const startKey = toISODate(rangeStart);
  const endKey = toISODate(rangeEnd);

  const load = useCallback(async () => {
    try {
      const data = await api.get(`/calendar${qs({ start: startKey, end: endKey })}`);
      setItems(data.map((i) => ({ ...i, startDate: parseLocal(i.start), endDate: parseLocal(i.end) })));
      setError(null);
    } catch (e) {
      setError(e.message);
    }
  }, [startKey, endKey]);

  useEffect(() => { load(); }, [load]);

  const loadInvites = useCallback(() => {
    api.get("/invitations").then(setInvites).catch(() => {});
  }, []);
  useEffect(() => {
    loadInvites();
    api.get("/homework").then((d) => setClasses(d.classes)).catch(() => {});
  }, [loadInvites]);

  async function respond(invitationId, response) {
    try {
      await api.post(`/invitations/${invitationId}/respond`, { response });
      setDetail(null);
      loadInvites();
      load();
      window.dispatchEvent(new Event("invitations:changed"));
    } catch (e) {
      setError(e.message);
    }
  }

  function changeView(v) {
    setView(v);
    try { localStorage.setItem("calendar.view", v); } catch { /* storage unavailable */ }
  }

  function step(direction) {
    if (view === "day") setCursor((c) => addDays(c, direction));
    else if (view === "week") setCursor((c) => addDays(c, 7 * direction));
    else setCursor((c) => addMonths(c, direction));
  }

  const visible = useMemo(() => items.filter((i) => filters[FILTER_KEY[i.type]]), [items, filters]);

  const openItem = (item) => {
    if (item.type === "event") setDialog({ event: item.event });
    else if (item.type === "task") setTaskDialog({ task: item.task });
    else setDetail(item);
  };
  const createAt = (start, allDay = false) => setDialog({ defaults: { start, allDay } });
  const days = view === "day" ? [cursor] : Array.from({ length: 7 }, (_, i) => addDays(rangeStart, i));

  return (
    <div className="calendar">
      <div className="cal-toolbar">
        <button className="btn btn-primary" onClick={() => createAt(nextHalfHour(cursor))}>+ Event</button>
        <button className="btn" onClick={() => setTaskDialog({ defaults: { due: cursor } })}>+ Assignment</button>
        <button className={`btn ${invites.length ? "btn-attention" : ""}`} onClick={() => setShowInvites(true)}>
          Invitations{invites.length > 0 && <span className="count-badge">{invites.length}</span>}
        </button>
        <button className="btn" onClick={() => setCursor(startOfDay(new Date()))}>Today</button>
        <div className="cal-nav">
          <button className="btn btn-icon" onClick={() => step(-1)} aria-label="Previous">‹</button>
          <button className="btn btn-icon" onClick={() => step(1)} aria-label="Next">›</button>
        </div>
        <h1 className="cal-title">{title(view, cursor)}</h1>
        <div className="cal-filters">
          {[["event", "My events"], ["shared", "Shared"], ["class", "Classes"], ["assignment", "Assignments"]].map(([key, label]) => (
            <label key={key} className="check">
              <input
                type="checkbox"
                checked={filters[key]}
                onChange={(e) => setFilters((f) => ({ ...f, [key]: e.target.checked }))}
              />
              {label}
            </label>
          ))}
        </div>
        <div className="segmented">
          {VIEWS.map((v) => (
            <button key={v} className={view === v ? "active" : ""} onClick={() => changeView(v)}>
              {v[0].toUpperCase() + v.slice(1)}
            </button>
          ))}
        </div>
      </div>

      {error && <div className="alert alert-error">{error}</div>}

      {view === "month" ? (
        <MonthGrid
          cursor={cursor}
          start={rangeStart}
          items={visible}
          onItemClick={openItem}
          onDayClick={(d) => { setCursor(d); changeView("day"); }}
          onEmptyClick={(d) => createAt(d, true)}
        />
      ) : (
        <TimeGrid days={days} items={visible} onItemClick={openItem} onSlotClick={createAt} />
      )}

      {dialog && (
        <EventDialog
          event={dialog.event ?? null}
          defaults={dialog.defaults}
          onClose={() => setDialog(null)}
          onSaved={() => { setDialog(null); load(); }}
        />
      )}
      {taskDialog && (
        <AssignmentDialog
          task={taskDialog.task ?? null}
          defaults={taskDialog.defaults}
          classes={classes}
          onClose={() => setTaskDialog(null)}
          onSaved={() => { setTaskDialog(null); load(); }}
        />
      )}
      {detail && <ItemDetail item={detail} onClose={() => setDetail(null)} onRespond={respond} />}
      {showInvites && (
        <InvitationsPanel
          invites={invites}
          onRespond={respond}
          onClose={() => setShowInvites(false)}
          onShow={(inv) => { setShowInvites(false); setCursor(startOfDay(parseLocal(inv.start_at))); }}
        />
      )}
    </div>
  );
}

function nextHalfHour(day) {
  const now = new Date();
  if (!sameDay(day, now)) return new Date(day.getFullYear(), day.getMonth(), day.getDate(), 9);
  const d = new Date(now);
  d.setSeconds(0, 0);
  d.setMinutes(d.getMinutes() < 30 ? 30 : 60); // 60 rolls over to the next hour
  return d;
}

// --- day & week ------------------------------------------------------------

function TimeGrid({ days, items, onItemClick, onSlotClick }) {
  const scrollRef = useRef(null);
  const [now, setNow] = useState(new Date());

  useEffect(() => {
    if (scrollRef.current) scrollRef.current.scrollTop = 7 * HOUR_HEIGHT;
    const timer = setInterval(() => setNow(new Date()), 60_000);
    return () => clearInterval(timer);
  }, []);

  const cols = `56px repeat(${days.length}, 1fr)`;

  function handleColumnClick(e, day) {
    if (e.target !== e.currentTarget) return;
    const y = e.clientY - e.currentTarget.getBoundingClientRect().top;
    const minutes = Math.max(0, Math.min(23 * 60 + 30, Math.floor(y / HOUR_HEIGHT * 2) * 30));
    const start = new Date(day);
    start.setHours(0, minutes, 0, 0);
    onSlotClick(start);
  }

  return (
    <div className="timegrid">
      <div className="timegrid-head" style={{ gridTemplateColumns: cols }}>
        <div />
        {days.map((d) => (
          <div key={d.toISOString()} className={`timegrid-dayhead ${sameDay(d, now) ? "today" : ""}`}>
            <span className="dow">{JS_DAY_SHORT[d.getDay()].toUpperCase()}</span>
            <span className="dom">{d.getDate()}</span>
          </div>
        ))}
      </div>

      <div className="timegrid-allday" style={{ gridTemplateColumns: cols }}>
        <div className="timegrid-allday-label muted small">all-day</div>
        {days.map((d) => (
          <div
            key={d.toISOString()}
            className="timegrid-allday-cell"
            onClick={(e) => e.target === e.currentTarget && onSlotClick(startOfDay(d), true)}
          >
            {items
              .filter((i) => (i.all_day || isPoint(i)) && onDay(i, d))
              .map((i) => (
                <button
                  key={i.id}
                  className={`chip chip-${itemClass(i)}`}
                  style={{ "--chip-color": itemColor(i) }}
                  onClick={() => onItemClick(i)}
                  title={isPoint(i) ? `Due ${formatTime(i.startDate)}` : i.title}
                >
                  {itemLabel(i)}
                </button>
              ))}
          </div>
        ))}
      </div>

      <div className="timegrid-scroll" ref={scrollRef}>
        <div className="timegrid-body" style={{ gridTemplateColumns: cols }}>
          <div className="timegrid-hours">
            {Array.from({ length: 24 }, (_, h) => (
              <div key={h} className="timegrid-hour" style={{ height: HOUR_HEIGHT }}>
                {h > 0 && formatMinutes(h * 60)}
              </div>
            ))}
          </div>
          {days.map((day) => {
            const dayStart = startOfDay(day);
            const dayEnd = addDays(dayStart, 1);
            const segments = items
              .filter((i) => !i.all_day && !isPoint(i) && onDay(i, day))
              .map((i) => {
                const segStart = i.startDate < dayStart ? dayStart : i.startDate;
                const segEnd = i.endDate > dayEnd ? dayEnd : i.endDate;
                return {
                  item: i,
                  start: minutesSinceMidnight(segStart),
                  end: segEnd >= dayEnd ? 24 * 60 : minutesSinceMidnight(segEnd),
                };
              });
            return (
              <div
                key={day.toISOString()}
                className="timegrid-day"
                style={{ height: 24 * HOUR_HEIGHT }}
                onClick={(e) => handleColumnClick(e, day)}
              >
                {layoutOverlaps(segments).map(({ item, start, end, col, cols: n }) => {
                  const short = end - start < 45;
                  return (
                    <button
                      key={item.id}
                      className={`tg-event tg-${itemClass(item).split(" ").join(" tg-")}`}
                      style={{
                        top: (start / 60) * HOUR_HEIGHT,
                        height: Math.max(((end - start) / 60) * HOUR_HEIGHT - 2, 16),
                        left: `calc(${(col / n) * 100}% + 1px)`,
                        width: `calc(${100 / n}% - 3px)`,
                        "--ev-color": itemColor(item),
                      }}
                      onClick={() => onItemClick(item)}
                    >
                      <span className="tg-event-title">{itemLabel(item)}{short && `, ${formatTime(item.startDate)}`}</span>
                      {!short && (
                        <span className="tg-event-time">
                          {formatTime(item.startDate)} – {formatTime(item.endDate)}
                          {item.location && ` · ${item.location}`}
                        </span>
                      )}
                    </button>
                  );
                })}
                {sameDay(day, now) && (
                  <div className="now-line" style={{ top: (minutesSinceMidnight(now) / 60) * HOUR_HEIGHT }} />
                )}
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}

// --- month -----------------------------------------------------------------

const MAX_PER_CELL = 3;

function MonthGrid({ cursor, start, items, onItemClick, onDayClick, onEmptyClick }) {
  const today = new Date();
  const days = Array.from({ length: 42 }, (_, i) => addDays(start, i));
  return (
    <div className="monthgrid">
      {JS_DAY_SHORT.map((d) => <div key={d} className="monthgrid-dow">{d.toUpperCase()}</div>)}
      {days.map((day) => {
        const dayItems = items
          .filter((i) => onDay(i, day))
          .sort((a, b) => (b.all_day - a.all_day) || (a.startDate - b.startDate));
        const shown = dayItems.slice(0, MAX_PER_CELL);
        const hidden = dayItems.length - shown.length;
        return (
          <div
            key={day.toISOString()}
            className={`monthgrid-cell ${day.getMonth() !== cursor.getMonth() ? "other-month" : ""}`}
            onClick={(e) => e.target === e.currentTarget && onEmptyClick(day)}
          >
            <button
              className={`monthgrid-date ${sameDay(day, today) ? "today" : ""}`}
              onClick={() => onDayClick(day)}
            >
              {day.getDate() === 1 ? `${MONTHS[day.getMonth()].slice(0, 3)} 1` : day.getDate()}
            </button>
            {shown.map((i) =>
              i.all_day ? (
                <button key={i.id} className={`chip chip-solid chip-${itemClass(i)}`} style={{ "--chip-color": itemColor(i) }} onClick={() => onItemClick(i)}>
                  {itemLabel(i)}
                </button>
              ) : (
                <button key={i.id} className="month-item" onClick={() => onItemClick(i)}>
                  <span className="dot" style={{ background: itemColor(i) }} />
                  <span className="month-item-time">{formatTime(i.startDate)}</span>
                  <span className="month-item-title">{itemLabel(i)}</span>
                </button>
              ),
            )}
            {hidden > 0 && (
              <button className="month-more" onClick={() => onDayClick(day)}>+{hidden} more</button>
            )}
          </div>
        );
      })}
    </div>
  );
}

// --- read-only popover for classes and assignments --------------------------

function ItemDetail({ item, onClose, onRespond }) {
  useEffect(() => {
    const onKey = (e) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  return (
    <div className="modal-backdrop" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <div className="modal item-detail" style={{ "--ev-color": itemColor(item) }}>
        <div className="item-detail-bar" />
        <h2>{item.title}</h2>
        {item.type === "shared" ? (
          <>
            <p>
              {item.all_day
                ? formatShortDate(item.startDate)
                : `${formatShortDate(item.startDate)} · ${formatTime(item.startDate)} – ${formatTime(item.endDate)}`}
              {item.recurring && " · repeats"}
            </p>
            {item.location && <p className="muted">{item.location}</p>}
            {item.description && <p>{item.description}</p>}
            <p className="small muted">
              Shared by {item.owner_name} ·{" "}
              {item.invitation_status === "accepted" ? "You're going" : "You haven't answered yet"}
            </p>
            <div className="modal-actions">
              {item.invitation_status !== "accepted" && (
                <button className="btn btn-sm btn-primary" onClick={() => onRespond(item.invitation_id, "accepted")}>Accept</button>
              )}
              <button className="btn btn-sm" onClick={() => onRespond(item.invitation_id, "declined")}>
                {item.invitation_status === "accepted" ? "No longer going" : "Decline"}
              </button>
              <span className="spacer" />
              <button className="btn btn-sm btn-ghost" onClick={onClose}>Close</button>
            </div>
          </>
        ) : item.type === "class" ? (
          <>
            <p>{formatShortDate(item.startDate)} · {formatTime(item.startDate)} – {formatTime(item.endDate)}</p>
            <p className="muted">{item.course_title} · Section {item.section_code}</p>
            <p className="muted">{item.instructor}{item.location && ` · ${item.location}`}</p>
            <p className="small muted">Repeats weekly for the term, from your committed schedule.</p>
            <div className="modal-actions">
              <Link className="btn btn-sm" to={`/courses/${item.course_id}`}>Course page</Link>
              <Link className="btn btn-sm" to={`/grades/${item.term_id}/${item.course_id}`}>Grades</Link>
              <span className="spacer" />
              <button className="btn btn-sm btn-ghost" onClick={onClose}>Close</button>
            </div>
          </>
        ) : (
          <>
            <p>{item.course_code} · {CATEGORY_LABEL[item.category]}</p>
            <p>Due {formatShortDate(item.startDate)} at {formatTime(item.startDate, { compact: false })}</p>
            <p className="muted">
              {item.score != null
                ? `Your score: ${item.score} / ${item.max_points}`
                : `Not graded yet · worth ${item.max_points} points`}
            </p>
            <div className="modal-actions">
              <Link className="btn btn-sm btn-primary" to={`/grades/${item.term_id}/${item.course_id}`}>
                {item.score != null ? "View in gradebook" : "Enter grade"}
              </Link>
              <span className="spacer" />
              <button className="btn btn-sm btn-ghost" onClick={onClose}>Close</button>
            </div>
          </>
        )}
      </div>
    </div>
  );
}

// --- invitations from other students ----------------------------------------

function InvitationsPanel({ invites, onRespond, onClose, onShow }) {
  useEffect(() => {
    const onKey = (e) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  return (
    <div className="modal-backdrop" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <div className="modal" role="dialog" aria-label="Invitations">
        <h2>Invitations</h2>
        {invites.length === 0 ? (
          <p className="muted">No invitations waiting. Events you accept stay on your calendar.</p>
        ) : (
          <ul className="invite-list">
            {invites.map((inv) => {
              const start = parseLocal(inv.start_at);
              return (
                <li key={inv.invitation_id}>
                  <div className="invite-swatch" style={{ background: EVENT_COLORS[inv.color] ?? EVENT_COLORS.blue }} />
                  <div className="invite-body">
                    <strong>{inv.title}</strong>
                    <div className="small">
                      {formatShortDate(start)}{!inv.all_day && ` · ${formatTime(start)}`}
                      {inv.recurrence_freq && " · repeats"}
                      {inv.location && ` · ${inv.location}`}
                    </div>
                    <div className="small muted">From {inv.owner_name} ({inv.owner_email})</div>
                    <div className="invite-actions">
                      <button className="btn btn-sm btn-primary" onClick={() => onRespond(inv.invitation_id, "accepted")}>Accept</button>
                      <button className="btn btn-sm" onClick={() => onRespond(inv.invitation_id, "declined")}>Decline</button>
                      <button className="btn btn-sm btn-ghost" onClick={() => onShow(inv)}>Show on calendar</button>
                    </div>
                  </div>
                </li>
              );
            })}
          </ul>
        )}
        <div className="modal-actions">
          <span className="spacer" />
          <button className="btn btn-ghost" onClick={onClose}>Close</button>
        </div>
      </div>
    </div>
  );
}
