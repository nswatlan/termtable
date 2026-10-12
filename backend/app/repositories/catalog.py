"""terms, courses, sections and meeting_times."""

from ..db import in_clause, query, query_one, to_time

COURSE_FIELDS = "c.id, c.department, c.number, c.title, c.description, c.credits"


def like(term):
    """A LIKE pattern matching `term` anywhere, with wildcards escaped."""
    escaped = term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


# --- terms & departments ----------------------------------------------------

def list_terms():
    return query("SELECT id, name, start_date, end_date FROM terms ORDER BY start_date")


def terms_by_ids(term_ids):
    if not term_ids:
        return []
    return query(
        f"SELECT id, name, start_date, end_date FROM terms WHERE id IN ({in_clause(term_ids)})",
        tuple(term_ids),
    )


def term_exists(term_id):
    return query_one("SELECT id FROM terms WHERE id = %s", (term_id,)) is not None


def list_departments():
    return [r["department"] for r in query("SELECT DISTINCT department FROM courses ORDER BY department")]


# --- courses ------------------------------------------------------------------

def search_courses(q=None, crn_prefix=None, department=None, term_id=None, limit=200):
    """Courses matching all given filters. `q` matches code, title,
    description, instructor or an exact CRN; `crn_prefix` matches CRNs."""
    conditions, args = [], []
    if q:
        pattern = like(q)
        conditions.append(
            """(CONCAT(c.department, ' ', c.number) LIKE %s
                OR CONCAT(c.department, c.number) LIKE %s
                OR c.title LIKE %s OR c.description LIKE %s
                OR EXISTS (SELECT 1 FROM sections s
                           WHERE s.course_id = c.id AND (s.instructor LIKE %s OR s.crn = %s)))"""
        )
        args += [pattern, pattern, pattern, pattern, pattern, q]
    if crn_prefix:
        conditions.append(
            "EXISTS (SELECT 1 FROM sections s WHERE s.course_id = c.id AND s.crn LIKE %s"
            + (" AND s.term_id = %s)" if term_id else ")")
        )
        args.append(f"{crn_prefix}%")
        if term_id:
            args.append(term_id)
    if department:
        conditions.append("c.department = %s")
        args.append(department)
    if term_id:
        conditions.append("EXISTS (SELECT 1 FROM sections s WHERE s.course_id = c.id AND s.term_id = %s)")
        args.append(term_id)
    where = " AND ".join(conditions) or "TRUE"
    return query(
        f"""SELECT {COURSE_FIELDS} FROM courses c WHERE {where}
            ORDER BY c.department, c.number LIMIT {int(limit)}""",
        tuple(args),
    )


def get_course(course_id):
    return query_one(f"SELECT {COURSE_FIELDS} FROM courses c WHERE c.id = %s", (course_id,))


def course_exists(course_id):
    return query_one("SELECT id FROM courses WHERE id = %s", (course_id,)) is not None


def rating_stats(course_ids):
    """Rows of (course_id, avg_rating, review_count) for courses with reviews."""
    if not course_ids:
        return []
    return query(
        f"""SELECT course_id, AVG(rating) AS avg_rating, COUNT(*) AS review_count
            FROM reviews WHERE course_id IN ({in_clause(course_ids)})
            GROUP BY course_id""",
        tuple(course_ids),
    )


def rating_counts(course_id):
    """Rows of (rating, n) for one course."""
    return query("SELECT rating, COUNT(*) AS n FROM reviews WHERE course_id = %s GROUP BY rating", (course_id,))


# --- sections -------------------------------------------------------------------

def _load_sections(where, args):
    """Sections joined with their course, each with a list of meetings.
    `where` is a SQL condition over the aliases s (sections) and c (courses)."""
    sections = query(
        f"""SELECT s.id, s.course_id, s.term_id, s.section_code, s.crn, s.instructor,
                   s.location, s.capacity,
                   c.department, c.number, c.title, c.credits
            FROM sections s JOIN courses c ON c.id = s.course_id
            WHERE {where}
            ORDER BY c.department, c.number, s.section_code""",
        args,
    )
    if not sections:
        return []
    ids = [s["id"] for s in sections]
    meetings = query(
        f"""SELECT id, section_id, day_of_week, start_time, end_time, kind
            FROM meeting_times WHERE section_id IN ({in_clause(ids)})
            ORDER BY day_of_week, start_time""",
        tuple(ids),
    )
    by_section = {sid: [] for sid in ids}
    for m in meetings:
        m["start_time"] = to_time(m["start_time"])
        m["end_time"] = to_time(m["end_time"])
        by_section[m["section_id"]].append(m)
    for s in sections:
        s["meetings"] = by_section[s["id"]]
    return sections


def sections_by_ids(section_ids):
    if not section_ids:
        return []
    return _load_sections(f"s.id IN ({in_clause(section_ids)})", tuple(section_ids))


def sections_for_course(course_id, term_id=None):
    if term_id:
        return _load_sections("s.course_id = %s AND s.term_id = %s", (course_id, term_id))
    return _load_sections("s.course_id = %s", (course_id,))


def sections_for_courses(course_ids, term_id=None, crn_prefix=None):
    if not course_ids:
        return []
    where = f"s.course_id IN ({in_clause(course_ids)})"
    args = list(course_ids)
    if term_id:
        where += " AND s.term_id = %s"
        args.append(term_id)
    if crn_prefix:
        where += " AND s.crn LIKE %s"
        args.append(f"{crn_prefix}%")
    return _load_sections(where, tuple(args))


def section_by_crn(crn):
    sections = _load_sections("s.crn = %s", (crn,))
    return sections[0] if sections else None


def committed_sections(user_id, term_ids=None):
    """Sections in the student's committed schedules."""
    where = """s.id IN (
                   SELECT ss.section_id FROM schedule_sections ss
                   JOIN schedules sc ON sc.id = ss.schedule_id
                   WHERE sc.user_id = %s AND sc.is_committed)"""
    args = [user_id]
    if term_ids is not None:
        where += f" AND s.term_id IN ({in_clause(term_ids)})"
        args += list(term_ids)
    return _load_sections(where, tuple(args))


def section_basics(section_id):
    return query_one("SELECT id, course_id, term_id FROM sections WHERE id = %s", (section_id,))


def instructors(department=None, course_id=None):
    conditions, args = [], []
    if department:
        conditions.append("c.department = %s")
        args.append(department)
    if course_id:
        conditions.append("c.id = %s")
        args.append(course_id)
    where = " AND ".join(conditions) or "TRUE"
    rows = query(
        f"""SELECT DISTINCT s.instructor FROM sections s JOIN courses c ON c.id = s.course_id
            WHERE {where} ORDER BY s.instructor""",
        tuple(args),
    )
    return [r["instructor"] for r in rows]


def instructor_teaches(course_id, instructor):
    return query_one(
        "SELECT 1 FROM sections WHERE course_id = %s AND instructor = %s LIMIT 1",
        (course_id, instructor),
    ) is not None
