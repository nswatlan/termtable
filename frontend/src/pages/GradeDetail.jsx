import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api } from "../api";
import { formatDue } from "../lib/dates";
import { CATEGORY_NAMES, formatPercent } from "./Grades";

export default function GradeDetail() {
  const { termId, courseId } = useParams();
  const base = `/gradebook/${termId}/${courseId}`;
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  // What-if mode: hypothetical scores ({assignment id: string}) and extra
  // made-up assignments. Nothing here is saved.
  const [whatIf, setWhatIf] = useState(false);
  const [hyp, setHyp] = useState({});
  const [extra, setExtra] = useState([]);
  const [projection, setProjection] = useState(null);

  useEffect(() => {
    api.get(base).then(setData).catch((e) => setError(e.message));
  }, [base]);

  // Recompute the projected grade whenever the hypotheticals change.
  useEffect(() => {
    if (!whatIf || !data) return setProjection(null);
    const handle = setTimeout(() => {
      api.post(`${base}/what-if`, {
        scores: hyp,
        extra: extra.filter((x) => x.max_points !== ""),
        target_grade: data.target_grade,
      }).then((p) => { setProjection(p); setError(null); }).catch((e) => setError(e.message));
    }, 250);
    return () => clearTimeout(handle);
  }, [whatIf, hyp, extra, data, base]);

  async function call(promise) {
    setError(null);
    try {
      setData(await promise);
    } catch (e) {
      setError(e.message);
    }
  }

  async function saveScore(assignment, raw) {
    const value = raw.trim();
    if (whatIf) {
      setHyp((h) => ({ ...h, [assignment.id]: value === "" ? null : value }));
      return;
    }
    if (value === "") {
      if (assignment.score != null) call(api.del(`/grades/${assignment.id}`));
      return;
    }
    const score = Number(value);
    if (!Number.isFinite(score) || score < 0) return setError("Scores must be a number of 0 or more.");
    if (score !== assignment.score) call(api.put(`/grades/${assignment.id}`, { score }));
  }

  function saveWeight(assignment, raw) {
    const value = raw.trim();
    if (value === "") return call(api.put(`${base}/weights`, { weights: { [assignment.id]: null } }));
    const weight = Number(value);
    if (!Number.isFinite(weight) || weight < 0 || weight > 100) return setError("Weights must be between 0 and 100.");
    if (weight !== assignment.weight) call(api.put(`${base}/weights`, { weights: { [assignment.id]: weight } }));
  }

  function exitWhatIf() {
    setWhatIf(false);
    setHyp({});
    setExtra([]);
  }

  if (!data) {
    return (
      <div className="page">
        {error ? <div className="alert alert-error">{error}</div> : <div className="page-loading">Loading…</div>}
      </div>
    );
  }

  const custom = data.mode === "custom";
  const grade = projection?.grade ?? data.grade;
  const target = projection ? projection.target : data.target;
  const now = new Date();
  const totalWeight = data.assignments.reduce((sum, a) => sum + a.weight, 0);
  const hasCustomWeights = data.assignments.some((a) => a.has_custom_weight);

  return (
    <div className="page">
      <Link to="/grades" className="small">← All classes</Link>
      <header className="grade-header">
        <div>
          <div className="eyebrow">{data.course_code} · Section {data.section_code} · {data.term_name}</div>
          <h1>{data.title}</h1>
          <div className="muted">{data.instructor}</div>
        </div>
        <div className={`grade-hero ${projection ? "grade-hero-whatif" : ""}`}>
          {projection && <div className="eyebrow">Projected</div>}
          <div className="grade-hero-letter">{grade.letter ?? "—"}</div>
          <div className="grade-hero-pct">{formatPercent(grade.overall)}</div>
          <div className="small muted">
            {grade.overall == null
              ? "Enter a score to see your grade"
              : grade.counted_weight < 1
                ? `Based on ${Math.round(grade.counted_weight * 100)}% of the course weight so far`
                : "Everything counted"}
          </div>
          {projection && <div className="small">Actual: {formatPercent(data.grade.overall)}</div>}
        </div>
      </header>

      {error && <div className="alert alert-error">{error}</div>}

      <div className="grade-tools">
        <section className="card">
          <h2>How this class is graded</h2>
          <div className="segmented">
            <button className={!custom ? "active" : ""} onClick={() => call(api.put(`${base}/settings`, { mode: "category" }))}>
              Category weights
            </button>
            <button className={custom ? "active" : ""} onClick={() => call(api.put(`${base}/settings`, { mode: "custom" }))}>
              My own weights
            </button>
          </div>
          <p className="small muted" style={{ marginTop: 8 }}>
            {custom
              ? "Give each assignment the weight from your syllabus. Weights start as the category split; clear a box to reset it."
              : "Homework 20%, quizzes 10%, midterm 30%, final 40%. Switch to your own weights if your syllabus differs."}
          </p>
          {custom && (
            <div className="weight-total">
              <span className={Math.abs(totalWeight - 100) > 0.05 ? "warn-text" : ""}>
                Weights total {totalWeight.toFixed(1)}%
                {Math.abs(totalWeight - 100) > 0.05 && " (grades are scaled to the total)"}
              </span>
              {hasCustomWeights && (
                <button className="btn btn-sm btn-ghost" onClick={() => call(api.del(`${base}/weights`))}>Reset all weights</button>
              )}
            </div>
          )}
        </section>

        <TargetCard
          target={target}
          value={data.target_grade}
          projected={!!projection}
          onSave={(t) => call(api.put(`${base}/settings`, { target_grade: t }))}
        />
      </div>

      <section className={`card whatif-bar ${whatIf ? "on" : ""}`}>
        <label className="check">
          <input type="checkbox" checked={whatIf} onChange={(e) => (e.target.checked ? setWhatIf(true) : exitWhatIf())} />
          <strong>What-if mode</strong>
        </label>
        <span className="small muted">
          {whatIf
            ? "Type scores you might get, or add made-up assignments, to see your projected grade. Nothing is saved."
            : "Try hypothetical scores without changing your real grades."}
        </span>
        {whatIf && <button className="btn btn-sm" onClick={exitWhatIf}>Done</button>}
      </section>

      {!custom && (
        <section className="card">
          <h2>Breakdown</h2>
          <table className="table">
            <thead>
              <tr><th>Category</th><th>Weight</th><th>Graded</th><th>Average</th><th>Counts toward grade</th></tr>
            </thead>
            <tbody>
              {data.categories.map((cat) => {
                const info = grade.categories[cat];
                return (
                  <tr key={cat} className={info.counted ? "" : "muted"}>
                    <td>{CATEGORY_NAMES[cat]}</td>
                    <td>{Math.round(info.weight * 100)}%</td>
                    <td>{info.graded} / {info.total}</td>
                    <td>{formatPercent(info.average)}</td>
                    <td>
                      {info.counted
                        ? `${((info.weight / grade.counted_weight) * 100).toFixed(1)}% of current grade`
                        : "Not yet (nothing graded)"}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </section>
      )}

      {data.categories.map((cat) => {
        const rows = data.assignments.filter((a) => a.category === cat);
        if (!rows.length) return null;
        return (
          <section key={cat} className="card">
            <h2>{CATEGORY_NAMES[cat]}</h2>
            <table className="table assignment-table">
              <thead>
                <tr><th>Assignment</th><th>Due</th>{custom && <th>Weight</th>}<th>Score</th><th>%</th></tr>
              </thead>
              <tbody>
                {rows.map((a) => {
                  const hypothetical = whatIf && a.id in hyp;
                  const shown = hypothetical ? hyp[a.id] : a.score;
                  return (
                    <tr key={a.id} className={a.score == null && new Date(a.due_at) < now ? "row-pending" : ""}>
                      <td>{a.title}</td>
                      <td className="muted">{formatDue(a.due_at)}</td>
                      {custom && (
                        <td>
                          <NumberInput
                            value={a.has_custom_weight ? a.weight : ""}
                            placeholder={a.default_weight.toFixed(2)}
                            label={`Weight for ${a.title}`}
                            onSave={(v) => saveWeight(a, v)}
                          />
                          <span className="muted">%</span>
                        </td>
                      )}
                      <td>
                        <NumberInput
                          value={shown ?? ""}
                          className={hypothetical ? "hypothetical" : ""}
                          placeholder={whatIf ? "what if?" : "—"}
                          label={`Score for ${a.title}`}
                          onSave={(v) => saveScore(a, v)}
                        />
                        <span className="muted"> / {a.max_points}</span>
                      </td>
                      <td>
                        {shown == null || shown === ""
                          ? <span className="muted">—</span>
                          : formatPercent((Number(shown) / a.max_points) * 100)}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </section>
        );
      })}

      {whatIf && <ExtraAssignments extra={extra} setExtra={setExtra} custom={custom} categories={data.categories} />}
    </div>
  );
}

function TargetCard({ target, value, projected, onSave }) {
  const [draft, setDraft] = useState(value ?? "");
  useEffect(() => setDraft(value ?? ""), [value]);

  function save() {
    const v = String(draft).trim();
    if (v === "") return value != null && onSave(null);
    const n = Number(v);
    if (Number.isFinite(n) && n !== value) onSave(n);
  }

  let message = "Set a target to see what you need on the rest of the class.";
  if (target) {
    const n = target.remaining;
    const rest = `the remaining ${n} assignment${n === 1 ? "" : "s"}`;
    message = {
      possible: `You need an average of ${target.required.toFixed(1)}% on ${rest} to finish with ${target.target}%.`,
      secured: `You'll finish at ${target.target}% or higher even with 0% on ${rest}.`,
      out_of_reach: `Even 100% on ${rest} gets you ${target.highest?.toFixed(1)}%, short of ${target.target}%. Only extra credit would close the gap.`,
      no_remaining: `Everything is graded. Your final grade is ${formatPercent(target.highest)}.`,
    }[target.status];
  }

  return (
    <section className="card">
      <h2>Target grade</h2>
      <div className="event-row">
        <span>I want to finish with</span>
        <input
          className="score-input"
          inputMode="decimal"
          placeholder="e.g. 90"
          value={draft}
          aria-label="Target grade percent"
          onChange={(e) => setDraft(e.target.value)}
          onBlur={save}
          onKeyDown={(e) => e.key === "Enter" && e.currentTarget.blur()}
        />
        <span>%</span>
      </div>
      <p className={`target-message ${target ? `target-${target.status}` : "muted small"}`}>
        {projected && target && <strong>With your what-if scores: </strong>}
        {message}
      </p>
    </section>
  );
}

function ExtraAssignments({ extra, setExtra, custom, categories }) {
  const update = (i, key, value) => setExtra((list) => list.map((x, j) => (j === i ? { ...x, [key]: value } : x)));
  return (
    <section className="card">
      <div className="card-head">
        <h2>Hypothetical assignments</h2>
        <button
          className="btn btn-sm"
          onClick={() => setExtra((list) => [...list, { title: "", category: "homework", max_points: "100", score: "", weight: "" }])}
        >
          + Add one
        </button>
      </div>
      {extra.length === 0 ? (
        <p className="muted small">Add an assignment that isn't in the gradebook (extra credit, a project) to see how it would count.</p>
      ) : (
        <table className="table assignment-table">
          <thead>
            <tr><th>Name</th><th>Category</th>{custom && <th>Weight</th>}<th>Score</th><th>Out of</th><th /></tr>
          </thead>
          <tbody>
            {extra.map((x, i) => (
              <tr key={i}>
                <td><input value={x.title} placeholder="Extra credit" onChange={(e) => update(i, "title", e.target.value)} aria-label="Name" /></td>
                <td>
                  <select value={x.category} onChange={(e) => update(i, "category", e.target.value)} aria-label="Category">
                    {categories.map((c) => <option key={c} value={c}>{CATEGORY_NAMES[c]}</option>)}
                  </select>
                </td>
                {custom && (
                  <td><input className="score-input" inputMode="decimal" value={x.weight} placeholder="%" onChange={(e) => update(i, "weight", e.target.value)} aria-label="Weight" /></td>
                )}
                <td><input className="score-input" inputMode="decimal" value={x.score} onChange={(e) => update(i, "score", e.target.value)} aria-label="Score" /></td>
                <td><input className="score-input" inputMode="decimal" value={x.max_points} onChange={(e) => update(i, "max_points", e.target.value)} aria-label="Out of" /></td>
                <td><button className="btn btn-sm btn-ghost" onClick={() => setExtra((list) => list.filter((_, j) => j !== i))}>Remove</button></td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      {custom && extra.some((x) => !x.weight) && (
        <p className="small muted">In your-own-weights mode, a hypothetical assignment needs a weight to count.</p>
      )}
    </section>
  );
}

function NumberInput({ value, onSave, label, placeholder, className = "" }) {
  const [draft, setDraft] = useState(value);
  useEffect(() => setDraft(value), [value]);
  return (
    <input
      className={`score-input ${className}`}
      inputMode="decimal"
      placeholder={placeholder}
      value={draft}
      aria-label={label}
      onChange={(e) => setDraft(e.target.value)}
      onBlur={() => onSave(String(draft))}
      onKeyDown={(e) => e.key === "Enter" && e.currentTarget.blur()}
    />
  );
}
