"""Create the database, load schema.sql and fill it with sample data.

    python seed.py

Everything is regenerated from scratch (schema.sql drops all tables). Data is
deterministic except for which demo grades exist: the demo student has grades
for Fall 2026 work due before today, so the gradebook shows a partial term.

Every seeded account's password is "password123".
Demo login: demo@student.edu
"""

import random
from datetime import date, datetime, time, timedelta
from pathlib import Path

import pymysql
from werkzeug.security import generate_password_hash

from app.config import Config
from app.logic.conflicts import find_conflicts
from migrate import crn_for

SEED_PASSWORD = "password123"
rng = random.Random(2026)

TERMS = [
    ("Fall 2026", date(2026, 8, 31), date(2026, 12, 11)),
    ("Spring 2027", date(2027, 1, 19), date(2027, 5, 7)),
]

# (department, number, title, credits, description, has_lab)
COURSES = [
    ("CS", "101", "Introduction to Programming", 4,
     "First course in programming using Python: variables, control flow, functions, lists, "
     "dictionaries, files and an introduction to object-oriented design.", True),
    ("CS", "201", "Data Structures", 4,
     "Lists, stacks, queues, trees, heaps, hash tables and graphs, with analysis of their "
     "running time. Weekly programming projects in Java.", False),
    ("CS", "240", "Computer Systems", 3,
     "How programs run: C, memory, the compiler toolchain, processes, caching and basic "
     "assembly.", False),
    ("CS", "330", "Algorithms", 3,
     "Design and analysis of algorithms: divide and conquer, greedy methods, dynamic "
     "programming, graph algorithms and NP-completeness.", False),
    ("CS", "350", "Database Systems", 3,
     "Relational modeling, SQL, normalization, indexing, transactions and building "
     "database-backed web applications.", False),
    ("MATH", "121", "Calculus I", 4,
     "Limits, derivatives and their applications, and an introduction to integration.", False),
    ("MATH", "122", "Calculus II", 4,
     "Techniques of integration, sequences and series, parametric curves and polar "
     "coordinates.", False),
    ("MATH", "221", "Linear Algebra", 3,
     "Systems of linear equations, matrices, vector spaces, eigenvalues and applications.", False),
    ("STAT", "200", "Introduction to Statistics", 3,
     "Descriptive statistics, probability, sampling distributions, confidence intervals, "
     "hypothesis testing and regression, using R.", False),
    ("PHYS", "151", "Physics I: Mechanics", 4,
     "Calculus-based kinematics, Newton's laws, energy, momentum, rotation and oscillations. "
     "Includes a weekly lab.", True),
    ("CHEM", "101", "General Chemistry I", 4,
     "Atomic structure, bonding, stoichiometry, gases, thermochemistry and solutions. "
     "Includes a weekly lab.", True),
    ("BIO", "110", "Principles of Biology", 4,
     "Cells, genetics, evolution and ecology, with a weekly laboratory.", True),
    ("ENG", "102", "College Writing", 3,
     "Academic argument and research writing with frequent drafting and peer review.", False),
    ("ENG", "230", "Modern American Literature", 3,
     "American fiction and poetry from 1900 to the present.", False),
    ("HIST", "140", "World History Since 1500", 3,
     "Global connections, empires, revolutions and the making of the modern world.", False),
    ("ECON", "101", "Principles of Microeconomics", 3,
     "Supply and demand, consumer and firm behavior, market structures and market failure.", False),
    ("ECON", "102", "Principles of Macroeconomics", 3,
     "GDP, unemployment, inflation, monetary and fiscal policy, and international trade.", False),
    ("PSYC", "100", "Introduction to Psychology", 3,
     "Survey of psychology: the brain, perception, learning, memory, development, "
     "personality and mental health.", False),
    ("PHIL", "120", "Introduction to Ethics", 3,
     "Major ethical theories and their application to contemporary moral problems.", False),
    ("ART", "105", "Drawing I", 3,
     "Foundations of observational drawing: line, value, perspective and composition.", False),
]

INSTRUCTORS = {
    "CS": ["Dr. Priya Raman", "Dr. Alan Okafor", "Prof. Mei Lin", "Dr. Samuel Ortiz"],
    "MATH": ["Dr. Helen Brooks", "Prof. Ivan Petrov", "Dr. Nadia Haddad"],
    "STAT": ["Dr. Grace Kim", "Dr. Luis Fernandez"],
    "PHYS": ["Dr. Robert Chen", "Prof. Amara Diallo"],
    "CHEM": ["Dr. Sofia Rossi", "Dr. Kenji Watanabe"],
    "BIO": ["Dr. Emily Carter", "Prof. Daniel Mensah"],
    "ENG": ["Prof. Laura Whitman", "Dr. Marcus Bell", "Prof. Ana Torres"],
    "HIST": ["Dr. Thomas Reid", "Prof. Leila Farouk"],
    "ECON": ["Dr. Rachel Goldberg", "Prof. Victor Nguyen"],
    "PSYC": ["Dr. Hannah Schultz", "Dr. Omar Siddiqui"],
    "PHIL": ["Prof. Catherine Doyle"],
    "ART": ["Prof. Julian Moreau"],
}

BUILDINGS = {
    "CS": "Turing Hall", "MATH": "Noether Hall", "STAT": "Noether Hall",
    "PHYS": "Curie Science Center", "CHEM": "Curie Science Center",
    "BIO": "Darwin Life Sciences", "ENG": "Morrison Hall", "HIST": "Morrison Hall",
    "ECON": "Keynes Hall", "PSYC": "James Hall", "PHIL": "Morrison Hall",
    "ART": "Studio Arts Building",
}

MWF, TR, MW = (0, 2, 4), (1, 3), (0, 2)
# (days, start, end)
PATTERNS = (
    [(MWF, time(h), time(h, 50)) for h in (8, 9, 10, 11, 12, 13, 14)]
    + [(TR, s, e) for s, e in (
        (time(8), time(9, 15)), (time(9, 30), time(10, 45)), (time(11), time(12, 15)),
        (time(12, 30), time(13, 45)), (time(14), time(15, 15)), (time(15, 30), time(16, 45)))]
    + [(MW, time(15, 30), time(16, 45)), (MW, time(17), time(18, 15))]
)
LAB_SLOTS = [(d, time(14), time(16, 50)) for d in (1, 2, 3)] + [(4, time(13), time(15, 50))]

REVIEWERS = [
    ("Maya Patel", "maya.patel@student.edu"),
    ("Jordan Lee", "jordan.lee@student.edu"),
    ("Chris Alvarez", "chris.alvarez@student.edu"),
    ("Sam Okonkwo", "sam.okonkwo@student.edu"),
    ("Taylor Nguyen", "taylor.nguyen@student.edu"),
    ("Riley Johnson", "riley.johnson@student.edu"),
    ("Avery Cohen", "avery.cohen@student.edu"),
    ("Jamie Rivera", "jamie.rivera@student.edu"),
    ("Morgan Smith", "morgan.smith@student.edu"),
    ("Casey Brown", "casey.brown@student.edu"),
]

REVIEW_TEXT = {
    5: [
        "One of the best classes I've taken. Lectures were clear and the professor clearly cares "
        "whether you learn the material.",
        "Challenging but completely worth it. Office hours saved me more than once.",
        "Loved it. The assignments actually build on each other, so by the end you can do real things.",
        "Great pacing, fair exams and really helpful TAs. Would take again.",
    ],
    4: [
        "Solid course. The workload is steady, but if you keep up you'll be fine.",
        "Good class overall. A couple of the homeworks were way longer than the others.",
        "Interesting material and a fair grader. Exams were harder than the homework, so practice "
        "with the old exams.",
        "Learned a lot. Lectures could drag sometimes, but the readings filled in the gaps.",
    ],
    3: [
        "It's fine. Some weeks were great and some felt like busywork.",
        "Average. You get out of it what you put in. Start the projects early.",
        "Decent content but disorganized: deadlines moved around a lot.",
    ],
    2: [
        "The material is important but the course is poorly organized. Expect to teach yourself.",
        "Way more work than the credit hours suggest. The exams didn't match the homework.",
    ],
    1: [
        "Frustrating. Feedback on assignments came back weeks late, so it was hard to improve.",
        "I would avoid it if you can. The grading felt arbitrary.",
    ],
}


def connect(database=True):
    return pymysql.connect(
        host=Config.MYSQL_HOST, port=Config.MYSQL_PORT,
        user=Config.MYSQL_USER, password=Config.MYSQL_PASSWORD,
        database=Config.MYSQL_DATABASE if database else None,
        charset="utf8mb4", autocommit=False,
        ssl={"ca": "ca.pem"},
    )


def load_schema(conn):
    sql = (Path(__file__).parent / "schema.sql").read_text()
    # Strip comment lines first (they may contain semicolons), then split.
    code = "\n".join(l for l in sql.splitlines() if not l.strip().startswith("--"))
    with conn.cursor() as cur:
        for statement in code.split(";"):
            if statement.strip():
                cur.execute(statement)
    conn.commit()


def insert(cur, sql, args):
    cur.execute(sql, args)
    return cur.lastrowid


def seed_sections(cur, course_ids, term_ids):
    """Two or three sections per course per term, with distinct meeting patterns."""
    sections = []  # dicts: id, course_id, term_id, meetings
    for (dept, number, _title, _cr, _desc, has_lab), course_id in zip(COURSES, course_ids):
        for term_index, term_id in enumerate(term_ids):
            count = 3 if dept in ("CS", "MATH", "ENG") else 2
            if dept in ("PHIL", "ART"):
                count = 1
            patterns = rng.sample(PATTERNS, count)
            for i, (days, start, end) in enumerate(patterns):
                code = f"{i + 1:03d}"
                instructor = rng.choice(INSTRUCTORS[dept])
                location = f"{BUILDINGS[dept]} {rng.randint(1, 3)}{rng.randint(0, 3)}{rng.randint(1, 9)}"
                section_id = insert(
                    cur,
                    """INSERT INTO sections (course_id, term_id, section_code, instructor, location, capacity)
                       VALUES (%s, %s, %s, %s, %s, %s)""",
                    (course_id, term_id, code, instructor, location, rng.choice((24, 30, 40, 60, 120))),
                )
                cur.execute("UPDATE sections SET crn = %s WHERE id = %s", (crn_for(section_id), section_id))
                meetings = [(d, start, end, "Lecture") for d in days]
                if has_lab:
                    lab_day, lab_start, lab_end = LAB_SLOTS[(i + term_index) % len(LAB_SLOTS)]
                    meetings.append((lab_day, lab_start, lab_end, "Lab"))
                for d, s, e, kind in meetings:
                    cur.execute(
                        """INSERT INTO meeting_times (section_id, day_of_week, start_time, end_time, kind)
                           VALUES (%s, %s, %s, %s, %s)""",
                        (section_id, d, s, e, kind),
                    )
                sections.append({
                    "id": section_id, "course_id": course_id, "term_id": term_id,
                    "dept": dept, "number": number, "instructor": instructor,
                    "meetings": [
                        {"section_id": section_id, "day_of_week": d, "start_time": s, "end_time": e}
                        for d, s, e, _k in meetings
                    ],
                })
    return sections


def seed_assignments(cur, course_ids, terms):
    """Homework roughly every other week, four quizzes, an evening midterm in
    week 8 and a final during the last week of the term."""
    for index, course_id in enumerate(course_ids):
        for term_id, start, end in terms:
            monday = start - timedelta(days=start.weekday())
            hw_day = index % 5  # spread due days across the week
            hw_points = 20 if index % 2 else 50

            def due(week, weekday, at):
                return datetime.combine(monday + timedelta(weeks=week, days=weekday), at)

            rows = []
            for n, week in enumerate(range(1, 14, 2), start=1):
                rows.append((f"Homework {n}", "homework", due(week, hw_day, time(23, 59)), hw_points))
            for n, week in enumerate((3, 6, 10, 13), start=1):
                rows.append((f"Quiz {n}", "quiz", due(week, (hw_day + 2) % 5, time(23, 59)), 10))
            rows.append(("Midterm Exam", "midterm", due(7, 2, time(19, 0)), 100))
            final_day = end - timedelta(days=1 + index % 3)
            while final_day.weekday() > 4:
                final_day -= timedelta(days=1)
            rows.append(("Final Exam", "final", datetime.combine(final_day, time(9 + 3 * (index % 3))), 150))

            cur.executemany(
                """INSERT INTO assignments (course_id, term_id, title, category, due_at, max_points)
                   VALUES (%s, %s, %s, %s, %s, %s)""",
                [(course_id, term_id, title, cat, due_at, pts) for title, cat, due_at, pts in rows],
            )


def seed_reviews(cur, course_ids, reviewer_ids, sections):
    instructors = {}
    for s in sections:
        instructors.setdefault(s["course_id"], set()).add(s["instructor"])
    for course_id in course_ids:
        quality = rng.choice((2, 3, 3, 4, 4, 4, 5))
        for user_id in rng.sample(reviewer_ids, rng.randint(2, 7)):
            rating = max(1, min(5, quality + rng.choice((-1, 0, 0, 0, 1))))
            created = datetime(2026, 5, 1) + timedelta(days=rng.randint(0, 150), hours=rng.randint(8, 22))
            instructor = rng.choice(sorted(instructors[course_id]))
            cur.execute(
                """INSERT INTO reviews (course_id, user_id, rating, instructor, body, created_at, updated_at)
                   VALUES (%s, %s, %s, %s, %s, %s, %s)""",
                (course_id, user_id, rating, instructor, rng.choice(REVIEW_TEXT[rating]), created, created),
            )


def pick_schedule(sections, term_id, wanted, allow=lambda s: True, limit=None):
    """Greedy: for each wanted course code, first section that fits without
    conflict, stopping once `limit` courses are chosen."""
    chosen = []
    for code in wanted:
        if limit and len(chosen) >= limit:
            break
        for s in sections:
            if s["term_id"] != term_id or f"{s['dept']} {s['number']}" != code or not allow(s):
                continue
            meetings = [m for c in chosen for m in c["meetings"]] + s["meetings"]
            if not find_conflicts(meetings):
                chosen.append(s)
                break
    return chosen


def create_schedule(cur, user_id, term_id, name, sections, committed=False):
    schedule_id = insert(
        cur,
        "INSERT INTO schedules (user_id, term_id, name, is_committed) VALUES (%s, %s, %s, %s)",
        (user_id, term_id, name, committed),
    )
    cur.executemany(
        "INSERT INTO schedule_sections (schedule_id, section_id) VALUES (%s, %s)",
        [(schedule_id, s["id"]) for s in sections],
    )
    return schedule_id


def seed_demo_student(cur, demo_id, sections, term_ids):
    fall_id, spring_id = term_ids

    # Fall 2026: committed, so it shows on the calendar and in the gradebook.
    fall = pick_schedule(sections, fall_id, ["CS 201", "MATH 221", "PSYC 100", "ENG 102"])
    create_schedule(cur, demo_id, fall_id, "Fall plan", fall, committed=True)

    # Partial grades: only work already due, so midterms/finals are ungraded.
    today = datetime.now()
    cur.execute(
        f"""SELECT id, max_points FROM assignments
            WHERE term_id = %s AND due_at < %s
              AND course_id IN ({", ".join(["%s"] * len(fall))})""",
        (fall_id, today, *[s["course_id"] for s in fall]),
    )
    grades = []
    for assignment_id, max_points in cur.fetchall():
        pct = min(1.0, max(0.55, rng.gauss(0.87, 0.08)))
        grades.append((demo_id, assignment_id, round(float(max_points) * pct, 1)))
    cur.executemany("INSERT INTO grades (user_id, assignment_id, score) VALUES (%s, %s, %s)", grades)

    # Spring 2027: two candidates to compare, neither committed yet.
    # Preferred courses first, then fallbacks so each candidate gets 4 courses.
    spring_courses = ["CS 330", "CS 350", "STAT 200", "ECON 101", "HIST 140",
                      "PHIL 120", "ENG 230", "ECON 102", "MATH 122", "ART 105"]
    mornings = pick_schedule(
        sections, spring_id, spring_courses, limit=4,
        allow=lambda s: all(m["start_time"] < time(12) for m in s["meetings"]),
    )
    # Deliberately add one overlapping section so the planner's conflict
    # warning has something to show.
    taken = {s["course_id"] for s in mornings}
    overlap = next(
        (s for s in sections
         if s["term_id"] == spring_id and s["course_id"] not in taken
         and find_conflicts([m for c in mornings for m in c["meetings"]] + s["meetings"])),
        None,
    )
    create_schedule(cur, demo_id, spring_id, "Mornings (has a conflict)",
                    mornings + ([overlap] if overlap else []))

    no_friday = pick_schedule(
        sections, spring_id, spring_courses, limit=4,
        allow=lambda s: all(m["day_of_week"] != 4 for m in s["meetings"]),
    )
    create_schedule(cur, demo_id, spring_id, "No Fridays", no_friday)


def seed_events(cur, user_id):
    events = [
        # title, start, end, all_day, color, freq, days, until, location
        ("Robotics Club", datetime(2026, 9, 1, 18), datetime(2026, 9, 1, 19, 30), False, "purple",
         "WEEKLY", "TU", date(2026, 12, 8), "Turing Hall 120"),
        ("Library shift", datetime(2026, 9, 2, 16), datetime(2026, 9, 2, 19), False, "orange",
         "WEEKLY", "MO,WE", date(2026, 12, 9), "Main Library circulation desk"),
        ("Gym", datetime(2026, 9, 5, 9), datetime(2026, 9, 5, 10, 15), False, "green",
         "WEEKLY", "SA", None, "Rec Center"),
        ("Call home", datetime(2026, 9, 6, 19), datetime(2026, 9, 6, 19, 45), False, "teal",
         "WEEKLY", "SU", None, None),
        ("Rent due", datetime(2026, 9, 1), datetime(2026, 9, 2), True, "red",
         "MONTHLY", None, None, None),
        ("Career Fair", datetime(2026, 10, 8, 10), datetime(2026, 10, 8, 14), False, "blue",
         None, None, None, "Student Union Ballroom"),
        ("Fall Break", datetime(2026, 10, 12), datetime(2026, 10, 14), True, "yellow",
         None, None, None, None),
        ("Dentist", datetime(2026, 10, 20, 15, 30), datetime(2026, 10, 20, 16, 30), False, "gray",
         None, None, None, "Campus Health Center"),
        ("Study group: Data Structures", datetime(2026, 9, 3, 20), datetime(2026, 9, 3, 21, 30), False,
         "blue", "WEEKLY", "TH", date(2026, 12, 10), "Turing Hall 2nd floor lounge"),
    ]
    cur.executemany(
        """INSERT INTO calendar_events
               (user_id, title, start_at, end_at, all_day, color,
                recurrence_freq, recurrence_days, recurrence_until, location)
           VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
        [(user_id, *e) for e in events],
    )


def seed_sharing(cur, demo_id, other_ids):
    """Club events other students shared with the demo student: one accepted,
    one waiting for an answer. Also one of the demo's own events shared out."""
    president, member = other_ids[0], other_ids[1]
    meeting_id = insert(
        cur,
        """INSERT INTO calendar_events (user_id, title, start_at, end_at, color, recurrence_freq,
                                        recurrence_days, recurrence_until, location, description)
           VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
        (president, "Coding Club meeting", datetime(2026, 9, 2, 19), datetime(2026, 9, 2, 20), "green",
         "WEEKLY", "WE", date(2026, 12, 9), "Turing Hall 101", "Weekly meeting. Bring a laptop."),
    )
    social_id = insert(
        cur,
        """INSERT INTO calendar_events (user_id, title, start_at, end_at, color, location)
           VALUES (%s, %s, %s, %s, %s, %s)""",
        (president, "Club game night", datetime(2026, 10, 23, 19), datetime(2026, 10, 23, 22), "purple",
         "Student Union, Room 204"),
    )
    cur.execute("SELECT id FROM calendar_events WHERE user_id = %s AND title LIKE 'Study group%%'", (demo_id,))
    study_id = cur.fetchone()[0]
    cur.executemany(
        "INSERT INTO event_invitations (event_id, invitee_id, status, responded_at) VALUES (%s, %s, %s, %s)",
        [
            (meeting_id, demo_id, "accepted", datetime(2026, 8, 30, 12)),
            (social_id, demo_id, "pending", None),
            (study_id, member, "accepted", datetime(2026, 9, 1, 9)),
        ],
    )


def seed_my_assignments(cur, demo_id):
    """A few assignments the demo student added for their Fall classes."""
    cur.execute(
        """SELECT c.id, sc.term_id FROM schedules sc
           JOIN schedule_sections ss ON ss.schedule_id = sc.id
           JOIN sections s ON s.id = ss.section_id JOIN courses c ON c.id = s.course_id
           WHERE sc.user_id = %s AND sc.is_committed ORDER BY c.department, c.number""",
        (demo_id,),
    )
    classes = cur.fetchall()
    rows = [
        ("Read chapter 4", datetime(2026, 9, 21, 9), classes[0], True),
        ("Group project proposal", datetime(2026, 10, 16, 17), classes[1], False),
        ("Lab report draft", datetime(2026, 10, 27, 23, 59), classes[0], False),
        ("Scholarship application", datetime(2026, 11, 1, 12), None, False),
    ]
    cur.executemany(
        """INSERT INTO user_assignments (user_id, course_id, term_id, title, due_at, completed, completed_at)
           VALUES (%s, %s, %s, %s, %s, %s, %s)""",
        [(demo_id, c[0] if c else None, c[1] if c else None, title, due, done, due if done else None)
         for title, due, c, done in rows],
    )


def main():
    # Aiven provisions the database; its user cannot create additional ones.
    conn = connect()
    load_schema(conn)
    password_hash = generate_password_hash(SEED_PASSWORD)

    with conn.cursor() as cur:
        term_ids = [
            insert(cur, "INSERT INTO terms (name, start_date, end_date) VALUES (%s, %s, %s)", t)
            for t in TERMS
        ]
        course_ids = [
            insert(cur,
                   """INSERT INTO courses (department, number, title, credits, description)
                      VALUES (%s, %s, %s, %s, %s)""",
                   (dept, num, title, credits, desc))
            for dept, num, title, credits, desc, _lab in COURSES
        ]
        sections = seed_sections(cur, course_ids, term_ids)
        seed_assignments(cur, course_ids, [(tid, s, e) for tid, (_n, s, e) in zip(term_ids, TERMS)])

        demo_id = insert(
            cur,
            "INSERT INTO users (email, password_hash, display_name) VALUES (%s, %s, %s)",
            ("demo@student.edu", password_hash, "Demo Student"),
        )
        reviewer_ids = [
            insert(cur,
                   "INSERT INTO users (email, password_hash, display_name) VALUES (%s, %s, %s)",
                   (email, password_hash, name))
            for name, email in REVIEWERS
        ]
        seed_reviews(cur, course_ids, reviewer_ids, sections)
        seed_demo_student(cur, demo_id, sections, term_ids)
        seed_events(cur, demo_id)
        seed_sharing(cur, demo_id, reviewer_ids)
        seed_my_assignments(cur, demo_id)

        cur.execute("SELECT COUNT(*) FROM sections")
        n_sections = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM assignments")
        n_assignments = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM reviews")
        n_reviews = cur.fetchone()[0]
    conn.commit()
    conn.close()

    print(f"Seeded {len(TERMS)} terms, {len(COURSES)} courses, {n_sections} sections, "
          f"{n_assignments} assignments, {n_reviews} reviews.")
    print(f"Log in as demo@student.edu / {SEED_PASSWORD}")


if __name__ == "__main__":
    main()
