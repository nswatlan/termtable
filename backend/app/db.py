"""Thin PyMySQL layer: one connection per request, explicit commits."""

from datetime import time, timedelta

import pymysql
from flask import current_app, g
from pymysql.cursors import DictCursor


def connect(database=True):
    cfg = current_app.config
    return pymysql.connect(
        host=cfg["MYSQL_HOST"],
        port=cfg["MYSQL_PORT"],
        user=cfg["MYSQL_USER"],
        password=cfg["MYSQL_PASSWORD"],
        database=cfg["MYSQL_DATABASE"] if database else None,
        charset="utf8mb4",
        cursorclass=DictCursor,
        autocommit=False,
        ssl={"ca": cfg["MYSQL_SSL_CA"]},
    )


def get_db():
    if "db" not in g:
        g.db = connect()
    return g.db


def close_db(_exc=None):
    db = g.pop("db", None)
    if db is not None:
        # Anything not explicitly committed by a handler is discarded.
        db.rollback()
        db.close()


def query(sql, args=None):
    with get_db().cursor() as cur:
        cur.execute(sql, args)
        # PyMySQL returns () for no rows; Flask would treat a returned tuple
        # as (body, status), so always hand back a list.
        return list(cur.fetchall())


def query_one(sql, args=None):
    with get_db().cursor() as cur:
        cur.execute(sql, args)
        return cur.fetchone()


def execute(sql, args=None):
    """Run a write statement; returns lastrowid (or rowcount if no id)."""
    with get_db().cursor() as cur:
        cur.execute(sql, args)
        return cur.lastrowid or cur.rowcount


def commit():
    get_db().commit()


def in_clause(values):
    """Placeholders for `IN (...)`; callers must ensure values is non-empty."""
    return ", ".join(["%s"] * len(values))


def to_time(value):
    """PyMySQL returns TIME columns as timedelta; convert to datetime.time."""
    if isinstance(value, timedelta):
        total = int(value.total_seconds())
        return time(total // 3600, (total % 3600) // 60, total % 60)
    return value


def init_app(app):
    app.teardown_appcontext(close_db)
