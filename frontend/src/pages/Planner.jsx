import { useCallback, useEffect, useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { api, qs } from "../api";
import { useDialog } from "../components/Dialog";
import { Stars } from "../components/Stars";
import WeekGrid from "../components/WeekGrid";
import { courseColor } from "../lib/colors";
import { DAY_SHORT, formatHHMM } from "../lib/dates";
import { courseCode, describeConflict, meetingSummary } from "../lib/sections";
import { defaultPlanningTerm, useTerms } from "../lib/useTerms";

export default function Planner() {
  const terms = useTerms();
  const dialog = useDialog();
  const [params, setParams] = useSearchParams();
  const termId = Number(params.get("term")) || defaultPlanningTerm(terms)?.id;

  const [schedules, setSchedules] = useState(null);
  const [activeId, setActiveId] = useState(null);
  const [comparing, setComparing] = useState(false);
  const [preview, setPreview] = useState(null);
  const [error, setError] = useState(null);

  const load = useCallback(async () => {
    if (!termId) return;
    const list = await api.get(`/schedules${qs({ term_id: termId })}`);
    setSchedules(list);
    setActiveId((current) =>
      list.some((s) => s.id === current) ? current : (list.find((s) => s.is_committed) ?? list[0])?.id ?? null,
    );
  }, [termId]);

  useEffect(() => {
    setSchedules(null);
    load().catch((e) => setError(e.message));
  }, [load]);

  const active = schedules?.find((s) => s.id === activeId) ?? null;

  // Run an API call that returns an updated schedule and swap it into the list.
  async function run(promise) {
    setError(null);
    try {
      const updated = await promise;
      if (updated?.id) {
        setSchedules((list) => {
          const exists = list.some((s) => s.id === updated.id);
          return exists ? list.map((s) => (s.id === updated.id ? updated : s)) : [...list, updated];
        });
      }
      return updated;
    } catch (e) {
      setError(e.message);
      return null;
    }
  }

  async function createSchedule(copyFrom) {
    const name = await dialog.prompt({
      title: copyFrom ? "Duplicate schedule" : "New schedule",
      message: copyFrom ? `Starts with the same sections as "${copyFrom.name}".` : undefined,
      defaultValue: copyFrom ? `${copyFrom.name} (copy)` : `Option ${String.fromCharCode(65 + (schedules?.length ?? 0))}`,
      confirmLabel: "Create",
    });
    if (!name) return;
    const created = await run(
      api.post("/schedules", copyFrom ? { name, copy_from: copyFrom.id } : { name, term_id: termId }),
    );
    if (created) {
      setActiveId(created.id);
      setComparing(false);
    }
  }

  async function renameSchedule() {
    const name = await dialog.prompt({ title: "Rename schedule", defaultValue: active.name, confirmLabel: "Rename" });
    if (name && name !== active.name) await run(api.patch(`/schedules/${active.id}`, { name }));
  }

  async function deleteSchedule() {
    const ok = await dialog.confirm({
      title: `Delete "${active.name}"?`,
      message: active.is_committed
        ? "This is the schedule on your calendar, so its classes will be removed from your calendar too. This can't be undone."
        : "This can't be undone.",
      confirmLabel: "Delete",
      danger: true,
    });
    if (!ok) return;
    setError(null);
    try {
      await api.del(`/schedules/${active.id}`);
      await load();
    } catch (e) {
      setError(e.message);
    }
  }

  async function toggleCommit() {
    if (active.is_committed) {
      const ok = await dialog.confirm({
        title: "Remove from your calendar?",
        message: "These classes and their assignments will come off your calendar. Grades you've entered are kept.",
        confirmLabel: "Remove",
        danger: true,
      });
      if (!ok) return;
      await run(api.del(`/schedules/${active.id}/commit`));
    } else {
      if (active.conflicts.length) {
        const ok = await dialog.confirm({
          title: "This schedule has time conflicts",
          message: "Add it to your calendar anyway?",
          confirmLabel: "Add anyway",
        });
        if (!ok) return;
      }
      await run(api.post(`/schedules/${active.id}/commit`));
    }
    await load(); // committing one schedule un-commits the others for this term
  }

  const addSection = (section) => {
    if (!active) return;
    setComparing(false); // show the schedule being changed
    run(api.post(`/schedules/${active.id}/sections`, { section_id: section.id }));
  };
  const removeSection = (section) => run(api.del(`/schedules/${active.id}/sections/${section.id}`));

  if (!terms) return <div className="page-loading">Loading…</div>;

  return (
    <div className="planner">
      <aside className="planner-search">
        <CourseFinder
          termId={termId}
          active={active}
          onAdd={addSection}
          onPreview={setPreview}
        />
      </aside>

      <section className="planner-main">
        <div className="planner-toolbar">
          <select
            value={termId ?? ""}
            onChange={(e) => setParams({ term: e.target.value })}
            aria-label="Term"
          >
            {terms.map((t) => <option key={t.id} value={t.id}>{t.name}</option>)}
          </select>

          <div className="tabs">
            {schedules?.map((s) => (
              <button
                key={s.id}
                className={`tab ${!comparing && s.id === activeId ? "active" : ""}`}
                onClick={() => { setActiveId(s.id); setComparing(false); }}
              >
                {s.is_committed && <span className="dot dot-green" title="On your calendar" />}
                {s.name}
                {s.conflicts.length > 0 && <span className="tab-warn" title="Has time conflicts">⚠</span>}
              </button>
            ))}
            <button className="tab tab-new" onClick={() => createSchedule(null)}>+ New schedule</button>
          </div>

          {schedules?.length > 1 && (
            <button className={`btn btn-sm ${comparing ? "btn-primary" : ""}`} onClick={() => setComparing(!comparing)}>
              {comparing ? "Back to editing" : "Compare"}
            </button>
          )}
        </div>

        {error && <div className="alert alert-error">{error}</div>}

        {schedules === null ? (
          <div className="page-loading">Loading schedules…</div>
        ) : schedules.length === 0 ? (
          <div className="empty">
            <h2>No schedules for this term yet</h2>
            <p className="muted">
              Make a few candidate schedules (say, one with morning classes and one with no Fridays) and compare them.
            </p>
            <button className="btn btn-primary" onClick={() => createSchedule(null)}>Create a schedule</button>
          </div>
        ) : comparing ? (
          <CompareView schedules={schedules} onPick={(id) => { setActiveId(id); setComparing(false); }} />
        ) : active ? (
          <ScheduleEditor
            schedule={active}
            preview={preview}
            onRename={renameSchedule}
            onDuplicate={() => createSchedule(active)}
            onDelete={deleteSchedule}
            onToggleCommit={toggleCommit}
            onRemove={removeSection}
          />
        ) : null}
      </section>
    </div>
  );
}

// --- left column: search courses and pick sections -----------------------

function CourseFinder({ termId, active, onAdd, onPreview }) {
  const [q, setQ] = useState("");
  const [department, setDepartment] = useState("");
  const [departments, setDepartments] = useState([]);
  const [results, setResults] = useState(null);
  const [expanded, setExpanded] = useState(null);
  const [sectionsByCourse, setSectionsByCourse] = useState({});

  useEffect(() => { api.get("/departments").then(setDepartments); }, []);

  useEffect(() => {
    if (!termId) return;
    const handle = setTimeout(() => {
      api.get(`/courses${qs({ q, department, term_id: termId })}`).then(setResults);
    }, 200);
    return () => clearTimeout(handle);
  }, [q, department, termId]);

  useEffect(() => { setSectionsByCourse({}); setExpanded(null); }, [termId]);

  async function toggle(course) {
    if (expanded === course.id) return setExpanded(null);
    setExpanded(course.id);
    if (!sectionsByCourse[course.id]) {
      const detail = await api.get(`/courses/${course.id}${qs({ term_id: termId })}`);
      setSectionsByCourse((m) => ({ ...m, [course.id]: detail.sections }));
    }
  }

  const inSchedule = useMemo(() => new Set(active?.sections.map((s) => s.id) ?? []), [active]);
  const coursesInSchedule = useMemo(() => new Set(active?.sections.map((s) => s.course_id) ?? []), [active]);

  return (
    <>
      <div className="finder-controls">
        <input
          type="search"
          placeholder="Search courses (e.g. CS 201, calculus)"
          value={q}
          onChange={(e) => setQ(e.target.value)}
        />
        <select value={department} onChange={(e) => setDepartment(e.target.value)} aria-label="Department">
          <option value="">All departments</option>
          {departments.map((d) => <option key={d}>{d}</option>)}
        </select>
      </div>

      <div className="finder-results">
        {results === null && <div className="muted pad">Loading…</div>}
        {results?.length === 0 && <div className="muted pad">No courses match.</div>}
        {results?.map((course) => (
          <div key={course.id} className={`finder-course ${expanded === course.id ? "open" : ""}`}>
            <button className="finder-course-head" onClick={() => toggle(course)}>
              <span className="swatch" style={{ background: courseColor(course.id) }} />
              <span className="finder-course-text">
                <strong>{courseCode(course)}</strong> {course.title}
                <span className="finder-course-meta">
                  <Stars rating={course.avg_rating} count={course.review_count} />
                  <span className="muted"> · {course.credits} cr</span>
                  {coursesInSchedule.has(course.id) && <span className="pill pill-green">In schedule</span>}
                </span>
              </span>
            </button>

            {expanded === course.id && (
              <div className="finder-sections">
                {!sectionsByCourse[course.id] && <div className="muted pad">Loading sections…</div>}
                {sectionsByCourse[course.id]?.map((section) => {
                  const added = inSchedule.has(section.id);
                  const swaps = !added && coursesInSchedule.has(course.id);
                  return (
                    <div
                      key={section.id}
                      className="finder-section"
                      onMouseEnter={() => onPreview({ ...section, has_conflict: false })}
                      onMouseLeave={() => onPreview(null)}
                    >
                      <div>
                        <div><strong>Sec {section.section_code}</strong> · {section.instructor}</div>
                        {meetingSummary(section.meetings).map((line) => (
                          <div key={line} className="muted small">{line}</div>
                        ))}
                        {section.location && <div className="muted small">{section.location}</div>}
                      </div>
                      <button
                        className={`btn btn-sm ${added ? "" : "btn-primary"}`}
                        disabled={added || !active}
                        title={!active ? "Create a schedule first" : undefined}
                        onClick={() => { onAdd(section); onPreview(null); }}
                      >
                        {added ? "Added" : swaps ? "Swap in" : "Add"}
                      </button>
                    </div>
                  );
                })}
                <Link className="small" to={`/courses/${course.id}`}>Course page & reviews →</Link>
              </div>
            )}
          </div>
        ))}
      </div>
    </>
  );
}

// --- the selected schedule -------------------------------------------------

function ScheduleEditor({ schedule, preview, onRename, onDuplicate, onDelete, onToggleCommit, onRemove }) {
  const sectionsById = Object.fromEntries(schedule.sections.map((s) => [s.id, s]));
  return (
    <div className="schedule-editor">
      <div className="schedule-header">
        <div>
          <h1>{schedule.name}</h1>
          <StatsLine stats={schedule.stats} />
        </div>
        <div className="schedule-actions">
          <button className="btn btn-sm btn-ghost" onClick={onRename}>Rename</button>
          <button className="btn btn-sm btn-ghost" onClick={onDuplicate}>Duplicate</button>
          <button className="btn btn-sm btn-ghost btn-danger" onClick={onDelete}>Delete</button>
          <button className={`btn btn-sm ${schedule.is_committed ? "" : "btn-primary"}`} onClick={onToggleCommit}>
            {schedule.is_committed ? "✓ On your calendar · Remove" : "Add classes to calendar"}
          </button>
        </div>
      </div>

      {schedule.conflicts.length > 0 && (
        <div className="alert alert-warn">
          <strong>Time conflicts</strong>
          <ul>
            {schedule.conflicts.map((c, i) => <li key={i}>{describeConflict(c, sectionsById)}</li>)}
          </ul>
        </div>
      )}

      <WeekGrid sections={schedule.sections} preview={preview} />

      {schedule.sections.length === 0 ? (
        <p className="muted pad">Search for courses on the left and add sections to this schedule.</p>
      ) : (
        <table className="table section-table">
          <thead>
            <tr><th>Course</th><th>Section</th><th>Meets</th><th>Rating</th><th>Credits</th><th /></tr>
          </thead>
          <tbody>
            {schedule.sections.map((s) => (
              <tr key={s.id} className={s.has_conflict ? "row-conflict" : ""}>
                <td>
                  <span className="swatch" style={{ background: courseColor(s.course_id) }} />
                  <Link to={`/courses/${s.course_id}`}><strong>{courseCode(s)}</strong></Link> {s.title}
                </td>
                <td>{s.section_code}<div className="muted small">{s.instructor}</div></td>
                <td>{meetingSummary(s.meetings).map((l) => <div key={l} className="small">{l}</div>)}</td>
                <td><Stars rating={s.avg_rating} count={s.review_count} /></td>
                <td>{s.credits}</td>
                <td><button className="btn btn-sm btn-ghost" onClick={() => onRemove(s)}>Remove</button></td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}

function StatsLine({ stats }) {
  const parts = [
    `${stats.credits} credits`,
    stats.days.length ? stats.days.map((d) => DAY_SHORT[d]).join(" ") : "no class days",
  ];
  if (stats.earliest_start) parts.push(`${formatHHMM(stats.earliest_start)}–${formatHHMM(stats.latest_end)}`);
  return <div className="muted">{parts.join(" · ")}</div>;
}

// --- side-by-side comparison ---------------------------------------------

function CompareView({ schedules, onPick }) {
  const hours = (m) => `${(m / 60).toFixed(1)} h`;
  const rows = [
    ["Credits", (s) => s.stats.credits],
    ["Courses", (s) => s.stats.section_count],
    ["Time conflicts", (s) => s.stats.conflict_count
      ? <span className="text-danger">⚠ {s.stats.conflict_count}</span>
      : <span className="text-success">None</span>],
    ["Days on campus", (s) => s.stats.days.map((d) => DAY_SHORT[d]).join(" ") || "—"],
    ["Fridays free", (s) => (s.stats.days.includes(4) ? "No" : "Yes")],
    ["Earliest class", (s) => (s.stats.earliest_start ? formatHHMM(s.stats.earliest_start) : "—")],
    ["Latest class ends", (s) => (s.stats.latest_end ? formatHHMM(s.stats.latest_end) : "—")],
    ["Time in class / week", (s) => hours(s.stats.weekly_class_minutes)],
    ["Avg. course rating", (s) => <Stars rating={s.stats.avg_course_rating} showCount={false} />],
  ];
  return (
    <div className="compare">
      <div className="compare-grids" style={{ gridTemplateColumns: `repeat(${schedules.length}, minmax(280px, 1fr))` }}>
        {schedules.map((s) => (
          <div key={s.id} className="compare-col">
            <div className="compare-col-head">
              <strong>{s.name}</strong>
              {s.is_committed && <span className="pill pill-green">On calendar</span>}
              <button className="btn btn-sm btn-ghost" onClick={() => onPick(s.id)}>Edit</button>
            </div>
            <WeekGrid sections={s.sections} compact />
            <div className="compare-courses">
              {s.sections.map((sec) => (
                <span key={sec.id} className="chip" style={{ "--chip-color": courseColor(sec.course_id) }}>
                  {courseCode(sec)}
                </span>
              ))}
            </div>
          </div>
        ))}
      </div>
      <table className="table compare-table">
        <tbody>
          {rows.map(([label, value]) => (
            <tr key={label}>
              <th>{label}</th>
              {schedules.map((s) => <td key={s.id}>{value(s)}</td>)}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
