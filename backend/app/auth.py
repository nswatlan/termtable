import re
from functools import wraps

import pymysql
from flask import Blueprint, g, session
from werkzeug.security import check_password_hash, generate_password_hash

from .db import commit, execute, query_one
from .errors import ApiError, bad_request, json_body, require_str

bp = Blueprint("auth", __name__)

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        user_id = session.get("user_id")
        if user_id is None:
            raise ApiError(401, "Please log in")
        user = query_one("SELECT id, email, display_name FROM users WHERE id = %s", (user_id,))
        if user is None:
            session.clear()
            raise ApiError(401, "Please log in")
        g.user = user
        return view(*args, **kwargs)
    return wrapped


@bp.post("/auth/register")
def register():
    data = json_body()
    email = require_str(data, "email", max_len=255).lower()
    password = require_str(data, "password", max_len=200)
    display_name = require_str(data, "display_name", max_len=100)
    if not EMAIL_RE.match(email):
        raise bad_request("Enter a valid email address")
    if len(password) < 8:
        raise bad_request("Password must be at least 8 characters")

    try:
        user_id = execute(
            "INSERT INTO users (email, password_hash, display_name) VALUES (%s, %s, %s)",
            (email, generate_password_hash(password), display_name),
        )
    except pymysql.err.IntegrityError:
        raise ApiError(409, "An account with that email already exists")
    commit()

    session.clear()
    session["user_id"] = user_id
    return {"id": user_id, "email": email, "display_name": display_name}, 201


@bp.post("/auth/login")
def login():
    data = json_body()
    email = require_str(data, "email").lower()
    password = require_str(data, "password")
    user = query_one("SELECT * FROM users WHERE email = %s", (email,))
    if user is None or not check_password_hash(user["password_hash"], password):
        raise ApiError(401, "Incorrect email or password")
    session.clear()
    session["user_id"] = user["id"]
    return {"id": user["id"], "email": user["email"], "display_name": user["display_name"]}


@bp.post("/auth/logout")
def logout():
    session.clear()
    return {"ok": True}


@bp.get("/auth/me")
@login_required
def me():
    return g.user
