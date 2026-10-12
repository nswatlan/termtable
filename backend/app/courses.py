"""Catalog browsing (terms, courses, sections) and public course reviews."""

from flask import Blueprint, g, request, session

from .auth import login_required
from .db import commit, execute, in_clause, query, query_one, to_time
from .errors import bad_request, json_body, not_found, optional_str, require_int, require_str

bp = Blueprint("courses", __name__)


# --- shared helpers (also used by schedules / calendar) -------------------

def rating_summaries(course_ids):
    """{course_id: {"avg_rating": float|None, "review_count": int}}"""
    summaries = {cid: {"avg_rating": None, "review_count": 0} for cid in course_ids}
    if not course_ids:
        return summaries
    rows = query(
        f"""SELECT course_id, AVG(rating) AS avg_rating, COUNT(*) AS review_count
            FROM reviews WHERE course_id IN ({in_clause(course_ids)})
            GROUP BY course_id""",
        tuple(course_ids),
    )
    for row in rows:
        summaries[row["course_id"]] = {
            "avg_rating": round(float(row["avg_rating"]), 2),
            "review_count": row["review_count"],
        }
    return summaries


def load_sections(where, args):
    """Sections joined with their course, each with a list of meetings.

    `where` is a SQL condition over the aliases s (sections) and c (courses).
    """
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


def _like(term):
    escaped = term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


# --- terms & courses ------------------------------------------------------

@bp.get("/terms")
def list_terms():
    return query("SELECT id, name, start_date, end_date FROM terms ORDER BY start_date")


@bp.get("/departments")
def list_departments():
    rows = query("SELECT DISTINCT department FROM courses ORDER BY department")
    return [r["department"] for r in rows]


@bp.get("/courses")
def search_courses():
    """Search the catalog. `q` matches course code, title, description,
    instructor or CRN; `crn` matches CRNs only (by prefix). Each course comes
    with its sections (CRN, instructor, location, meetings), limited to the
    chosen term and, when searching by CRN, to the matching sections."""
    q = (request.args.get("q") or "").strip()
    crn = "".join(ch for ch in (request.args.get("crn") or "") if ch.isdigit())
    department = (request.args.get("department") or "").strip()
    term_id = request.args.get("term_id", type=int)

    conditions, args = [], []
    if q:
        like = _like(q)
        conditions.append(
            """(CONCAT(c.department, ' ', c.number) LIKE %s
                OR CONCAT(c.department, c.number) LIKE %s
                OR c.title LIKE %s OR c.description LIKE %s
                OR EXISTS (SELECT 1 FROM sections s
                           WHERE s.course_id = c.id AND (s.instructor LIKE %s OR s.crn = %s)))"""
        )
        args += [like, like, like, like, like, q]
    if crn:
        conditions.append(
            "EXISTS (SELECT 1 FROM sections s WHERE s.course_id = c.id AND s.crn LIKE %s"
            + (" AND s.term_id = %s)" if term_id else ")")
        )
        args.append(f"{crn}%")
        if term_id:
            args.append(term_id)
    elif crn == "" and request.args.get("crn"):
        return []  # a CRN search with no digits matches nothing
    if department:
        conditions.append("c.department = %s")
        args.append(department)
    if term_id:
        conditions.append("EXISTS (SELECT 1 FROM sections s WHERE s.course_id = c.id AND s.term_id = %s)")
        args.append(term_id)

    where = " AND ".join(conditions) or "TRUE"
    courses = query(
        f"""SELECT c.id, c.department, c.number, c.title, c.description, c.credits
            FROM courses c WHERE {where}
            ORDER BY c.department, c.number LIMIT 200""",
        tuple(args),
    )
    ids = [c["id"] for c in courses]
    ratings = rating_summaries(ids)
    sections_by_course = {cid: [] for cid in ids}
    if ids:
        where = f"s.course_id IN ({in_clause(ids)})"
        section_args = list(ids)
        if term_id:
            where += " AND s.term_id = %s"
            section_args.append(term_id)
        if crn:
            where += " AND s.crn LIKE %s"
            section_args.append(f"{crn}%")
        for section in load_sections(where, tuple(section_args)):
            sections_by_course[section["course_id"]].append(section)
    for c in courses:
        c.update(ratings[c["id"]])
        c["sections"] = sections_by_course[c["id"]]
    return courses


@bp.get("/sections/by-crn/<crn>")
def section_by_crn(crn):
    sections = load_sections("s.crn = %s", (crn.strip(),))
    if not sections:
        raise not_found("Section with that CRN")
    return sections[0]


@bp.get("/instructors")
def list_instructors():
    """Instructors who teach (or taught) at least one section, optionally
    for one department or one course."""
    department = (request.args.get("department") or "").strip()
    course_id = request.args.get("course_id", type=int)
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


@bp.get("/courses/<int:course_id>")
def get_course(course_id):
    course = query_one(
        "SELECT id, department, number, title, description, credits FROM courses WHERE id = %s",
        (course_id,),
    )
    if course is None:
        raise not_found("Course")
    course.update(rating_summaries([course_id])[course_id])

    distribution = {str(n): 0 for n in range(1, 6)}
    for row in query(
        "SELECT rating, COUNT(*) AS n FROM reviews WHERE course_id = %s GROUP BY rating",
        (course_id,),
    ):
        distribution[str(row["rating"])] = row["n"]
    course["rating_distribution"] = distribution

    term_id = request.args.get("term_id", type=int)
    if term_id:
        course["sections"] = load_sections("s.course_id = %s AND s.term_id = %s", (course_id, term_id))
    else:
        course["sections"] = load_sections("s.course_id = %s", (course_id,))
    return course


# --- reviews --------------------------------------------------------------

REVIEW_SORTS = {
    "newest": "r.updated_at DESC, r.id DESC",
    "oldest": "r.updated_at ASC, r.id ASC",
    "highest": "r.rating DESC, r.updated_at DESC",
    "lowest": "r.rating ASC, r.updated_at DESC",
}


def _review_order():
    sort = request.args.get("sort") or "newest"
    if sort not in REVIEW_SORTS:
        raise bad_request(f"'sort' must be one of {', '.join(REVIEW_SORTS)}")
    return REVIEW_SORTS[sort]


def _mark_mine(reviews):
    viewer = session.get("user_id")
    for r in reviews:
        r["mine"] = r.pop("user_id") == viewer
    return reviews


@bp.get("/courses/<int:course_id>/reviews")
def list_reviews(course_id):
    if query_one("SELECT id FROM courses WHERE id = %s", (course_id,)) is None:
        raise not_found("Course")
    conditions, args = ["r.course_id = %s"], [course_id]
    instructor = (request.args.get("instructor") or "").strip()
    if instructor:
        conditions.append("r.instructor = %s")
        args.append(instructor)
    reviews = query(
        f"""SELECT r.id, r.rating, r.instructor, r.body, r.created_at, r.updated_at, r.user_id,
                   u.display_name AS author
            FROM reviews r JOIN users u ON u.id = r.user_id
            WHERE {" AND ".join(conditions)} ORDER BY {_review_order()}""",
        tuple(args),
    )
    return _mark_mine(reviews)


@bp.get("/reviews")
def search_reviews():
    """Reviews across all courses, filtered by professor, department and/or
    course (code or title), sorted by `sort`."""
    conditions, args = [], []
    instructor = (request.args.get("instructor") or "").strip()
    department = (request.args.get("department") or "").strip()
    course = (request.args.get("course") or "").strip()
    if instructor:
        conditions.append("r.instructor LIKE %s")
        args.append(_like(instructor))
    if department:
        conditions.append("c.department = %s")
        args.append(department)
    if course:
        like = _like(course)
        conditions.append(
            """(CONCAT(c.department, ' ', c.number) LIKE %s
                OR CONCAT(c.department, c.number) LIKE %s OR c.title LIKE %s)""")
        args += [like, like, like]
    where = " AND ".join(conditions) or "TRUE"
    reviews = query(
        f"""SELECT r.id, r.rating, r.instructor, r.body, r.created_at, r.updated_at, r.user_id,
                   u.display_name AS author,
                   c.id AS course_id, c.department, c.number, c.title AS course_title
            FROM reviews r
            JOIN users u ON u.id = r.user_id
            JOIN courses c ON c.id = r.course_id
            WHERE {where} ORDER BY {_review_order()} LIMIT 200""",
        tuple(args),
    )
    return _mark_mine(reviews)


@bp.put("/courses/<int:course_id>/reviews/mine")
@login_required
def upsert_my_review(course_id):
    if query_one("SELECT id FROM courses WHERE id = %s", (course_id,)) is None:
        raise not_found("Course")
    data = json_body()
    rating = require_int(data, "rating", minimum=1, maximum=5)
    body = require_str(data, "body", max_len=5000)
    instructor = optional_str(data, "instructor", max_len=100)
    if instructor is not None and query_one(
        "SELECT 1 FROM sections WHERE course_id = %s AND instructor = %s LIMIT 1",
        (course_id, instructor),
    ) is None:
        raise bad_request("Pick a professor who teaches this course")
    execute(
        """INSERT INTO reviews (course_id, user_id, rating, instructor, body) VALUES (%s, %s, %s, %s, %s)
           ON DUPLICATE KEY UPDATE rating = VALUES(rating), instructor = VALUES(instructor),
                                   body = VALUES(body)""",
        (course_id, g.user["id"], rating, instructor, body),
    )
    commit()
    return query_one(
        """SELECT r.id, r.rating, r.instructor, r.body, r.created_at, r.updated_at,
                  u.display_name AS author, TRUE AS mine
           FROM reviews r JOIN users u ON u.id = r.user_id
           WHERE r.course_id = %s AND r.user_id = %s""",
        (course_id, g.user["id"]),
    )


@bp.delete("/courses/<int:course_id>/reviews/mine")
@login_required
def delete_my_review(course_id):
    deleted = execute(
        "DELETE FROM reviews WHERE course_id = %s AND user_id = %s",
        (course_id, g.user["id"]),
    )
    if not deleted:
        raise not_found("Review")
    commit()
    return {"ok": True}
