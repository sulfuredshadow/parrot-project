import sqlite3
from pathlib import Path
import time

def init_db(data_dir: Path):
    data_dir.mkdir(parents=True, exist_ok=True)
    db_path = data_dir / "parrot.db"
    conn = sqlite3.connect(db_path)
    conn.execute(
        """CREATE TABLE IF NOT EXISTS phrases (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            text TEXT,
            path TEXT NOT NULL,
            times_heard INTEGER NOT NULL DEFAULT 1,
            times_played INTEGER NOT NULL DEFAULT 0,
            created_at REAL NOT NULL,
            last_heard REAL NOT NULL)"""
    )
    conn.commit()
    return conn

def prune_db(conn, data_dir: Path, max_clips: int):
    n = conn.execute("SELECT COUNT(*) FROM phrases").fetchone()[0]
    if n <= max_clips:
        return
    rows = conn.execute(
        "SELECT id, path FROM phrases ORDER BY times_heard ASC, last_heard ASC LIMIT ?",
        (n - max_clips,),
    ).fetchall()
    for pid, path in rows:
        Path(path).unlink(missing_ok=True)
        conn.execute("DELETE FROM phrases WHERE id=?", (pid,))
    conn.commit()
