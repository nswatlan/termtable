"""calendar_events (a student's own events) and event_invitations."""

from ..db import execute, in_clause, query, query_one

EVENT_COLUMNS = ("id", "title", "description", "location", "color", "start_at", "end_at", "all_day",
                 "recurrence_freq", "recurrence_interval", "recurrence_days", "recurrence_until")
EVENT_FIELDS = ", ".join(EVENT_COLUMNS)
_E_FIELDS = ", ".join(f"e.{c}" for c in EVENT_COLUMNS)


# --- events ---------------------------------------------------------------------

def get_owned(event_id, user_id):
    return query_one(f"SELECT {EVENT_FIELDS} FROM calendar_events WHERE id = %s AND user_id = %s",
                     (event_id, user_id))


def insert(user_id, fields):
    columns = ", ".join(fields)
    return execute(
        f"INSERT INTO calendar_events (user_id, {columns}) VALUES (%s, {in_clause(fields)})",
        (user_id, *fields.values()),
    )


def update(event_id, user_id, fields):
    assignments = ", ".join(f"{k} = %s" for k in fields)
    execute(
        f"UPDATE calendar_events SET {assignments} WHERE id = %s AND user_id = %s",
        (*fields.values(), event_id, user_id),
    )


def delete(event_id, user_id):
    execute("DELETE FROM calendar_events WHERE id = %s AND user_id = %s", (event_id, user_id))


def owned_in_range(user_id, range_start, range_end):
    """Non-recurring events overlapping the range, plus recurring ones that
    started before it ends (recurrence expansion filters those further)."""
    return query(
        f"""SELECT {EVENT_FIELDS} FROM calendar_events
            WHERE user_id = %s AND start_at < %s
              AND (end_at > %s OR recurrence_freq IS NOT NULL)""",
        (user_id, range_end, range_start),
    )


def guest_counts(event_ids):
    """{event_id: number of invitations not declined}"""
    if not event_ids:
        return {}
    rows = query(
        f"""SELECT event_id, COUNT(*) AS n FROM event_invitations
            WHERE event_id IN ({in_clause(event_ids)}) AND status <> 'declined' GROUP BY event_id""",
        tuple(event_ids),
    )
    return {r["event_id"]: r["n"] for r in rows}


# --- invitations ------------------------------------------------------------------

def guests(event_id):
    return query(
        """SELECT i.id, i.status, i.created_at, i.responded_at,
                  u.id AS user_id, u.email, u.display_name
           FROM event_invitations i JOIN users u ON u.id = i.invitee_id
           WHERE i.event_id = %s
           ORDER BY FIELD(i.status, 'accepted', 'pending', 'declined'), u.display_name""",
        (event_id,),
    )


def find_invitation(event_id, invitee_id):
    return query_one(
        "SELECT id, status FROM event_invitations WHERE event_id = %s AND invitee_id = %s",
        (event_id, invitee_id),
    )


def create_invitation(event_id, invitee_id):
    """Raises pymysql IntegrityError if one already exists."""
    execute("INSERT INTO event_invitations (event_id, invitee_id) VALUES (%s, %s)", (event_id, invitee_id))


def reopen_invitation(invitation_id):
    execute(
        "UPDATE event_invitations SET status = 'pending', responded_at = NULL, created_at = NOW() WHERE id = %s",
        (invitation_id,),
    )


def delete_invitation(invitation_id, event_id):
    """Returns the number of rows deleted."""
    return execute("DELETE FROM event_invitations WHERE id = %s AND event_id = %s", (invitation_id, event_id))


def invitation_for_invitee(invitation_id, invitee_id):
    return query_one(
        "SELECT id FROM event_invitations WHERE id = %s AND invitee_id = %s",
        (invitation_id, invitee_id),
    )


def set_invitation_status(invitation_id, status):
    execute("UPDATE event_invitations SET status = %s, responded_at = NOW() WHERE id = %s", (status, invitation_id))


def pending_count(invitee_id):
    row = query_one(
        "SELECT COUNT(*) AS n FROM event_invitations WHERE invitee_id = %s AND status = 'pending'",
        (invitee_id,),
    )
    return row["n"]


def received(invitee_id, status=None, invitation_id=None):
    """Invitations sent to a student, joined with the event and its owner.
    Optionally only one status, or one invitation."""
    conditions, args = ["i.invitee_id = %s"], [invitee_id]
    if status is not None:
        conditions.append("i.status = %s")
        args.append(status)
    if invitation_id is not None:
        conditions.append("i.id = %s")
        args.append(invitation_id)
    return query(
        f"""SELECT i.id AS invitation_id, i.status, i.created_at AS invited_at,
                   o.display_name AS owner_name, o.email AS owner_email,
                   {_E_FIELDS}
            FROM event_invitations i
            JOIN calendar_events e ON e.id = i.event_id
            JOIN users o ON o.id = e.user_id
            WHERE {" AND ".join(conditions)}
            ORDER BY e.start_at""",
        tuple(args),
    )


def shared_in_range(invitee_id, range_start, range_end):
    """Other students' events this student accepted or hasn't answered."""
    return query(
        f"""SELECT {_E_FIELDS}, i.id AS invitation_id, i.status AS invitation_status,
                   o.display_name AS owner_name
            FROM event_invitations i
            JOIN calendar_events e ON e.id = i.event_id
            JOIN users o ON o.id = e.user_id
            WHERE i.invitee_id = %s AND i.status IN ('accepted', 'pending')
              AND e.start_at < %s AND (e.end_at > %s OR e.recurrence_freq IS NOT NULL)""",
        (invitee_id, range_end, range_start),
    )
