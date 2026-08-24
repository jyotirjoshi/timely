"""
One-time migration script — adds columns that were added after initial DB creation.
Run this ONCE while the server is STOPPED:

    python migrate.py

Safe to run multiple times (skips columns that already exist).
"""
import sqlite3
import os

DB_PATH = os.getenv("DATABASE_URL", "sqlite:///./timely.db").replace("sqlite:///", "")
DB_PATH = DB_PATH.lstrip("./")
if not os.path.isabs(DB_PATH):
    DB_PATH = os.path.join(os.path.dirname(__file__), DB_PATH)

print(f"Migrating: {DB_PATH}")

conn = sqlite3.connect(DB_PATH)
cur  = conn.cursor()


def add_column_if_missing(table: str, column: str, definition: str):
    cur.execute(f"PRAGMA table_info({table})")
    existing = {row[1] for row in cur.fetchall()}
    if column not in existing:
        print(f"  ADD COLUMN {table}.{column}")
        cur.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")
    else:
        print(f"  OK        {table}.{column} already exists")


# institutions — new columns from Phase 2
add_column_if_missing("institutions", "academic_year_start", "DATE")
add_column_if_missing("institutions", "board",               "VARCHAR DEFAULT ''")

# holidays table (may not exist yet)
cur.execute("""
    CREATE TABLE IF NOT EXISTS holidays (
        id            VARCHAR  PRIMARY KEY,
        institution_id VARCHAR NOT NULL REFERENCES institutions(id),
        date          DATE    NOT NULL,
        name          VARCHAR NOT NULL,
        type          VARCHAR DEFAULT 'national'
    )
""")
print("  OK        holidays table")

# teacher_absences table
cur.execute("""
    CREATE TABLE IF NOT EXISTS teacher_absences (
        id             VARCHAR  PRIMARY KEY,
        institution_id VARCHAR  NOT NULL REFERENCES institutions(id),
        teacher_id     VARCHAR  NOT NULL REFERENCES teachers(id),
        date           DATE     NOT NULL,
        reason         VARCHAR  DEFAULT 'sick leave',
        created_at     DATETIME DEFAULT CURRENT_TIMESTAMP
    )
""")
print("  OK        teacher_absences table")

# substitute_assignments table
cur.execute("""
    CREATE TABLE IF NOT EXISTS substitute_assignments (
        id                    VARCHAR PRIMARY KEY,
        absence_id            VARCHAR NOT NULL REFERENCES teacher_absences(id),
        assignment_id         VARCHAR NOT NULL REFERENCES assignments(id),
        original_teacher_id   VARCHAR NOT NULL,
        substitute_teacher_id VARCHAR NOT NULL,
        confirmed             BOOLEAN DEFAULT 0
    )
""")
print("  OK        substitute_assignments table")

conn.commit()
conn.close()
print("\nMigration complete. Start the server now.")
