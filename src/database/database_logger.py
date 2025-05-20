import sqlite3
import logging
from enum import Enum
from pathlib import Path
from dataclasses import asdict, is_dataclass
from datetime import datetime
import json

DATABASE_PATH = Path('database.db')

def init_database() -> None:
    """
    The function creates the database tables for logging the platform events if they don't exist.
    \nThe tables created are:
    \n- events_log: contains the events logged by the platform (This table is accessed and modified by the central agent, the orchestrator, upon sending or receiving a new message from the runtime).
    \n- users: contains the users registered on the platform and their hashed passwords (this table is accessed and modified by the FastAPI python module).
    \n- user_data: contains the public information, private information and policies of the users (this table is accessed and modified by the users' personal agents).
    :return: None
    """
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

def get_database() -> sqlite3.Connection:
    """
    The function returns the database connection object.
    :return: A sqlite3.Connection object.
    """
    return sqlite3.connect(DATABASE_PATH)

def create_user(db : sqlite3.Connection, username: str, hashed_password: str) -> None:
    """
    The function is called to create a new user in the database given the username and the hashed password.
    :param db: A sqlite3.Connection object.
    :param username: A string containing the username.
    :param hashed_password: A string containing the hashed password.
    :return: None
    """
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
    """
    The function clears the database by deleting all the tables and their contents.
    :return: None
    """
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
    """
    The function retirieves and closes the database connection.
    :return: None
    """
    try:
        db = get_database()
        db.close()
    except Exception as e:
        print(f"Error closing database: {e}")

def get_user(db : sqlite3.Connection, username: str) -> tuple | None:
    """
    The function retrieves the user data from the database given the username.
    :param db: A sqlite3.Connection object.
    :param username: A string containing the username.
    :return: A tuple containing the user data or None if the user is not found.
    """
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

async def log_event(event_type: str, source: str, data: object) -> None:
    """
    The function logs the event specified in the parameters in the database.
    The database is retireved using the get_database() function.
    The event is logged in the events_log table using the following SQL query: "INSERT INTO events_log (event_type, agent, timestamp, data) VALUES (?, ?, ?, ?)".
    The object is serialized to a JSON-serializable format using the serialize() function.
    :param event_type: A string containing the type of the event.
    :param source: A string containing the source of the event.
    :param data: A JSON-serializable object containing the data of the event.
    :return: None
    """
    db = get_database()

    def serialize(obj):
        """
        The function is a recursive serializer called to transform Python objects into JSON-serializable formats.
        :param obj: An object
        :return: JSON-serializable version of the `obj` object.
        """
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
