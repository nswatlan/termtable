-- Schema for the course planner + calendar app (MySQL 8.0+).
-- Running this file drops and recreates every table.

SET FOREIGN_KEY_CHECKS = 0;
DROP TABLE IF EXISTS grade_weights;
DROP TABLE IF EXISTS grade_settings;
DROP TABLE IF EXISTS user_assignments;
DROP TABLE IF EXISTS event_invitations;
DROP TABLE IF EXISTS grades;
DROP TABLE IF EXISTS calendar_events;
DROP TABLE IF EXISTS schedule_sections;
DROP TABLE IF EXISTS schedules;
DROP TABLE IF EXISTS reviews;
DROP TABLE IF EXISTS assignments;
DROP TABLE IF EXISTS meeting_times;
DROP TABLE IF EXISTS sections;
DROP TABLE IF EXISTS courses;
DROP TABLE IF EXISTS terms;
DROP TABLE IF EXISTS users;
SET FOREIGN_KEY_CHECKS = 1;

CREATE TABLE users (
    id            INT AUTO_INCREMENT PRIMARY KEY,
    email         VARCHAR(255) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    display_name  VARCHAR(100) NOT NULL,
    created_at    DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- A term bounds when class meetings recur on the calendar.
CREATE TABLE terms (
    id         INT AUTO_INCREMENT PRIMARY KEY,
    name       VARCHAR(50) NOT NULL UNIQUE,
    start_date DATE NOT NULL,
    end_date   DATE NOT NULL,
    CONSTRAINT chk_term_dates CHECK (end_date > start_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- The central object: a course has sections, reviews and assignments.
CREATE TABLE courses (
    id          INT AUTO_INCREMENT PRIMARY KEY,
    department  VARCHAR(10)  NOT NULL,
    number      VARCHAR(10)  NOT NULL,
    title       VARCHAR(200) NOT NULL,
    description TEXT,
    credits     TINYINT NOT NULL DEFAULT 3,
    UNIQUE KEY uq_course_code (department, number)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE sections (
    id           INT AUTO_INCREMENT PRIMARY KEY,
    course_id    INT NOT NULL,
    term_id      INT NOT NULL,
    section_code VARCHAR(10)  NOT NULL,
    crn          VARCHAR(10)  NULL,
    instructor   VARCHAR(100) NOT NULL,
    location     VARCHAR(100),
    capacity     INT NOT NULL DEFAULT 30,
    UNIQUE KEY uq_section (course_id, term_id, section_code),
    UNIQUE KEY uq_section_crn (crn),
    CONSTRAINT fk_section_course FOREIGN KEY (course_id) REFERENCES courses(id) ON DELETE CASCADE,
    CONSTRAINT fk_section_term   FOREIGN KEY (term_id)   REFERENCES terms(id)   ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- day_of_week: 0 = Monday ... 6 = Sunday (matches Python's date.weekday()).
CREATE TABLE meeting_times (
    id          INT AUTO_INCREMENT PRIMARY KEY,
    section_id  INT NOT NULL,
    day_of_week TINYINT NOT NULL,
    start_time  TIME NOT NULL,
    end_time    TIME NOT NULL,
    kind        VARCHAR(20) NOT NULL DEFAULT 'Lecture',
    KEY idx_meeting_section (section_id),
    CONSTRAINT chk_meeting_day   CHECK (day_of_week BETWEEN 0 AND 6),
    CONSTRAINT chk_meeting_times CHECK (end_time > start_time),
    CONSTRAINT fk_meeting_section FOREIGN KEY (section_id) REFERENCES sections(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Defined once per course offering (course + term). Every student in the
-- course sees the same row on their calendar and in their gradebook.
CREATE TABLE assignments (
    id          INT AUTO_INCREMENT PRIMARY KEY,
    course_id   INT NOT NULL,
    term_id     INT NOT NULL,
    title       VARCHAR(200) NOT NULL,
    category    ENUM('homework', 'quiz', 'midterm', 'final') NOT NULL,
    due_at      DATETIME NOT NULL,
    max_points  DECIMAL(6,2) NOT NULL DEFAULT 100,
    description TEXT,
    KEY idx_assignment_offering (course_id, term_id),
    KEY idx_assignment_due (due_at),
    CONSTRAINT chk_assignment_points CHECK (max_points > 0),
    CONSTRAINT fk_assignment_course FOREIGN KEY (course_id) REFERENCES courses(id) ON DELETE CASCADE,
    CONSTRAINT fk_assignment_term   FOREIGN KEY (term_id)   REFERENCES terms(id)   ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Public. One review per student per course.
CREATE TABLE reviews (
    id         INT AUTO_INCREMENT PRIMARY KEY,
    course_id  INT NOT NULL,
    user_id    INT NOT NULL,
    rating     TINYINT NOT NULL,
    instructor VARCHAR(100) NULL,
    body       TEXT NOT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY uq_review_once (course_id, user_id),
    KEY idx_review_instructor (instructor),
    CONSTRAINT chk_review_rating CHECK (rating BETWEEN 1 AND 5),
    CONSTRAINT fk_review_course FOREIGN KEY (course_id) REFERENCES courses(id) ON DELETE CASCADE,
    CONSTRAINT fk_review_user   FOREIGN KEY (user_id)   REFERENCES users(id)   ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- A candidate schedule: a named set of sections for one student and term.
-- At most one schedule per student per term can be committed; the committed
-- one is what appears on the calendar and in the gradebook. committed_term_id
-- is NULL for uncommitted schedules, so the unique key only bites on commits.
CREATE TABLE schedules (
    id                INT AUTO_INCREMENT PRIMARY KEY,
    user_id           INT NOT NULL,
    term_id           INT NOT NULL,
    name              VARCHAR(100) NOT NULL,
    is_committed      BOOLEAN NOT NULL DEFAULT FALSE,
    committed_term_id INT AS (IF(is_committed, term_id, NULL)) STORED,
    created_at        DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at        DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY uq_one_committed_per_term (user_id, committed_term_id),
    KEY idx_schedule_user_term (user_id, term_id),
    CONSTRAINT fk_schedule_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    -- No CASCADE: MySQL forbids it on a base column of a stored generated
    -- column (committed_term_id). Deleting a term with schedules is refused.
    CONSTRAINT fk_schedule_term FOREIGN KEY (term_id) REFERENCES terms(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE schedule_sections (
    schedule_id INT NOT NULL,
    section_id  INT NOT NULL,
    PRIMARY KEY (schedule_id, section_id),
    CONSTRAINT fk_ss_schedule FOREIGN KEY (schedule_id) REFERENCES schedules(id) ON DELETE CASCADE,
    CONSTRAINT fk_ss_section  FOREIGN KEY (section_id)  REFERENCES sections(id)  ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- The student's own events. Times are naive local datetimes.
-- All-day events use midnight-to-midnight with an exclusive end_at.
-- Recurrence follows a small subset of RFC 5545: freq, interval, weekly
-- weekdays (e.g. 'MO,WE,FR') and an optional inclusive end date.
CREATE TABLE calendar_events (
    id                  INT AUTO_INCREMENT PRIMARY KEY,
    user_id             INT NOT NULL,
    title               VARCHAR(200) NOT NULL,
    description         TEXT,
    location            VARCHAR(200),
    color               VARCHAR(20) NOT NULL DEFAULT 'blue',
    start_at            DATETIME NOT NULL,
    end_at              DATETIME NOT NULL,
    all_day             BOOLEAN NOT NULL DEFAULT FALSE,
    recurrence_freq     ENUM('DAILY', 'WEEKLY', 'MONTHLY') NULL,
    recurrence_interval TINYINT NOT NULL DEFAULT 1,
    recurrence_days     VARCHAR(30) NULL,
    recurrence_until    DATE NULL,
    created_at          DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at          DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    KEY idx_event_user_start (user_id, start_at),
    CONSTRAINT chk_event_times CHECK (end_at > start_at),
    CONSTRAINT chk_event_interval CHECK (recurrence_interval BETWEEN 1 AND 99),
    CONSTRAINT fk_event_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- A student's score on one assignment. No row means "not graded yet".
CREATE TABLE grades (
    user_id       INT NOT NULL,
    assignment_id INT NOT NULL,
    score         DECIMAL(6,2) NOT NULL,
    updated_at    DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (user_id, assignment_id),
    CONSTRAINT chk_grade_score CHECK (score >= 0),
    CONSTRAINT fk_grade_user       FOREIGN KEY (user_id)       REFERENCES users(id)       ON DELETE CASCADE,
    CONSTRAINT fk_grade_assignment FOREIGN KEY (assignment_id) REFERENCES assignments(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- An invitation to another student's event. The event stays owned by its
-- creator; accepted invitations put the event on the invitee's calendar.
CREATE TABLE event_invitations (
    id           INT AUTO_INCREMENT PRIMARY KEY,
    event_id     INT NOT NULL,
    invitee_id   INT NOT NULL,
    status       ENUM('pending', 'accepted', 'declined') NOT NULL DEFAULT 'pending',
    created_at   DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    responded_at DATETIME NULL,
    UNIQUE KEY uq_invite_once (event_id, invitee_id),
    KEY idx_invite_invitee (invitee_id, status),
    CONSTRAINT fk_invite_event FOREIGN KEY (event_id)   REFERENCES calendar_events(id) ON DELETE CASCADE,
    CONSTRAINT fk_invite_user  FOREIGN KEY (invitee_id) REFERENCES users(id)           ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Homework the student adds themselves (course assignments are shared rows
-- in `assignments`). course_id/term_id are optional and, when set, point at
-- a class the student is taking.
CREATE TABLE user_assignments (
    id           INT AUTO_INCREMENT PRIMARY KEY,
    user_id      INT NOT NULL,
    course_id    INT NULL,
    term_id      INT NULL,
    title        VARCHAR(200) NOT NULL,
    due_at       DATETIME NOT NULL,
    notes        TEXT,
    completed    BOOLEAN NOT NULL DEFAULT FALSE,
    completed_at DATETIME NULL,
    created_at   DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    KEY idx_user_assignment_due (user_id, due_at),
    CONSTRAINT fk_ua_user   FOREIGN KEY (user_id)   REFERENCES users(id)   ON DELETE CASCADE,
    CONSTRAINT fk_ua_course FOREIGN KEY (course_id) REFERENCES courses(id) ON DELETE SET NULL,
    CONSTRAINT fk_ua_term   FOREIGN KEY (term_id)   REFERENCES terms(id)   ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Per-student gradebook settings for one class: which weighting to use
-- ('category' = the fixed category weights, 'custom' = per-assignment
-- weights from grade_weights) and an optional target grade.
CREATE TABLE grade_settings (
    user_id      INT NOT NULL,
    course_id    INT NOT NULL,
    term_id      INT NOT NULL,
    mode         ENUM('category', 'custom') NOT NULL DEFAULT 'category',
    target_grade DECIMAL(5,2) NULL,
    PRIMARY KEY (user_id, course_id, term_id),
    CONSTRAINT fk_gs_user   FOREIGN KEY (user_id)   REFERENCES users(id)   ON DELETE CASCADE,
    CONSTRAINT fk_gs_course FOREIGN KEY (course_id) REFERENCES courses(id) ON DELETE CASCADE,
    CONSTRAINT fk_gs_term   FOREIGN KEY (term_id)   REFERENCES terms(id)   ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- A student's own weight for one assignment, as a share of the course grade
-- (used in 'custom' mode). Missing rows fall back to the category default.
CREATE TABLE grade_weights (
    user_id       INT NOT NULL,
    assignment_id INT NOT NULL,
    weight        DECIMAL(6,3) NOT NULL,
    PRIMARY KEY (user_id, assignment_id),
    CONSTRAINT chk_weight CHECK (weight >= 0),
    CONSTRAINT fk_gw_user       FOREIGN KEY (user_id)       REFERENCES users(id)       ON DELETE CASCADE,
    CONSTRAINT fk_gw_assignment FOREIGN KEY (assignment_id) REFERENCES assignments(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
