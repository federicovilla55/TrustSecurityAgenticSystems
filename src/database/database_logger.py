import sqlite3
import logging
from pathlib import Path
from dataclasses import asdict

DATABASE_PATH = Path('database.db')

class DatabaseLogger(logging.Handler):
    def __init__(self) -> None:
        super().__init__()
        self.db_conn = sqlite3.connect(DATABASE_PATH)
        self._create_table()

    def _create_table(self) -> None:
        self.db_conn.execute(
            """
            CREATE TABLE IF NOT EXISTS events_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_type TEXT,
                timestamp TEXT,
                data JSON
            )
            """
        )

        self.db_conn.commit()

    def emit(self, record : logging.LogRecord) -> None:
        try:
            event = record.msg
            data = asdict(event)
            self.db_conn.execute(
                "INSERT INTO events_log (event_type, timestamp, data) VALUES (?, ?, ?)",
                (data["event_type"], data.get("timestamp"), str(data))
            )
            self.db_conn.commit()
        except Exception as e:
            print(f'Exception occurred: {e}')
            self.handleError(record)

def init_database():
    db = sqlite3.connect(DATABASE_PATH)

    db.execute(
        """
        CREATE TABLE IF NOT EXISTS events_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_type TEXT,
            timestamp TEXT,
            data JSON
        )
        """
    )

    db.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            username TEXT PRIMARY KEY,
            hashed_password TEXT NOT NULL
        )
        """
    )

    db.execute(
        """
        CREATE TABLE IF NOT EXISTS user_data (
            username TEXT PRIMARY KEY,
            public_information TEXT,
            private_information TEXT,
            policies TEXT,
            FOREIGN KEY(username) REFERENCES users(username)
        )
        """
   )



def get_database():
    return sqlite3.connect(DATABASE_PATH)

def create_user(db, username: str, hashed_password: str):
    cursor = db.cursor()
    cursor.execute(
        "INSERT INTO users (username, hashed_password) VALUES (?, ?)",
        (username, hashed_password)
    )
    cursor.execute(
        "INSERT INTO user_data (username) VALUES (?)",
        (username,)
    )
    db.commit()

def clear_database() -> None:
    db = get_database()
    try:
        cursor = db.cursor()

        cursor.execute("DELETE FROM events_log;")
        cursor.execute("DELETE FROM users;")
        cursor.execute("DELETE FROM user_data;")

        db.commit()
    except Exception as e:
        print(f"Error clearing users database: {e}")
    finally:
        db.close()

def close_database() -> None:
    try:
        db = get_database()
        db.close()
    except Exception as e:
        print(f"Error closing database: {e}")

def get_user(db, username: str):
    cursor = db.cursor()
    cursor.execute(
        """SELECT u.username, u.hashed_password, 
            d.public_information, d.private_information, d.policies
         FROM users u
         LEFT JOIN user_data d ON u.username = d.username
         WHERE u.username = ?""",
        (username,)
    )
    return cursor.fetchone()
