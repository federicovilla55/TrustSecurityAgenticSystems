import sqlite3
import logging
from enum import Enum
from pathlib import Path
from dataclasses import asdict, is_dataclass
from datetime import datetime
import json

DATABASE_PATH = Path('database.db')

def init_database():
    db = get_database()

    db.execute(
        """
        CREATE TABLE IF NOT EXISTS events_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_type TEXT,
            agent TEXT,
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

        cursor.execute("DROP TABLE IF EXISTS events_log;")
        cursor.execute("DROP TABLE IF EXISTS users;")
        cursor.execute("DROP TABLE IF EXISTS user_data;")

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

async def log_event(event_type: str, source: str, data: object):
    db = get_database()

    def serialize(obj):
        if isinstance(obj, Enum):
            return obj.value
        if is_dataclass(obj):
            return serialize(asdict(obj))
        if isinstance(obj, (list, tuple)):
            return [serialize(item) for item in obj]
        if isinstance(obj, dict):
            return {k: serialize(v) for k, v in obj.items()}
        if hasattr(obj, 'isoformat'):
            return obj.isoformat()
        return str(obj)

    try:

        db.execute(
            """INSERT INTO events_log 
            (event_type, agent, timestamp, data)
            VALUES (?, ?, ?, ?)""",
            (
                event_type,
                source,
                datetime.now().isoformat(),
                json.dumps(serialize(data), indent=2)
            )
        )
        db.commit()
    finally:
        db.close()
