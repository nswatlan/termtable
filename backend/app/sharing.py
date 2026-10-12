"""Calendar sharing: an event's owner invites other students by the email they
registered with; invitees accept or decline. Accepted (and still-pending)
invitations put the owner's event on the invitee's calendar feed, read live
from calendar_events, so the owner's edits show up everywhere at once.

Invitations are delivered in the app (an "Invitations" panel on the calendar
and a count in the navigation bar), not by sending email.
"""

import pymysql
from flask import Blueprint, g, request

from .auth import EMAIL_RE, login_required
from .calendar import EVENT_FIELDS, _own_event, _serialize_event
from .db import commit, execute, query, query_one
from .errors import ApiError, bad_request, json_body, not_found, require_str

bp = Blueprint("sharing", __name__)

RESPONSES = ("accepted", "declined")


def _guest_list(event_id):
    return query(
        """SELECT i.id, i.status, i.created_at, i.responded_at,
                  u.id AS user_id, u.email, u.display_name
           FROM event_invitations i JOIN users u ON u.id = i.invitee_id
           WHERE i.event_id = %s
           ORDER BY FIELD(i.status, 'accepted', 'pending', 'declined'), u.display_name""",
        (event_id,),
    )


# --- the owner's side -------------------------------------------------------

def _find_invitee(email):
    if not EMAIL_RE.match(email):
        raise bad_request("Enter a valid email address")
    if email == g.user["email"].lower():
        raise bad_request("You're already on your own event")
    invitee = query_one("SELECT id, email, display_name FROM users WHERE email = %s", (email,))
    if invitee is None:
        raise ApiError(404, f"No Termtable account uses {email}. They need to sign up first.")
    return invitee


@bp.get("/users/lookup")
@login_required
def lookup_user():
    """Check an email before inviting it (used while creating a new event)."""
    invitee = _find_invitee((request.args.get("email") or "").strip().lower())
    return {"email": invitee["email"], "display_name": invitee["display_name"]}

@bp.get("/events/<int:event_id>/invitations")
@login_required
def list_guests(event_id):
    _own_event(event_id)
    return _guest_list(event_id)


@bp.post("/events/<int:event_id>/invitations")
@login_required
def invite_guest(event_id):
    _own_event(event_id)
    invitee = _find_invitee(require_str(json_body(), "email", max_len=255).lower())

    existing = query_one(
        "SELECT id, status FROM event_invitations WHERE event_id = %s AND invitee_id = %s",
        (event_id, invitee["id"]),
    )
    if existing and existing["status"] != "declined":
        raise ApiError(409, f"{invitee['display_name']} is already invited")
    if existing:
        # Re-inviting someone who declined asks them again.
        execute(
            "UPDATE event_invitations SET status = 'pending', responded_at = NULL, created_at = NOW() WHERE id = %s",
            (existing["id"],),
        )
    else:
        try:
            execute(
                "INSERT INTO event_invitations (event_id, invitee_id) VALUES (%s, %s)",
                (event_id, invitee["id"]),
            )
        except pymysql.err.IntegrityError:
            raise ApiError(409, f"{invitee['display_name']} is already invited")
    commit()
    return _guest_list(event_id), 201


@bp.delete("/events/<int:event_id>/invitations/<int:invitation_id>")
@login_required
def remove_guest(event_id, invitation_id):
    _own_event(event_id)
    deleted = execute(
        "DELETE FROM event_invitations WHERE id = %s AND event_id = %s",
        (invitation_id, event_id),
    )
    if not deleted:
        raise not_found("Invitation")
    commit()
    return _guest_list(event_id)


# --- the invitee's side -----------------------------------------------------

def _received(where, args):
    rows = query(
        f"""SELECT i.id AS invitation_id, i.status, i.created_at AS invited_at,
                   o.display_name AS owner_name, o.email AS owner_email,
                   {", ".join("e." + f.strip() for f in EVENT_FIELDS.split(","))}
            FROM event_invitations i
            JOIN calendar_events e ON e.id = i.event_id
            JOIN users o ON o.id = e.user_id
            WHERE i.invitee_id = %s AND {where}
            ORDER BY e.start_at""",
        (g.user["id"], *args),
    )
    return [_serialize_event(r) for r in rows]


@bp.get("/invitations")
@login_required
def my_invitations():
    """Invitations sent to me. ?status=pending (default), accepted, declined or all."""
    status = request.args.get("status") or "pending"
    if status == "all":
        return _received("TRUE", ())
    if status not in ("pending", *RESPONSES):
        raise bad_request("'status' must be pending, accepted, declined or all")
    return _received("i.status = %s", (status,))


@bp.get("/invitations/count")
@login_required
def pending_count():
    row = query_one(
        "SELECT COUNT(*) AS n FROM event_invitations WHERE invitee_id = %s AND status = 'pending'",
        (g.user["id"],),
    )
    return {"pending": row["n"]}


@bp.post("/invitations/<int:invitation_id>/respond")
@login_required
def respond(invitation_id):
    response = json_body().get("response")
    if response not in RESPONSES:
        raise bad_request("'response' must be accepted or declined")
    updated = query_one(
        "SELECT id FROM event_invitations WHERE id = %s AND invitee_id = %s",
        (invitation_id, g.user["id"]),
    )
    if updated is None:
        raise not_found("Invitation")
    execute(
        "UPDATE event_invitations SET status = %s, responded_at = NOW() WHERE id = %s",
        (response, invitation_id),
    )
    commit()
    return _received("i.id = %s", (invitation_id,))[0]
