"""schedules and schedule_sections."""

from ..db import execute, in_clause, query, query_one

SCHEDULE_FIELDS = """s.id, s.term_id, s.name, s.is_committed, s.created_at, s.updated_at,
                     t.name AS term_name"""


def get_owned(schedule_id, user_id):
    return query_one(
        f"""SELECT {SCHEDULE_FIELDS}
            FROM schedules s JOIN terms t ON t.id = s.term_id
            WHERE s.id = %s AND s.user_id = %s""",
        (schedule_id, user_id),
    )


def list_for_user(user_id, term_id=None):
    sql = f"""SELECT {SCHEDULE_FIELDS}
              FROM schedules s JOIN terms t ON t.id = s.term_id
              WHERE s.user_id = %s"""
    args = [user_id]
    if term_id:
        sql += " AND s.term_id = %s"
        args.append(term_id)
    sql += " ORDER BY t.start_date, s.created_at, s.id"
    return query(sql, tuple(args))


def section_ids(schedule_ids):
    """{schedule_id: [section_id, ...]}"""
    result = {sid: [] for sid in schedule_ids}
    if schedule_ids:
        for row in query(
            f"SELECT schedule_id, section_id FROM schedule_sections WHERE schedule_id IN ({in_clause(schedule_ids)})",
            tuple(schedule_ids),
        ):
            result[row["schedule_id"]].append(row["section_id"])
    return result


def create(user_id, term_id, name):
    return execute(
        "INSERT INTO schedules (user_id, term_id, name) VALUES (%s, %s, %s)",
        (user_id, term_id, name),
    )


def copy_sections(to_schedule_id, from_schedule_id):
    execute(
        """INSERT INTO schedule_sections (schedule_id, section_id)
           SELECT %s, section_id FROM schedule_sections WHERE schedule_id = %s""",
        (to_schedule_id, from_schedule_id),
    )


def rename(schedule_id, name):
    execute("UPDATE schedules SET name = %s WHERE id = %s", (name, schedule_id))


def delete(schedule_id):
    execute("DELETE FROM schedules WHERE id = %s", (schedule_id,))


def remove_course(schedule_id, course_id):
    """Remove any section of `course_id` from the schedule."""
    execute(
        """DELETE ss FROM schedule_sections ss JOIN sections s ON s.id = ss.section_id
           WHERE ss.schedule_id = %s AND s.course_id = %s""",
        (schedule_id, course_id),
    )


def add_section(schedule_id, section_id):
    execute("INSERT INTO schedule_sections (schedule_id, section_id) VALUES (%s, %s)", (schedule_id, section_id))


def remove_section(schedule_id, section_id):
    """Returns the number of rows deleted."""
    return execute(
        "DELETE FROM schedule_sections WHERE schedule_id = %s AND section_id = %s",
        (schedule_id, section_id),
    )


def touch(schedule_id, when):
    execute("UPDATE schedules SET updated_at = %s WHERE id = %s", (when, schedule_id))


def uncommit_others(user_id, term_id, keep_schedule_id):
    execute(
        "UPDATE schedules SET is_committed = FALSE WHERE user_id = %s AND term_id = %s AND id <> %s",
        (user_id, term_id, keep_schedule_id),
    )


def set_committed(schedule_id, committed):
    execute(f"UPDATE schedules SET is_committed = {'TRUE' if committed else 'FALSE'} WHERE id = %s", (schedule_id,))
