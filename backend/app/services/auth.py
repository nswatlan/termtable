"""Accounts: registering and checking passwords."""

import re

import pymysql
from werkzeug.security import check_password_hash, generate_password_hash

from ..db import commit
from ..errors import ApiError, bad_request, require_object, require_str
from ..repositories import users as users_repo

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def current_user(user_id):
    return users_repo.find_by_id(user_id)


def register(body):
    data = require_object(body)
    email = require_str(data, "email", max_len=255).lower()
    password = require_str(data, "password", max_len=200)
    display_name = require_str(data, "display_name", max_len=100)
    if not EMAIL_RE.match(email):
        raise bad_request("Enter a valid email address")
    if len(password) < 8:
        raise bad_request("Password must be at least 8 characters")
    try:
        user_id = users_repo.create(email, generate_password_hash(password), display_name)
    except pymysql.err.IntegrityError:
        raise ApiError(409, "An account with that email already exists")
    commit()
    return {"id": user_id, "email": email, "display_name": display_name}


def authenticate(body):
    data = require_object(body)
    email = require_str(data, "email").lower()
    password = require_str(data, "password")
    user = users_repo.find_credentials(email)
    if user is None or not check_password_hash(user["password_hash"], password):
        raise ApiError(401, "Incorrect email or password")
    return {"id": user["id"], "email": user["email"], "display_name": user["display_name"]}
