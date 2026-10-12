import { useEffect, useState } from "react";
import { api } from "../api";
import { useDialog } from "./Dialog";
import { EVENT_COLORS } from "../lib/colors";
import { JS_DAY_CODES, addDays, parseLocal, toISODate, toISODateTime, toISOTime } from "../lib/dates";

const WEEKDAY_BUTTONS = [
  ["SU", "S"], ["MO", "M"], ["TU", "T"], ["WE", "W"], ["TH", "T"], ["FR", "F"], ["SA", "S"],
];

function formFromEvent(event, defaults) {
  if (event) {
    const start = parseLocal(event.start_at);
    const end = parseLocal(event.end_at);
    const shownEnd = event.all_day ? addDays(end, -1) : end;
    return {
      title: event.title,
      all_day: event.all_day,
      startDate: toISODate(start),
      startTime: toISOTime(start),
      endDate: toISODate(shownEnd),
      endTime: toISOTime(end),
      location: event.location ?? "",
      description: event.description ?? "",
      color: event.color,
      freq: event.recurrence_freq ?? "",
      interval: event.recurrence_interval ?? 1,
      days: event.recurrence_days ? event.recurrence_days.split(",") : [JS_DAY_CODES[start.getDay()]],
      until: event.recurrence_until ?? "",
    };
  }
  const start = defaults.start;
  const end = defaults.allDay ? start : new Date(start.getTime() + 60 * 60 * 1000);
  return {
    title: "",
    all_day: !!defaults.allDay,
    startDate: toISODate(start),
    startTime: defaults.allDay ? "09:00" : toISOTime(start),
    endDate: toISODate(end),
    endTime: defaults.allDay ? "10:00" : toISOTime(end),
    location: "",
    description: "",
    color: "blue",
    freq: "",
    interval: 1,
    days: [JS_DAY_CODES[start.getDay()]],
    until: "",
  };
}

/**
 * Create / edit / delete a personal event. Edits and deletes of a repeating
 * event apply to the whole series.
 * event:    the backend event row to edit, or null to create
 * defaults: { start: Date, allDay: bool } for a new event
 */
export default function EventDialog({ event, defaults, onClose, onSaved }) {
  const dialog = useDialog();
  const [form, setForm] = useState(() => formFromEvent(event, defaults));
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);
  const [newGuests, setNewGuests] = useState([]); // emails to invite once a new event is saved

  useEffect(() => {
    const onKey = (e) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  const set = (key, value) => setForm((f) => ({ ...f, [key]: value }));

  // Moving the start keeps the event's duration, like Google Calendar.
  function setStart(key, value) {
    setForm((f) => {
      const oldStart = parseLocal(`${f.startDate}T${f.startTime}`);
      const oldEnd = parseLocal(`${f.endDate}T${f.endTime}`);
      const next = { ...f, [key]: value };
      if (!next.startDate || !next.startTime) return next;
      const newStart = parseLocal(`${next.startDate}T${next.startTime}`);
      const newEnd = new Date(newStart.getTime() + Math.max(oldEnd - oldStart, 0));
      next.endDate = toISODate(newEnd);
      next.endTime = toISOTime(newEnd);
      if (key === "startDate" && f.days.length === 1 && f.days[0] === JS_DAY_CODES[oldStart.getDay()]) {
        next.days = [JS_DAY_CODES[newStart.getDay()]];
      }
      return next;
    });
  }

  function toggleDay(code) {
    setForm((f) => {
      const startCode = JS_DAY_CODES[parseLocal(f.startDate).getDay()];
      if (code === startCode) return f; // the start day always repeats
      const days = f.days.includes(code) ? f.days.filter((d) => d !== code) : [...f.days, code];
      return { ...f, days };
    });
  }

  async function save(e) {
    e.preventDefault();
    setError(null);
    let start_at, end_at;
    if (form.all_day) {
      start_at = `${form.startDate}T00:00:00`;
      end_at = toISODateTime(addDays(parseLocal(form.endDate), 1));
    } else {
      start_at = `${form.startDate}T${form.startTime}:00`;
      end_at = `${form.endDate}T${form.endTime}:00`;
    }
    const payload = {
      title: form.title,
      all_day: form.all_day,
      start_at,
      end_at,
      location: form.location,
      description: form.description,
      color: form.color,
      recurrence_freq: form.freq || null,
      recurrence_interval: Number(form.interval) || 1,
      recurrence_days: form.freq === "WEEKLY" ? form.days.join(",") : null,
      recurrence_until: form.freq && form.until ? form.until : null,
    };
    setBusy(true);
    try {
      if (event) {
        await api.put(`/events/${event.id}`, payload);
      } else {
        const created = await api.post("/events", payload);
        const failed = [];
        for (const guest of newGuests) {
          try {
            await api.post(`/events/${created.id}/invitations`, { email: guest.email });
          } catch (err) {
            failed.push(`${guest.email}: ${err.message}`);
          }
        }
        if (failed.length) {
          await dialog.confirm({ title: "Event saved, but some invitations failed", message: failed.join(" · "), confirmLabel: "OK" });
        }
      }
      onSaved();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  async function remove() {
    const ok = await dialog.confirm({
      title: `Delete "${event.title}"?`,
      message: [
        event.recurrence_freq && "This deletes every occurrence of this repeating event.",
        "Anyone you invited will no longer see it.",
      ].filter(Boolean).join(" "),
      confirmLabel: "Delete",
      danger: true,
    });
    if (!ok) return;
    setBusy(true);
    try {
      await api.del(`/events/${event.id}`);
      onSaved();
    } catch (err) {
      setError(err.message);
      setBusy(false);
    }
  }

  const startCode = form.startDate ? JS_DAY_CODES[parseLocal(form.startDate).getDay()] : null;
  const unit = { DAILY: "day", WEEKLY: "week", MONTHLY: "month" }[form.freq];

  return (
    <div className="modal-backdrop" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <form className="modal event-dialog" onSubmit={save}>
        <input
          className="event-title-input"
          placeholder="Add title"
          value={form.title}
          onChange={(e) => set("title", e.target.value)}
          autoFocus
          required
          maxLength={200}
        />

        <div className="event-row">
          <label className="check">
            <input type="checkbox" checked={form.all_day} onChange={(e) => set("all_day", e.target.checked)} />
            All day
          </label>
        </div>

        <div className="event-row event-times">
          <input type="date" value={form.startDate} onChange={(e) => setStart("startDate", e.target.value)} required />
          {!form.all_day && (
            <input type="time" value={form.startTime} onChange={(e) => setStart("startTime", e.target.value)} required />
          )}
          <span className="muted">to</span>
          {!form.all_day && (
            <input type="time" value={form.endTime} onChange={(e) => set("endTime", e.target.value)} required />
          )}
          <input type="date" value={form.endDate} min={form.startDate} onChange={(e) => set("endDate", e.target.value)} required />
        </div>

        <div className="event-row">
          <select value={form.freq} onChange={(e) => set("freq", e.target.value)} aria-label="Repeat">
            <option value="">Does not repeat</option>
            <option value="DAILY">Daily</option>
            <option value="WEEKLY">Weekly</option>
            <option value="MONTHLY">Monthly</option>
          </select>
          {form.freq && (
            <>
              <span className="muted">every</span>
              <input
                type="number"
                min={1}
                max={99}
                className="input-narrow"
                value={form.interval}
                onChange={(e) => set("interval", e.target.value)}
                aria-label="Repeat interval"
              />
              <span className="muted">{unit}{Number(form.interval) > 1 ? "s" : ""}</span>
            </>
          )}
        </div>

        {form.freq === "WEEKLY" && (
          <div className="event-row weekday-picker" aria-label="Repeat on">
            {WEEKDAY_BUTTONS.map(([code, letter]) => (
              <button
                key={code}
                type="button"
                className={form.days.includes(code) || code === startCode ? "on" : ""}
                onClick={() => toggleDay(code)}
                aria-pressed={form.days.includes(code) || code === startCode}
                title={code}
              >
                {letter}
              </button>
            ))}
          </div>
        )}

        {form.freq && (
          <div className="event-row">
            <span className="muted">Ends</span>
            <select
              value={form.until ? "on" : "never"}
              onChange={(e) => set("until", e.target.value === "on" ? form.startDate : "")}
              aria-label="Repeat ends"
            >
              <option value="never">Never</option>
              <option value="on">On date</option>
            </select>
            {form.until && (
              <input type="date" value={form.until} min={form.startDate} onChange={(e) => set("until", e.target.value)} />
            )}
          </div>
        )}

        <input placeholder="Add location" value={form.location} onChange={(e) => set("location", e.target.value)} maxLength={200} />
        <textarea placeholder="Add description" rows={2} value={form.description} onChange={(e) => set("description", e.target.value)} />

        <div className="event-row color-picker" role="radiogroup" aria-label="Color">
          {Object.entries(EVENT_COLORS).map(([name, hex]) => (
            <button
              key={name}
              type="button"
              role="radio"
              aria-checked={form.color === name}
              aria-label={name}
              className={form.color === name ? "on" : ""}
              style={{ background: hex }}
              onClick={() => set("color", name)}
            />
          ))}
        </div>

        <Guests eventId={event?.id} pending={newGuests} setPending={setNewGuests} />

        {error && <div className="alert alert-error">{error}</div>}

        <div className="modal-actions">
          {event && (
            <button type="button" className="btn btn-ghost btn-danger" onClick={remove} disabled={busy}>Delete</button>
          )}
          <span className="spacer" />
          <button type="button" className="btn btn-ghost" onClick={onClose}>Cancel</button>
          <button className="btn btn-primary" disabled={busy}>Save</button>
        </div>
        {event?.recurrence_freq && (
          <p className="muted small">Changes apply to every occurrence of this repeating event.</p>
        )}
      </form>
    </div>
  );
}

const STATUS_LABEL = { accepted: "Going", pending: "Invited", declined: "Declined" };

/**
 * Invite other students by the email they signed up with. For a saved event
 * invitations are sent right away; for a new one they're collected in
 * `pending` and sent when the event is saved.
 */
function Guests({ eventId, pending, setPending }) {
  const [guests, setGuests] = useState(eventId ? null : []);
  const [email, setEmail] = useState("");
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (eventId) api.get(`/events/${eventId}/invitations`).then(setGuests).catch((e) => setError(e.message));
  }, [eventId]);

  async function add(e) {
    e.preventDefault();
    const value = email.trim().toLowerCase();
    if (!value) return;
    setError(null);
    setBusy(true);
    try {
      if (eventId) {
        setGuests(await api.post(`/events/${eventId}/invitations`, { email: value }));
      } else {
        if (pending.some((g) => g.email === value)) throw new Error("Already on the list");
        const user = await api.get(`/users/lookup?email=${encodeURIComponent(value)}`);
        setPending([...pending, user]);
      }
      setEmail("");
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  async function remove(guest) {
    setError(null);
    try {
      if (eventId) setGuests(await api.del(`/events/${eventId}/invitations/${guest.id}`));
      else setPending(pending.filter((g) => g.email !== guest.email));
    } catch (err) {
      setError(err.message);
    }
  }

  const list = eventId ? guests ?? [] : pending.map((g) => ({ ...g, status: "new" }));

  return (
    <div className="guests">
      <div className="guests-head">
        <span className="eyebrow">Invite people</span>
        {list.length > 0 && (
          <span className="muted small">
            {eventId
              ? `${list.filter((g) => g.status === "accepted").length} going · ${list.filter((g) => g.status === "pending").length} invited`
              : `${list.length} will be invited when you save`}
          </span>
        )}
      </div>
      <div className="event-row">
        <input
          type="email"
          placeholder="Classmate's email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && add(e)}
          className="guests-input"
          aria-label="Invite by email"
        />
        <button type="button" className="btn btn-sm" onClick={add} disabled={busy || !email.trim()}>Invite</button>
      </div>
      {error && <div className="alert alert-error small">{error}</div>}
      {list.length > 0 && (
        <ul className="guest-list">
          {list.map((g) => (
            <li key={g.email}>
              <span className="guest-name">{g.display_name}</span>
              <span className="muted small">{g.email}</span>
              {g.status !== "new" && <span className={`status-pill status-${g.status}`}>{STATUS_LABEL[g.status]}</span>}
              <button type="button" className="btn btn-ghost btn-sm" onClick={() => remove(g)} aria-label={`Remove ${g.display_name}`}>
                Remove
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
