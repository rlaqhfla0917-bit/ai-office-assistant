"""
정형 데이터 저장소 (SQL DB).
담당자(People), 업무(Tasks), 회의(Meetings) 테이블을 관리합니다.
"""
import sqlite3
from contextlib import contextmanager
from datetime import datetime

from config import DB_PATH

SCHEMA = """
CREATE TABLE IF NOT EXISTS people (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    emp_no TEXT UNIQUE NOT NULL,
    name TEXT NOT NULL,
    role TEXT DEFAULT 'member'  -- 'member' | 'lead' 등 (권한 체크용, 단순화)
);

CREATE TABLE IF NOT EXISTS meetings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT,
    raw_text TEXT,
    summary TEXT,
    created_at TEXT
);

CREATE TABLE IF NOT EXISTS leaves (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    person_id INTEGER NOT NULL,
    leave_date TEXT NOT NULL,   -- YYYY-MM-DD
    leave_type TEXT DEFAULT 'annual',  -- annual | half_am | half_pm | sick
    FOREIGN KEY (person_id) REFERENCES people(id)
);

CREATE TABLE IF NOT EXISTS tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    meeting_id INTEGER,
    raw_assignee_name TEXT,     -- LLM이 뽑아낸 원문 이름 (예: "김대리")
    assignee_id INTEGER,        -- people.id로 정규화된 값 (없으면 NULL = 미해결)
    description TEXT,
    due_date TEXT,
    status TEXT DEFAULT 'pending',  -- pending | done | overdue
    FOREIGN KEY (meeting_id) REFERENCES meetings(id),
    FOREIGN KEY (assignee_id) REFERENCES people(id)
);
"""


@contextmanager
def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db():
    with get_conn() as conn:
        conn.executescript(SCHEMA)


def seed_people(people: list[dict]):
    """데모용 인물 마스터 데이터 삽입. [{"emp_no": "E001", "name": "김철수", "role": "member"}, ...]"""
    with get_conn() as conn:
        for p in people:
            conn.execute(
                "INSERT OR IGNORE INTO people (emp_no, name, role) VALUES (?, ?, ?)",
                (p["emp_no"], p["name"], p.get("role", "member")),
            )


def save_meeting(title: str, raw_text: str, summary: str) -> int:
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO meetings (title, raw_text, summary, created_at) VALUES (?, ?, ?, ?)",
            (title, raw_text, summary, datetime.now().isoformat()),
        )
        return cur.lastrowid


def save_task(meeting_id: int, raw_assignee_name: str, description: str,
              due_date: str | None, assignee_id: int | None) -> int:
    with get_conn() as conn:
        cur = conn.execute(
            """INSERT INTO tasks (meeting_id, raw_assignee_name, assignee_id, description, due_date, status)
               VALUES (?, ?, ?, ?, ?, 'pending')""",
            (meeting_id, raw_assignee_name, assignee_id, description, due_date),
        )
        return cur.lastrowid


def find_person_by_name(name: str) -> sqlite3.Row | None:
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM people WHERE name = ?", (name,)).fetchone()
        return row


def search_candidates_by_partial_name(partial: str) -> list[sqlite3.Row]:
    """정확히 일치하는 사람이 없을 때, 후보를 찾기 위한 부분 일치 검색."""
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM people WHERE name LIKE ?", (f"%{partial}%",)
        ).fetchall()
        return rows


def seed_leaves(leaves: list[dict]):
    """데모용 연차 데이터 삽입. [{"name": "김대리", "leave_date": "2026-10-07", "leave_type": "annual"}, ...]"""
    with get_conn() as conn:
        for lv in leaves:
            person = conn.execute("SELECT id FROM people WHERE name = ?", (lv["name"],)).fetchone()
            if not person:
                continue
            conn.execute(
                "INSERT INTO leaves (person_id, leave_date, leave_type) VALUES (?, ?, ?)",
                (person["id"], lv["leave_date"], lv.get("leave_type", "annual")),
            )


def get_people_on_leave(date: str) -> list[sqlite3.Row]:
    """특정 날짜(YYYY-MM-DD)에 연차/휴가인 사람 목록 조회."""
    query = """
        SELECT people.name, people.emp_no, leaves.leave_type, leaves.leave_date
        FROM leaves
        JOIN people ON leaves.person_id = people.id
        WHERE leaves.leave_date = ?
    """
    with get_conn() as conn:
        return conn.execute(query, (date,)).fetchall()


def get_tasks_due_between(
    start_date: str, end_date: str, person_name: str | None = None
) -> list[sqlite3.Row]:
    """
    마감일이 start_date ~ end_date 사이인 업무 목록 조회.
    person_name이 주어지면 해당 담당자의 업무로 범위를 제한한다.
    """
    query = """
        SELECT tasks.*, people.name AS assignee_name
        FROM tasks
        LEFT JOIN people ON tasks.assignee_id = people.id
        WHERE tasks.due_date BETWEEN ? AND ?
    """
    params: list[str] = [start_date, end_date]
    if person_name:
        query += " AND (people.name = ? OR tasks.raw_assignee_name = ?)"
        params.extend([person_name, person_name])
    query += " ORDER BY tasks.due_date ASC"

    with get_conn() as conn:
        return conn.execute(query, params).fetchall()


def get_task_by_id(task_id: int) -> sqlite3.Row | None:
    """task_id로 업무와 실제 담당자 정보를 함께 조회."""
    query = """
        SELECT tasks.*, people.name AS assignee_name, people.emp_no AS assignee_emp_no
        FROM tasks
        LEFT JOIN people ON tasks.assignee_id = people.id
        WHERE tasks.id = ?
    """
    with get_conn() as conn:
        return conn.execute(query, (task_id,)).fetchone()


def get_tasks_by_person_name(name: str, only_pending: bool = False) -> list[sqlite3.Row]:
    query = """
        SELECT tasks.*, people.name AS assignee_name
        FROM tasks
        LEFT JOIN people ON tasks.assignee_id = people.id
        WHERE (people.name = ? OR tasks.raw_assignee_name = ?)
    """
    if only_pending:
        query += " AND tasks.status != 'done'"
    with get_conn() as conn:
        return conn.execute(query, (name, name)).fetchall()


def update_task_status(task_id: int, status: str) -> bool:
    with get_conn() as conn:
        cur = conn.execute("UPDATE tasks SET status = ? WHERE id = ?", (status, task_id))
        return cur.rowcount > 0
