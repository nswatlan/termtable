import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api";
import AssignmentDialog from "../components/AssignmentDialog";
import { courseColor } from "../lib/colors";
import { formatDue, parseLocal, startOfDay } from "../lib/dates";
import { CATEGORY_NAMES } from "./Grades";

// One to-do list: assignments the student added (which they can complete or
// delete) and the course assignments from their committed schedules.
export default function Assignments() {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const [dialog, setDialog] = useState(null); // { task } or {}
  const [showDone, setShowDone] = useState(false);

  const load = useCallback(() => {
    api.get("/homework").then(setData).catch((e) => setError(e.message));
  }, []);
  useEffect(load, [load]);

  async function toggle(task) {
    try {
      await api.patch(`/my-assignments/${task.id}`, { completed: !task.completed });
      load();
    } catch (e) {
      setError(e.message);
    }
  }

  if (!data) {
    return <div className="page">{error ? <div className="alert alert-error">{error}</div> : <div className="page-loading">Loading…</div>}</div>;
  }

  const items = [
    ...data.my_assignments.map((t) => ({ kind: "mine", key: `m${t.id}`, due: parseLocal(t.due_at), done: t.completed, t })),
    ...data.course_assignments.map((a) => ({ kind: "course", key: `c${a.id}`, due: parseLocal(a.due_at), done: a.score != null, a })),
  ].sort((x, y) => x.due - y.due);
  const visible = items.filter((i) => showDone || !i.done);

  const today = startOfDay(new Date());
  const groups = [
    ["Overdue", (d) => d < today],
    ["This week", (d) => d >= today && d < new Date(today.getTime() + 7 * 864e5)],
    ["Later", (d) => d >= new Date(today.getTime() + 7 * 864e5)],
  ];

  return (
    <div className="page">
      <div className="page-head">
        <div>
          <h1>Assignments</h1>
          <p className="muted">
            Add your own homework and check it off when it's done. Course assignments come from your
            committed schedules and count as done once they're graded.
          </p>
        </div>
        <button className="btn btn-primary" onClick={() => setDialog({})}>+ Add assignment</button>
      </div>
      <label className="check">
        <input type="checkbox" checked={showDone} onChange={(e) => setShowDone(e.target.checked)} />
        Show completed and graded
      </label>
      {error && <div className="alert alert-error">{error}</div>}

      {visible.length === 0 && <p className="muted" style={{ marginTop: 16 }}>Nothing due. Nice.</p>}

      {groups.map(([label, test]) => {
        const rows = visible.filter((i) => test(i.due));
        if (!rows.length) return null;
        return (
          <section key={label} className="card">
            <h2>{label}</h2>
            <ul className="todo-list">
              {rows.map((i) =>
                i.kind === "mine" ? (
                  <li key={i.key} className={i.done ? "done" : ""}>
                    <input
                      type="checkbox"
                      checked={i.done}
                      onChange={() => toggle(i.t)}
                      aria-label={`Mark ${i.t.title} ${i.done ? "not done" : "complete"}`}
                    />
                    <button className="todo-title link-button" onClick={() => setDialog({ task: i.t })}>
                      {i.t.title}
                    </button>
                    {i.t.course_code && (
                      <span className="todo-course" style={{ color: courseColor(i.t.course_id) }}>{i.t.course_code}</span>
                    )}
                    <span className="todo-tag">Yours</span>
                    <span className="todo-due muted">{formatDue(i.t.due_at)}</span>
                  </li>
                ) : (
                  <li key={i.key} className={i.done ? "done" : ""}>
                    <span className="todo-mark" aria-hidden>{i.done ? "✓" : "•"}</span>
                    <span className="todo-title">{i.a.title}</span>
                    <span className="todo-course" style={{ color: courseColor(i.a.course_id) }}>{i.a.course_code}</span>
                    <span className="todo-tag">{CATEGORY_NAMES[i.a.category]}</span>
                    <span className="todo-due muted">
                      {formatDue(i.a.due_at)} ·{" "}
                      <Link to={`/grades/${i.a.term_id}/${i.a.course_id}`}>
                        {i.done ? `${i.a.score} / ${i.a.max_points}` : "Enter grade"}
                      </Link>
                    </span>
                  </li>
                ),
              )}
            </ul>
          </section>
        );
      })}

      {dialog && (
        <AssignmentDialog
          task={dialog.task ?? null}
          classes={data.classes}
          onClose={() => setDialog(null)}
          onSaved={() => { setDialog(null); load(); }}
        />
      )}
    </div>
  );
}
