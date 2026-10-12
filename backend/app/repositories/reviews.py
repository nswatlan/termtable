"""reviews table."""

from ..db import execute, query, query_one
from .catalog import like

# Allowed sort keys, in the order they're listed in error messages.
ORDER_BY = {
    "newest": "r.updated_at DESC, r.id DESC",
    "oldest": "r.updated_at ASC, r.id ASC",
    "highest": "r.rating DESC, r.updated_at DESC",
    "lowest": "r.rating ASC, r.updated_at DESC",
}

REVIEW_FIELDS = """r.id, r.rating, r.instructor, r.body, r.created_at, r.updated_at, r.user_id,
                   u.display_name AS author"""


def for_course(course_id, sort, instructor=None):
    conditions, args = ["r.course_id = %s"], [course_id]
    if instructor:
        conditions.append("r.instructor = %s")
        args.append(instructor)
    return query(
        f"""SELECT {REVIEW_FIELDS}
            FROM reviews r JOIN users u ON u.id = r.user_id
            WHERE {" AND ".join(conditions)} ORDER BY {ORDER_BY[sort]}""",
        tuple(args),
    )


def search(sort, instructor=None, department=None, course=None, limit=200):
    conditions, args = [], []
    if instructor:
        conditions.append("r.instructor LIKE %s")
        args.append(like(instructor))
    if department:
        conditions.append("c.department = %s")
        args.append(department)
    if course:
        pattern = like(course)
        conditions.append(
            """(CONCAT(c.department, ' ', c.number) LIKE %s
                OR CONCAT(c.department, c.number) LIKE %s OR c.title LIKE %s)""")
        args += [pattern, pattern, pattern]
    where = " AND ".join(conditions) or "TRUE"
    return query(
        f"""SELECT {REVIEW_FIELDS},
                   c.id AS course_id, c.department, c.number, c.title AS course_title
            FROM reviews r
            JOIN users u ON u.id = r.user_id
            JOIN courses c ON c.id = r.course_id
            WHERE {where} ORDER BY {ORDER_BY[sort]} LIMIT {int(limit)}""",
        tuple(args),
    )


def upsert(course_id, user_id, rating, instructor, body):
    execute(
        """INSERT INTO reviews (course_id, user_id, rating, instructor, body) VALUES (%s, %s, %s, %s, %s)
           ON DUPLICATE KEY UPDATE rating = VALUES(rating), instructor = VALUES(instructor),
                                   body = VALUES(body)""",
        (course_id, user_id, rating, instructor, body),
    )


def get_mine(course_id, user_id):
    return query_one(
        """SELECT r.id, r.rating, r.instructor, r.body, r.created_at, r.updated_at,
                  u.display_name AS author, TRUE AS mine
           FROM reviews r JOIN users u ON u.id = r.user_id
           WHERE r.course_id = %s AND r.user_id = %s""",
        (course_id, user_id),
    )


def delete_mine(course_id, user_id):
    """Returns the number of rows deleted."""
    return execute("DELETE FROM reviews WHERE course_id = %s AND user_id = %s", (course_id, user_id))
