"""user_assignments: homework a student adds themselves."""

from ..db import execute, query

FIELDS = """ua.id, ua.title, ua.due_at, ua.notes, ua.completed, ua.completed_at,
            ua.course_id, ua.term_id, c.department, c.number, c.title AS course_title"""


def _select(user_id, where="TRUE", args=()):
    return query(
        f"""SELECT {FIELDS} FROM user_assignments ua
            LEFT JOIN courses c ON c.id = ua.course_id
            WHERE ua.user_id = %s AND {where}
            ORDER BY ua.due_at, ua.id""",
        (user_id, *args),
    )


def list_all(user_id):
    return _select(user_id)


def list_incomplete(user_id):
    return _select(user_id, "NOT ua.completed")


def list_due_between(user_id, start, end):
    return _select(user_id, "ua.due_at >= %s AND ua.due_at < %s", (start, end))


def list_since_or_incomplete(user_id, since):
    """Due on/after `since`, plus anything older that isn't done."""
    return _select(user_id, "(ua.due_at >= %s OR NOT ua.completed)", (since,))


def get(assignment_id, user_id):
    rows = _select(user_id, "ua.id = %s", (assignment_id,))
    return rows[0] if rows else None


def create(user_id, course_id, term_id, title, due_at, notes):
    return execute(
        """INSERT INTO user_assignments (user_id, course_id, term_id, title, due_at, notes)
           VALUES (%s, %s, %s, %s, %s, %s)""",
        (user_id, course_id, term_id, title, due_at, notes),
    )


def update(assignment_id, user_id, changes):
    execute(
        f"UPDATE user_assignments SET {', '.join(f'{k} = %s' for k in changes)} WHERE id = %s AND user_id = %s",
        (*changes.values(), assignment_id, user_id),
    )


def delete(assignment_id, user_id):
    execute("DELETE FROM user_assignments WHERE id = %s AND user_id = %s", (assignment_id, user_id))
