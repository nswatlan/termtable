import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api";
import { courseColor } from "../lib/colors";

export const CATEGORY_NAMES = { homework: "Homework", quiz: "Quizzes", midterm: "Midterm", final: "Final" };

export function formatPercent(value) {
  return value == null ? "—" : `${value.toFixed(1)}%`;
}

export default function Grades() {
  const [classes, setClasses] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    api.get("/gradebook").then(setClasses).catch((e) => setError(e.message));
  }, []);

  if (error) return <div className="page"><div className="alert alert-error">{error}</div></div>;
  if (!classes) return <div className="page-loading">Loading…</div>;

  // Newest term first.
  const terms = [];
  for (const c of [...classes].reverse()) {
    let group = terms.find((t) => t.term_id === c.term_id);
    if (!group) terms.push((group = { term_id: c.term_id, term_name: c.term_name, classes: [] }));
    group.classes.push(c);
  }
  terms.forEach((t) => t.classes.sort((a, b) => a.course_code.localeCompare(b.course_code)));

  return (
    <div className="page">
      <h1>Grades</h1>
      <p className="muted">
        By default every class is weighted homework 20%, quizzes 10%, midterm 30%, final 40%. Open a
        class to use your syllabus's own weights, set a target grade, or try what-if scores.
      </p>

      {classes.length === 0 && (
        <div className="empty">
          <h2>No classes yet</h2>
          <p className="muted">
            Once you add a schedule to your calendar from the planner, its classes show up here.
          </p>
          <Link className="btn btn-primary" to="/planner">Go to the planner</Link>
        </div>
      )}

      {terms.map((term) => (
        <section key={term.term_id}>
          <h2 className="term-heading">{term.term_name}</h2>
          <div className="grade-cards">
            {term.classes.map((c) => (
              <Link
                key={c.course_id}
                to={`/grades/${c.term_id}/${c.course_id}`}
                className="grade-card"
                style={{ "--accent": courseColor(c.course_id) }}
              >
                <div className="grade-card-top">
                  <div>
                    <div className="eyebrow">{c.course_code} · Sec {c.section_code}</div>
                    <div className="grade-card-title">{c.title}</div>
                  </div>
                  <div className="grade-big">
                    <div>{c.grade.letter ?? "—"}</div>
                    <div className="small muted">{formatPercent(c.grade.overall)}</div>
                  </div>
                </div>
                <div className="small muted">
                  {c.mode === "custom" && "Your weights · "}
                  {c.graded_count} of {c.assignment_count} graded
                  {c.grade.overall != null && c.grade.counted_weight < 1 &&
                    ` · based on ${Math.round(c.grade.counted_weight * 100)}% of the course weight`}
                </div>
                {c.target && (
                  <div className="small">
                    Target {c.target.target}%:{" "}
                    {{
                      possible: `need ${c.target.required.toFixed(1)}% on the rest`,
                      secured: "secured",
                      out_of_reach: "out of reach",
                      no_remaining: c.grade.overall >= c.target.target ? "reached" : "missed",
                    }[c.target.status]}
                  </div>
                )}
                <div className="cat-bar" aria-hidden>
                  {c.mode === "custom" ? (
                    <>
                      <span className="cat-bar-seg counted" style={{ flexGrow: c.grade.counted_weight }} />
                      <span className="cat-bar-seg" style={{ flexGrow: 1 - c.grade.counted_weight }} />
                    </>
                  ) : Object.entries(c.grade.categories).map(([cat, info]) => (
                    <span
                      key={cat}
                      className={`cat-bar-seg ${info.counted ? "counted" : ""}`}
                      style={{ flexGrow: info.weight }}
                      title={`${CATEGORY_NAMES[cat]}: ${info.counted ? formatPercent(info.average) : "not graded yet"}`}
                    />
                  ))}
                </div>
              </Link>
            ))}
          </div>
        </section>
      ))}
    </div>
  );
}
