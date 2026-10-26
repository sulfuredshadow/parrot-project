from pathlib import Path
import sqlite3

speech_db = Path("/Parrot/saved_db")

def load_db():
    conn = sqlite3.connect("saved_tts.db")
    cursor = conn.cursor()
    cursor.execute("""
          CREATE TABLE IF NOT EXISTS parrot_db (
              frase TEXT PRIMARY KEY,
              repeticiones INTEGER DEFAULT 1,
              ultima_vez TIMESTAMP
          )
      """)
    conn.commit()
    conn.close()
