import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { api, qs } from "../api";
import { Stars } from "../components/Stars";
import { courseColor } from "../lib/colors";
import { courseCode, meetingSummary } from "../lib/sections";
import { useTerms } from "../lib/useTerms";

export default function Courses() {
  const terms = useTerms();
  const [params, setParams] = useSearchParams();
  const q = params.get("q") ?? "";
  const department = params.get("department") ?? "";
  const termId = params.get("term") ?? "";
  const crn = params.get("crn") ?? "";
  const [departments, setDepartments] = useState([]);
  const [courses, setCourses] = useState(null);

  useEffect(() => { api.get("/departments").then(setDepartments); }, []);
  useEffect(() => {
    const handle = setTimeout(() => {
      api.get(`/courses${qs({ q, crn, department, term_id: termId })}`).then(setCourses);
    }, 200);
    return () => clearTimeout(handle);
  }, [q, crn, department, termId]);

  const termName = (id) => terms?.find((t) => t.id === id)?.name;

  const update = (key) => (e) => {
    const next = new URLSearchParams(params);
    if (e.target.value) next.set(key, e.target.value);
    else next.delete(key);
    setParams(next, { replace: true });
  };

  return (
    <div className="page">
      <h1>Courses</h1>
      <div className="filters">
        <input type="search" placeholder="Search by code, title, topic or professor" value={q} onChange={update("q")} />
        <input
          type="search"
          className="crn-input"
          inputMode="numeric"
          placeholder="CRN"
          aria-label="Search by CRN"
          value={crn}
          onChange={update("crn")}
        />
        <select value={department} onChange={update("department")} aria-label="Department">
          <option value="">All departments</option>
          {departments.map((d) => <option key={d}>{d}</option>)}
        </select>
        <select value={termId} onChange={update("term")} aria-label="Offered in">
          <option value="">Any term</option>
          {terms?.map((t) => <option key={t.id} value={t.id}>Offered {t.name}</option>)}
        </select>
      </div>

      {courses === null ? (
        <div className="page-loading">Loading…</div>
      ) : courses.length === 0 ? (
        <p className="muted">No courses match your search.</p>
      ) : (
        <div className="course-list">
          {courses.map((c) => (
            <Link key={c.id} to={`/courses/${c.id}`} className="course-card">
              <div className="course-card-code" style={{ color: courseColor(c.id) }}>{courseCode(c)}</div>
              <div className="course-card-title">{c.title}</div>
              <p className="muted small clamp-2">{c.description}</p>
              {c.sections.length > 0 && (
                <ul className="section-mini-list">
                  {[...c.sections].sort((a, b) => a.term_id - b.term_id || a.section_code.localeCompare(b.section_code))
                    .slice(0, crn ? undefined : 4).map((s) => (
                    <li key={s.id} className={crn && s.crn.startsWith(crn) ? "match" : ""}>
                      <div className="section-mini-top">
                        <span>Sec {s.section_code}</span>
                        <span className="crn">CRN {s.crn}</span>
                        {!termId && <span className="muted">{termName(s.term_id)}</span>}
                      </div>
                      <div className="section-mini-detail">
                        <span>{s.instructor}</span>
                        <span>{meetingSummary(s.meetings).join(", ")}</span>
                        {s.location && <span>{s.location}</span>}
                      </div>
                    </li>
                  ))}
                  {!crn && c.sections.length > 4 && (
                    <li className="muted small">+{c.sections.length - 4} more sections</li>
                  )}
                </ul>
              )}
              <div className="course-card-foot">
                <Stars rating={c.avg_rating} count={c.review_count} />
                <span className="muted small">{c.credits} credits</span>
              </div>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
