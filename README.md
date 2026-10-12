# Termtable

A web app for college students that combines a course schedule planner with a
personal calendar and a gradebook. The backend is Flask, the frontend is React
(Vite), and the database is MySQL.

## Running it

You need Python 3.11+, Node 20+ and MySQL 8.

```bash
# 1. Database + API
cd backend
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
cp .env.example .env          # edit MySQL credentials if needed
.venv/bin/python seed.py      # creates the DB, loads schema.sql, adds sample data
.venv/bin/python run.py       # API on http://127.0.0.1:5001

# 2. Frontend (second terminal)
cd frontend
npm install
npm run dev                   # http://localhost:5173 (proxies /api to :5001)
```

Log in as **demo@student.edu / password123**. Every seeded account uses that
password. The demo student has:

- a committed **Fall 2026** schedule, so the calendar and gradebook have data,
  with grades on work due before the day you ran the seed;
- two **Spring 2027** candidate schedules to compare: "Mornings", which has a
  deliberate time conflict, and "No Fridays";
- a set of personal events, including recurring ones.

`seed.py` drops and rebuilds every table, so re-run it whenever you want a
clean slate. Run the tests with `cd backend && .venv/bin/python -m pytest`.

The API uses port 5001 because macOS's AirPlay Receiver takes port 5000.

## How it fits together

```
backend/
  schema.sql            all tables (the source of truth for the data model)
  seed.py               sample terms, 20 courses, ~100 sections, assignments, reviews
  app/
    auth.py             register / login / logout, session cookie, @login_required
    courses.py          terms, course search, course detail, reviews
    schedules.py        candidate schedules, add/swap/remove sections, commit
    calendar.py         combined calendar feed + personal event CRUD
    gradebook.py        per-class grades and score entry
    enrollment.py       "what is this student taking" = committed schedules
    logic/              pure functions, unit-tested in tests/test_logic.py
      grades.py         weighted grade calculation
      conflicts.py      time-conflict detection
      recurrence.py     recurring-event and class-meeting expansion
frontend/src/
  pages/                Planner, Courses, CourseDetail, Calendar, Grades, GradeDetail, Login
  components/           WeekGrid (planner grid), EventDialog, Stars
  lib/                  date helpers, overlap layout, colors
```

### Data model

- A **course** is the central object. It has **sections** (per term), and each
  section has **meeting_times**: a weekday plus start and end times, tagged
  Lecture or Lab. A course also has **reviews** and **assignments**.
- An **assignment** is defined once per course offering (`course_id` +
  `term_id`). A student's score is a separate **grades** row keyed by
  `(user_id, assignment_id)`. No row means "not graded".
- A **schedule** is a named set of sections (`schedule_sections`) belonging to
  one student and one term. It holds at most one section per course: adding
  another section of the same course swaps it in.
- **Committing** a schedule ("Add classes to calendar") is what makes its
  classes the student's classes for that term. Only one schedule per student
  per term can be committed. The database enforces this with a unique key on a
  generated column (`committed_term_id`).
- **calendar_events** holds the student's own events, including recurrence
  rules (daily, weekly on chosen weekdays, or monthly, with an optional end
  date).

### Class meetings and assignments on the calendar are not copies

When a schedule is committed, nothing is copied into `calendar_events`. The
`/api/calendar` feed builds each requested date range from three sources:

1. the student's own events, with recurrences expanded;
2. class meetings from the committed schedules' `meeting_times`, repeated
   weekly between the term's start and end dates;
3. assignments for those courses that are due in the range, joined with the
   student's grade.

So the assignment shown on the calendar is the same row the gradebook grades,
as the spec requires. Swapping a section, or uncommitting a schedule, changes
the calendar right away and leaves nothing stale behind. Grades survive
uncommitting and come back if the schedule is committed again.

### Grade calculation

`app/logic/grades.py` works in three steps:

1. Each graded assignment becomes a percentage (`score / max_points`).
2. Those percentages are averaged within each category.
3. The categories are combined using homework 20%, quizzes 10%, midterm 30%
   and final 40%.

Categories with nothing graded yet are left out, and the remaining weights are
rescaled. With only homework and quizzes graded, the grade is
`(hw × 0.2 + quiz × 0.1) / 0.3`. A score of 0 counts; a missing score doesn't.
Scores above `max_points` are allowed, for extra credit.

### Privacy and security

- Schedules, events and grades are always queried with the logged-in user's id.
  Another user's ids return 404, and grading a class you aren't taking returns
  403.
- Reviews and the catalog are public reads. Writes require login.
- Passwords are hashed with Werkzeug (scrypt). Sessions are HttpOnly, SameSite=Lax cookies.
- Every write must carry an `X-Requested-With: fetch` header, which a
  cross-site form can't send. This is the CSRF defense.

## Deploying to Render (one Docker web service)

The root Dockerfile builds React and serves it through Flask with Gunicorn.
Frontend routes and `/api` share an origin, preserving session-cookie login.

1. Push the repository to GitHub. Local `.env` files, certificates, private keys,
   virtual environments and build outputs are ignored. Never put credentials in
   tracked source files; ignore rules do not remove files from Git history.
2. Create a Render web service using the Docker runtime, with the repository
   root as the build context and `./Dockerfile` as the Dockerfile path. Leave the
   Docker Command override empty so the image's CMD runs.
3. Set `MYSQL_HOST`, `MYSQL_PORT`, `MYSQL_USER`, `MYSQL_PASSWORD`, and
   `MYSQL_DATABASE=defaultdb` using your Aiven connection details. Set a strong
   random `SECRET_KEY`. The image defaults `SESSION_COOKIE_SECURE=1` for HTTPS.
4. Upload the Aiven CA certificate as a Render secret file named `ca.pem`.
   The image defaults `MYSQL_SSL_CA=/etc/secrets/ca.pem`; the certificate is not
   included in Git or the image. Local development still defaults to `ca.pem`
   in the backend working directory.
5. Set the health check path to `/api/health`. This checks HTTP availability,
   not database connectivity. Verify `/api/terms` and login after deployment.

The server binds to Render's `PORT` environment variable (default 10000).
Do not run `seed.py` during builds or startup: it drops and recreates tables.
The existing Aiven data is reused by deployments.

For local Docker testing from the repository root, use a backend `.env` with
your credentials and mount the certificate read-only:

```bash
docker build -t termtable .
docker run --rm -p 10000:10000 --env-file backend/.env \
  -e PORT=10000 -e SESSION_COOKIE_SECURE=0 \
  -e MYSQL_SSL_CA=/etc/secrets/ca.pem \
  -v "$PWD/backend/ca.pem:/etc/secrets/ca.pem:ro" termtable
```

## Round 4 additions

- **CRN search.** Every section has a CRN (`sections.crn`). The Courses page has a CRN
  box, and results list each section's CRN, professor, meeting times and location.
  The main search box also matches professor names.
- **Calendar sharing.** On any event, invite classmates by the email they registered
  with. Invitees see a count on the Calendar tab and an Invitations panel, can accept
  or decline, and accepted events appear on their calendar (pending ones appear
  dashed). Invitations are in-app only; no email is sent.
- **Homework tracking.** Students add their own assignments (optionally linked to a
  class), mark them complete, or delete them, from the new Assignments page or the
  calendar's "+ Assignment" button. They show on the calendar next to course assignments.
- **Grade tracking.** Per class, a student can switch to their own per-assignment
  weights, set a target grade (the app shows the average needed on remaining work),
  and use what-if mode to try hypothetical scores and made-up assignments without
  saving anything. Logic is in `logic/grades.py` with unit tests.
- **Reviews.** Reviews record which professor the student had. Course pages can filter
  and sort reviews, and the new Reviews page searches by professor, department and course.

### Updating an existing database

`migrate.py` adds the new columns and tables without touching existing data, and it is
safe to run repeatedly. On a brand-new database with no tables, it instead creates
the schema and loads the sample data. The Docker image runs it automatically before Gunicorn starts,
so a Render deploy applies it to the Aiven database on its own. Existing sections get
CRNs; existing reviews show "Professor not specified". Never run `seed.py` against
Aiven, since it wipes every table.

## Known limitations / next steps

- **Editing a recurring event applies to the whole series.** There is no "this
  occurrence only" yet. The clean way to add it is an `event_exceptions` table
  (event_id, original_start, cancelled / overrides) that `expand_event`
  consults.
- Times are naive local times. That's fine for a single-campus app; supporting
  students across time zones would mean storing UTC plus a time zone.
- There is no admin UI for courses and assignments. Add them through `seed.py`
  or SQL, as the spec intends.
- Seat counts are shown but enrollment limits aren't enforced. This is a
  planner, not a registration system.
