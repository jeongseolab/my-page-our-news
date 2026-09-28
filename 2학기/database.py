import sqlite3

DB_NAME = "memo.db"


def get_conn():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row      # 딕셔너리처럼 쓰게 해줌
    return conn


def init_db():
    conn = get_conn()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS memos (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            title        TEXT NOT NULL,
            content      TEXT NOT NULL,
            created_at   TEXT,
            likes        INTEGER NOT NULL DEFAULT 0,
            owner_token  TEXT
        )
    """)

    # 예전에 만든 memo.db 에 없는 칸은 여기서 채워 넣는다
    columns = [row["name"] for row in conn.execute("PRAGMA table_info(memos)")]
    if "created_at" not in columns:
        conn.execute("ALTER TABLE memos ADD COLUMN created_at TEXT")
    if "likes" not in columns:
        conn.execute("ALTER TABLE memos ADD COLUMN likes INTEGER NOT NULL DEFAULT 0")
    # 누가 쓴 포스트잇인지 표시. 이 칸이 비어 있는(= 이 기능 전에 쓴) 메모는 아무도 못 뗀다
    if "owner_token" not in columns:
        conn.execute("ALTER TABLE memos ADD COLUMN owner_token TEXT")

    conn.commit()
    conn.close()
