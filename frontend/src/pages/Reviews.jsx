import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { api, qs } from "../api";
import { Stars } from "../components/Stars";
import { courseColor } from "../lib/colors";
import { parseLocal } from "../lib/dates";
import { courseCode } from "../lib/sections";
import { SortSelect } from "./CourseDetail";

// Search reviews across every course by professor, department and course.
export default function Reviews() {
  const [params, setParams] = useSearchParams();
  const instructor = params.get("professor") ?? "";
  const department = params.get("department") ?? "";
  const course = params.get("course") ?? "";
  const sort = params.get("sort") ?? "newest";
  const [departments, setDepartments] = useState([]);
  const [professors, setProfessors] = useState([]);
  const [reviews, setReviews] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => { api.get("/departments").then(setDepartments); }, []);
  useEffect(() => { api.get(`/instructors${qs({ department })}`).then(setProfessors); }, [department]);
  useEffect(() => {
    const handle = setTimeout(() => {
      api.get(`/reviews${qs({ instructor, department, course, sort })}`)
        .then((r) => { setReviews(r); setError(null); })
        .catch((e) => setError(e.message));
    }, 200);
    return () => clearTimeout(handle);
  }, [instructor, department, course, sort]);

  const set = (key, value) => {
    const next = new URLSearchParams(params);
    if (value) next.set(key, value);
    else next.delete(key);
    setParams(next, { replace: true });
  };

  const average = reviews?.length
    ? reviews.reduce((sum, r) => sum + r.rating, 0) / reviews.length
    : null;

  return (
    <div className="page">
      <h1>Reviews</h1>
      <p className="muted">Find out what students say about a professor, a department or a course.</p>
      <div className="filters">
        <input
          type="search"
          list="professor-options"
          placeholder="Professor name"
          value={instructor}
          onChange={(e) => set("professor", e.target.value)}
        />
        <datalist id="professor-options">
          {professors.map((p) => <option key={p} value={p} />)}
        </datalist>
        <select value={department} onChange={(e) => set("department", e.target.value)} aria-label="Department">
          <option value="">All departments</option>
          {departments.map((d) => <option key={d}>{d}</option>)}
        </select>
        <input
          type="search"
          placeholder="Course code or title"
          value={course}
          onChange={(e) => set("course", e.target.value)}
        />
        <SortSelect value={sort} onChange={(v) => set("sort", v === "newest" ? "" : v)} />
      </div>

      {error && <div className="alert alert-error">{error}</div>}
      {reviews === null ? (
        <div className="page-loading">Loading…</div>
      ) : reviews.length === 0 ? (
        <p className="muted">No reviews match. Older reviews may not name a professor.</p>
      ) : (
        <>
          <div className="review-summary">
            <Stars rating={average} showCount={false} />
            <span>
              average across {reviews.length} review{reviews.length === 1 ? "" : "s"}
              {reviews.length === 200 && " (showing the first 200)"}
            </span>
          </div>
          <ul className="review-list card">
            {reviews.map((r) => (
              <li key={r.id} className={`review ${r.mine ? "review-mine" : ""}`}>
                <div className="review-head">
                  <Link to={`/courses/${r.course_id}`} className="review-course" style={{ color: courseColor(r.course_id) }}>
                    {courseCode(r)}
                  </Link>
                  <span className="muted">{r.course_title}</span>
                </div>
                <div className="review-head">
                  <Stars rating={r.rating} showCount={false} />
                  <span className="review-prof">{r.instructor ?? "Professor not specified"}</span>
                  <strong>{r.mine ? "You" : r.author}</strong>
                  <span className="muted small">
                    {parseLocal(r.updated_at).toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" })}
                  </span>
                </div>
                <p>{r.body}</p>
              </li>
            ))}
          </ul>
        </>
      )}
    </div>
  );
}
