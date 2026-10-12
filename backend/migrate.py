"""Bring an existing database up to the current schema without losing data.

seed.py drops and recreates every table, so it must never run against the
deployed database. This script only *adds* what is missing:

  - sections.crn (backfilled for existing sections)
  - reviews.instructor
  - event_invitations, user_assignments, grade_settings, grade_weights

If the database is brand new (no tables at all), it instead creates every
table and loads the sample data from seed.py, so a fresh Aiven database
works on the first deploy.

It is safe to run any number of times. The Docker image runs it before
starting the server, so a Render deploy applies it automatically. To run it
by hand:  cd backend && .venv/bin/python migrate.py
"""

import re
from pathlib import Path

import pymysql

from app.config import Config

NEW_TABLES = ("event_invitations", "user_assignments", "grade_settings", "grade_weights")


def crn_for(section_id):
    """CRN for a section. Five digits, derived from the id so it is unique."""
    return str(10000 + section_id)


def connect():
    return pymysql.connect(
        host=Config.MYSQL_HOST, port=Config.MYSQL_PORT,
        user=Config.MYSQL_USER, password=Config.MYSQL_PASSWORD,
        database=Config.MYSQL_DATABASE,
        charset="utf8mb4", autocommit=False,
        ssl={"ca": Config.MYSQL_SSL_CA},
    )


def create_statements():
    """CREATE TABLE statements for the new tables, taken from schema.sql so
    the schema file stays the single source of truth."""
    sql = (Path(__file__).parent / "schema.sql").read_text()
    code = "\n".join(l for l in sql.splitlines() if not l.strip().startswith("--"))
    statements = {}
    for statement in code.split(";"):
        match = re.match(r"\s*CREATE TABLE (\w+)", statement)
        if match and match.group(1) in NEW_TABLES:
            statements[match.group(1)] = statement.strip().replace(
                "CREATE TABLE", "CREATE TABLE IF NOT EXISTS", 1)
    return [statements[name] for name in NEW_TABLES]


def column_exists(cur, table, column):
    cur.execute(
        """SELECT 1 FROM information_schema.COLUMNS
           WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = %s AND COLUMN_NAME = %s""",
        (table, column),
    )
    return cur.fetchone() is not None


def index_exists(cur, table, index):
    cur.execute(
        """SELECT 1 FROM information_schema.STATISTICS
           WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = %s AND INDEX_NAME = %s""",
        (table, index),
    )
    return cur.fetchone() is not None


def table_exists(cur, table):
    cur.execute(
        "SELECT 1 FROM information_schema.TABLES WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = %s",
        (table,),
    )
    return cur.fetchone() is not None


def is_empty_database(conn):
    """True only if none of the app's original tables exist yet."""
    with conn.cursor() as cur:
        return not any(table_exists(cur, t) for t in ("users", "courses", "sections", "terms"))


def migrate(conn, log=print):
    with conn.cursor() as cur:
        if not column_exists(cur, "sections", "crn"):
            cur.execute("ALTER TABLE sections ADD COLUMN crn VARCHAR(10) NULL AFTER section_code")
            log("Added sections.crn")
        cur.execute("SELECT id FROM sections WHERE crn IS NULL")
        missing = [row[0] for row in cur.fetchall()]
        if missing:
            cur.executemany("UPDATE sections SET crn = %s WHERE id = %s",
                            [(crn_for(sid), sid) for sid in missing])
            log(f"Assigned CRNs to {len(missing)} sections")
        if not index_exists(cur, "sections", "uq_section_crn"):
            cur.execute("ALTER TABLE sections ADD UNIQUE KEY uq_section_crn (crn)")

        if not column_exists(cur, "reviews", "instructor"):
            cur.execute("ALTER TABLE reviews ADD COLUMN instructor VARCHAR(100) NULL AFTER rating")
            log("Added reviews.instructor")
        if not index_exists(cur, "reviews", "idx_review_instructor"):
            cur.execute("ALTER TABLE reviews ADD KEY idx_review_instructor (instructor)")

        for statement in create_statements():
            cur.execute(statement)
    conn.commit()
    log("Database is up to date.")


if __name__ == "__main__":
    connection = connect()
    try:
        empty = is_empty_database(connection)
        if not empty:
            migrate(connection)
    finally:
        connection.close()
    if empty:
        # Only ever runs on a database with none of the app's tables, so the
        # drop-and-recreate in seed.py cannot destroy anything.
        print("Empty database: creating tables and loading sample data.")
        import seed
        seed.main()
