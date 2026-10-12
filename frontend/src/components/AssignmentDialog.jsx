import { useEffect, useState } from "react";
import { api } from "../api";
import { useDialog } from "./Dialog";
import { parseLocal, toISODate, toISOTime } from "../lib/dates";

/**
 * Create / edit / complete / delete an assignment the student added themselves.
 * task:     the backend row to edit, or null to create
 * defaults: { due: Date } for a new assignment
 * classes:  [{course_id, term_id, course_code, title, term_name}] it can be linked to
 */
export default function AssignmentDialog({ task, defaults, classes, onClose, onSaved }) {
  const dialog = useDialog();
  const due = task ? parseLocal(task.due_at) : defaults?.due ?? new Date();
  const [form, setForm] = useState({
    title: task?.title ?? "",
    date: toISODate(due),
    time: task ? toISOTime(due) : "23:59",
    course: task?.course_id ? `${task.term_id}:${task.course_id}` : "",
    notes: task?.notes ?? "",
  });
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    const onKey = (e) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  const set = (key) => (e) => setForm((f) => ({ ...f, [key]: e.target.value }));

  async function run(action) {
    setBusy(true);
    setError(null);
    try {
      await action();
      onSaved();
    } catch (err) {
      setError(err.message);
      setBusy(false);
    }
  }

  function save(e) {
    e.preventDefault();
    const [termId, courseId] = form.course ? form.course.split(":").map(Number) : [null, null];
    const payload = {
      title: form.title,
      due_at: `${form.date}T${form.time}:00`,
      course_id: courseId,
      term_id: termId,
      notes: form.notes,
    };
    run(() => (task ? api.patch(`/my-assignments/${task.id}`, payload) : api.post("/my-assignments", payload)));
  }

  async function remove() {
    const ok = await dialog.confirm({ title: `Delete "${task.title}"?`, confirmLabel: "Delete", danger: true });
    if (ok) run(() => api.del(`/my-assignments/${task.id}`));
  }

  return (
    <div className="modal-backdrop" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <form className="modal event-dialog" onSubmit={save}>
        <div className="eyebrow">{task ? "Your assignment" : "New assignment"}</div>
        <input
          className="event-title-input"
          placeholder="What's due?"
          value={form.title}
          onChange={set("title")}
          autoFocus
          required
          maxLength={200}
        />
        <div className="event-row">
          <span className="muted">Due</span>
          <input type="date" value={form.date} onChange={set("date")} required />
          <input type="time" value={form.time} onChange={set("time")} required />
        </div>
        <select value={form.course} onChange={set("course")} aria-label="Class">
          <option value="">No class (personal)</option>
          {classes.map((c) => (
            <option key={`${c.term_id}:${c.course_id}`} value={`${c.term_id}:${c.course_id}`}>
              {c.course_code}: {c.title} ({c.term_name})
            </option>
          ))}
        </select>
        <textarea placeholder="Notes" rows={2} value={form.notes} onChange={set("notes")} maxLength={5000} />

        {error && <div className="alert alert-error">{error}</div>}

        <div className="modal-actions">
          {task && (
            <>
              <button type="button" className="btn btn-ghost btn-danger" onClick={remove} disabled={busy}>Delete</button>
              <button
                type="button"
                className="btn"
                disabled={busy}
                onClick={() => run(() => api.patch(`/my-assignments/${task.id}`, { completed: !task.completed }))}
              >
                {task.completed ? "Mark not done" : "Mark complete"}
              </button>
            </>
          )}
          <span className="spacer" />
          <button type="button" className="btn btn-ghost" onClick={onClose}>Cancel</button>
          <button className="btn btn-primary" disabled={busy}>Save</button>
        </div>
      </form>
    </div>
  );
}
