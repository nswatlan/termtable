import { useCallback, useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api, qs } from "../api";
import { useDialog } from "../components/Dialog";
import { StarInput, Stars } from "../components/Stars";
import { parseLocal } from "../lib/dates";
import { courseCode, meetingSummary } from "../lib/sections";
import { defaultPlanningTerm, useTerms } from "../lib/useTerms";

export default function CourseDetail() {
  const { courseId } = useParams();
  const terms = useTerms();
  const [course, setCourse] = useState(null);
  const [reviews, setReviews] = useState(null);
  const [myReview, setMyReview] = useState(undefined);
  const [sort, setSort] = useState("newest");
  const [professor, setProfessor] = useState("");
  const [error, setError] = useState(null);

  const loadReviews = useCallback(() => {
    api.get(`/courses/${courseId}/reviews${qs({ sort, instructor: professor })}`).then((list) => {
      setReviews(list);
      // The filter can hide your own review, so look it up separately then.
      if (!professor) setMyReview(list.find((r) => r.mine) ?? null);
      else api.get(`/courses/${courseId}/reviews`).then((all) => setMyReview(all.find((r) => r.mine) ?? null));
    });
  }, [courseId, sort, professor]);
  const load = useCallback(() => {
    api.get(`/courses/${courseId}`).then(setCourse).catch((e) => setError(e.message));
  }, [courseId]);
  useEffect(load, [load]);
  useEffect(loadReviews, [loadReviews]);

  if (error) return <div className="page"><div className="alert alert-error">{error}</div></div>;
  if (!course || !terms) return <div className="page-loading">Loading…</div>;

  const professors = [...new Set(course.sections.map((s) => s.instructor))].sort();
  const total = Object.values(course.rating_distribution).reduce((a, b) => a + b, 0);

  return (
    <div className="page course-page">
      <Link to="/courses" className="small">← All courses</Link>
      <header className="course-header">
        <div>
          <div className="eyebrow">{courseCode(course)} · {course.credits} credits</div>
          <h1>{course.title}</h1>
          <p>{course.description}</p>
        </div>
        <div className="rating-summary">
          <div className="rating-big">{course.avg_rating?.toFixed(1) ?? "—"}</div>
          <Stars rating={course.avg_rating} count={course.review_count} />
          <div className="rating-bars">
            {[5, 4, 3, 2, 1].map((n) => {
              const count = course.rating_distribution[n];
              return (
                <div key={n} className="rating-bar">
                  <span>{n}★</span>
                  <span className="rating-bar-track">
                    <span className="rating-bar-fill" style={{ width: total ? `${(count / total) * 100}%` : 0 }} />
                  </span>
                  <span className="muted">{count}</span>
                </div>
              );
            })}
          </div>
        </div>
      </header>

      <Sections course={course} terms={terms} />

      <section className="card">
        <div className="card-head">
          <h2>Reviews</h2>
          <div className="review-controls">
            <select value={professor} onChange={(e) => setProfessor(e.target.value)} aria-label="Filter by professor">
              <option value="">All professors</option>
              {professors.map((p) => <option key={p}>{p}</option>)}
            </select>
            <SortSelect value={sort} onChange={setSort} />
          </div>
        </div>
        <ReviewForm
          courseId={courseId}
          existing={myReview}
          professors={professors}
          onSaved={() => { load(); loadReviews(); }}
        />
        {reviews?.length === 0 && (
          <p className="muted">{professor ? `No reviews mention ${professor} yet.` : "No reviews yet. Be the first."}</p>
        )}
        <ul className="review-list">
          {reviews?.map((r) => (
            <li key={r.id} className={`review ${r.mine ? "review-mine" : ""}`}>
              <div className="review-head">
                <Stars rating={r.rating} showCount={false} />
                <strong>{r.mine ? "You" : r.author}</strong>
                <span className="review-prof">{r.instructor ?? "Professor not specified"}</span>
                <span className="muted small">
                  {parseLocal(r.updated_at).toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" })}
                </span>
              </div>
              <p>{r.body}</p>
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
}

function Sections({ course, terms }) {
  const offered = terms.filter((t) => course.sections.some((s) => s.term_id === t.id));
  const [termId, setTermId] = useState(
    () => (offered.find((t) => t.id === defaultPlanningTerm(terms)?.id) ?? offered[offered.length - 1])?.id,
  );
  const [schedules, setSchedules] = useState([]);
  const [message, setMessage] = useState(null);

  useEffect(() => {
    if (termId) api.get(`/schedules${qs({ term_id: termId })}`).then(setSchedules);
  }, [termId]);

  async function addTo(scheduleId, section) {
    setMessage(null);
    try {
      const updated = await api.post(`/schedules/${scheduleId}/sections`, { section_id: section.id });
      setSchedules((list) => list.map((s) => (s.id === updated.id ? updated : s)));
      setMessage({ ok: true, text: `Added section ${section.section_code} to "${updated.name}".` });
    } catch (e) {
      setMessage({ ok: false, text: e.message });
    }
  }

  if (!offered.length) {
    return <section className="card"><h2>Sections</h2><p className="muted">Not currently offered.</p></section>;
  }

  return (
    <section className="card">
      <div className="card-head">
        <h2>Sections</h2>
        <div className="segmented">
          {offered.map((t) => (
            <button key={t.id} className={t.id === termId ? "active" : ""} onClick={() => setTermId(t.id)}>
              {t.name}
            </button>
          ))}
        </div>
      </div>
      {message && <div className={`alert ${message.ok ? "alert-ok" : "alert-error"}`}>{message.text}</div>}
      <table className="table">
        <thead>
          <tr><th>Section</th><th>CRN</th><th>Instructor</th><th>Meets</th><th>Location</th><th>Seats</th><th /></tr>
        </thead>
        <tbody>
          {course.sections.filter((s) => s.term_id === termId).map((s) => (
            <tr key={s.id}>
              <td>{s.section_code}</td>
              <td className="crn">{s.crn}</td>
              <td>{s.instructor}</td>
              <td>{meetingSummary(s.meetings).map((l) => <div key={l}>{l}</div>)}</td>
              <td>{s.location}</td>
              <td>{s.capacity}</td>
              <td>
                {schedules.length > 0 ? (
                  <select
                    value=""
                    onChange={(e) => e.target.value && addTo(Number(e.target.value), s)}
                    aria-label="Add to schedule"
                  >
                    <option value="">Add to schedule…</option>
                    {schedules.map((sch) => (
                      <option key={sch.id} value={sch.id} disabled={sch.sections.some((x) => x.id === s.id)}>
                        {sch.name}{sch.sections.some((x) => x.id === s.id) ? " (added)" : ""}
                      </option>
                    ))}
                  </select>
                ) : (
                  <Link className="small" to={`/planner?term=${termId}`}>Make a schedule</Link>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}

export const REVIEW_SORTS = [
  ["newest", "Newest first"],
  ["oldest", "Oldest first"],
  ["highest", "Highest rated"],
  ["lowest", "Lowest rated"],
];

export function SortSelect({ value, onChange }) {
  return (
    <select value={value} onChange={(e) => onChange(e.target.value)} aria-label="Sort reviews">
      {REVIEW_SORTS.map(([key, label]) => <option key={key} value={key}>{label}</option>)}
    </select>
  );
}

function ReviewForm({ courseId, existing, professors, onSaved }) {
  const dialog = useDialog();
  const [editing, setEditing] = useState(false);
  const [rating, setRating] = useState(existing?.rating ?? null);
  const [instructor, setInstructor] = useState(existing?.instructor ?? "");
  const [body, setBody] = useState(existing?.body ?? "");
  const [error, setError] = useState(null);

  useEffect(() => {
    setRating(existing?.rating ?? null);
    setInstructor(existing?.instructor ?? "");
    setBody(existing?.body ?? "");
  }, [existing]);

  async function save(e) {
    e.preventDefault();
    if (!rating) return setError("Pick a star rating.");
    setError(null);
    try {
      await api.put(`/courses/${courseId}/reviews/mine`, { rating, body, instructor: instructor || null });
      setEditing(false);
      onSaved();
    } catch (err) {
      setError(err.message);
    }
  }

  async function remove() {
    const ok = await dialog.confirm({ title: "Delete your review?", confirmLabel: "Delete", danger: true });
    if (!ok) return;
    await api.del(`/courses/${courseId}/reviews/mine`);
    onSaved();
  }

  if (existing && !editing) {
    return (
      <div className="review-actions">
        <span className="muted">You've reviewed this course.</span>
        <button className="btn btn-sm" onClick={() => setEditing(true)}>Edit your review</button>
        <button className="btn btn-sm btn-ghost btn-danger" onClick={remove}>Delete</button>
      </div>
    );
  }

  return (
    <form className="review-form" onSubmit={save}>
      <div className="review-form-row">
        <span>{existing ? "Update your rating" : "Your rating"}</span>
        <StarInput value={rating} onChange={setRating} />
        <select value={instructor} onChange={(e) => setInstructor(e.target.value)} aria-label="Professor you had">
          <option value="">Which professor did you have?</option>
          {professors.map((p) => <option key={p}>{p}</option>)}
        </select>
      </div>
      <textarea
        value={body}
        onChange={(e) => setBody(e.target.value)}
        placeholder="What should other students know? Workload, exams, teaching…"
        rows={3}
        maxLength={5000}
        required
      />
      {error && <div className="alert alert-error">{error}</div>}
      <div className="review-form-row">
        <button className="btn btn-primary btn-sm">{existing ? "Save changes" : "Post review"}</button>
        {existing && <button type="button" className="btn btn-sm btn-ghost" onClick={() => setEditing(false)}>Cancel</button>}
        <span className="muted small">Reviews are public and show your name.</span>
      </div>
    </form>
  );
}
