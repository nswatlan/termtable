"""Course-provided assignments and a student's grades on them, plus the
student's gradebook settings (grade_settings) and custom weights
(grade_weights)."""

from ..db import execute, in_clause, query, query_one

SCORED_FIELDS = """a.id, a.course_id, a.term_id, a.title, a.category, a.due_at, a.max_points, gr.score"""


def _offering_filter(offerings):
    """SQL + args matching assignments of any (course_id, term_id) pair."""
    pairs = list(offerings)
    placeholders = ", ".join(["(%s, %s)"] * len(pairs))
    return f"(a.course_id, a.term_id) IN ({placeholders})", [v for p in pairs for v in p]


def scored_due_between(user_id, offerings, start, end):
    """Assignments of the given offerings due in [start, end), with the
    student's score (None if ungraded)."""
    if not offerings:
        return []
    where, args = _offering_filter(offerings)
    return query(
        f"""SELECT {SCORED_FIELDS}
            FROM assignments a
            LEFT JOIN grades gr ON gr.assignment_id = a.id AND gr.user_id = %s
            WHERE {where} AND a.due_at >= %s AND a.due_at < %s""",
        (user_id, *args, start, end),
    )


def scored_due_since(user_id, offerings, since, limit=300):
    if not offerings:
        return []
    where, args = _offering_filter(offerings)
    return query(
        f"""SELECT {SCORED_FIELDS}
            FROM assignments a
            LEFT JOIN grades gr ON gr.assignment_id = a.id AND gr.user_id = %s
            WHERE {where} AND a.due_at >= %s
            ORDER BY a.due_at, a.id LIMIT {int(limit)}""",
        (user_id, *args, since),
    )


def gradebook_rows(user_id, course_id, term_id):
    """Every assignment of one offering with the student's score and custom weight."""
    return query(
        """SELECT a.id, a.title, a.category, a.due_at, a.max_points, a.description,
                  gr.score, gw.weight AS custom_weight
           FROM assignments a
           LEFT JOIN grades gr ON gr.assignment_id = a.id AND gr.user_id = %s
           LEFT JOIN grade_weights gw ON gw.assignment_id = a.id AND gw.user_id = %s
           WHERE a.course_id = %s AND a.term_id = %s
           ORDER BY a.due_at, a.id""",
        (user_id, user_id, course_id, term_id),
    )


def get_assignment(assignment_id):
    return query_one("SELECT id, course_id, term_id, max_points FROM assignments WHERE id = %s", (assignment_id,))


def ids_in_offering(course_id, term_id, assignment_ids):
    if not assignment_ids:
        return set()
    rows = query(
        f"SELECT id FROM assignments WHERE course_id = %s AND term_id = %s AND id IN ({in_clause(assignment_ids)})",
        (course_id, term_id, *assignment_ids),
    )
    return {r["id"] for r in rows}


# --- grades -----------------------------------------------------------------------

def set_score(user_id, assignment_id, score):
    execute(
        """INSERT INTO grades (user_id, assignment_id, score) VALUES (%s, %s, %s)
           ON DUPLICATE KEY UPDATE score = VALUES(score)""",
        (user_id, assignment_id, score),
    )


def clear_score(user_id, assignment_id):
    execute("DELETE FROM grades WHERE user_id = %s AND assignment_id = %s", (user_id, assignment_id))


# --- settings & weights -------------------------------------------------------------

def get_settings(user_id, course_id, term_id):
    return query_one(
        "SELECT mode, target_grade FROM grade_settings WHERE user_id = %s AND course_id = %s AND term_id = %s",
        (user_id, course_id, term_id),
    )


def save_settings(user_id, course_id, term_id, mode, target_grade):
    execute(
        """INSERT INTO grade_settings (user_id, course_id, term_id, mode, target_grade)
           VALUES (%s, %s, %s, %s, %s)
           ON DUPLICATE KEY UPDATE mode = VALUES(mode), target_grade = VALUES(target_grade)""",
        (user_id, course_id, term_id, mode, target_grade),
    )


def set_weight(user_id, assignment_id, weight):
    execute(
        """INSERT INTO grade_weights (user_id, assignment_id, weight) VALUES (%s, %s, %s)
           ON DUPLICATE KEY UPDATE weight = VALUES(weight)""",
        (user_id, assignment_id, weight),
    )


def clear_weight(user_id, assignment_id):
    execute("DELETE FROM grade_weights WHERE user_id = %s AND assignment_id = %s", (user_id, assignment_id))


def clear_weights_for_offering(user_id, course_id, term_id):
    execute(
        """DELETE gw FROM grade_weights gw JOIN assignments a ON a.id = gw.assignment_id
           WHERE gw.user_id = %s AND a.course_id = %s AND a.term_id = %s""",
        (user_id, course_id, term_id),
    )
