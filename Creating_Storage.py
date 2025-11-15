# Creating_Storage.py
"""
Creates folder and SQLite database based on a username.
Usage inside project:
    from Creating_Storage import setup_user_storage
    STORAGE_ROOT, DB_PATH = setup_user_storage("admin")
"""

import os
import sqlite3
from pathlib import Path


def setup_user_storage(username: str):
    """
    Creates:
        <username>_folder/
        <username>_database.sqllite
    Also sets up category subfolders and initializes the DB if needed.
    Returns:
        (storage_root_path, db_path)
    """

    # Base paths
    base = Path.cwd()
    storage_root = base / f"{username}_folder"
    db_path = base / f"{username}_database.sqllite"

    # Create main storage folder
    storage_root.mkdir(parents=True, exist_ok=True)

    # Subfolders
    categories = [
        "image", "video", "json",
        "text", "audio", "pdf", "other"
    ]
    for c in categories:
        (storage_root / c).mkdir(parents=True, exist_ok=True)

    # Initialize SQLite database
    conn = sqlite3.connect(str(db_path))
    c = conn.cursor()

    c.execute("""
    CREATE TABLE IF NOT EXISTS files (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        original_path TEXT,
        stored_path TEXT,
        mime TEXT,
        category TEXT,
        sha256 TEXT,
        added_at TEXT,
        json_keys TEXT,
        json_preview TEXT,
        json_search_text TEXT
    )
    """)

    conn.commit()
    conn.close()

    return storage_root, db_path


# Allow this file to be run directly
if __name__ == "__main__":
    username = input("Enter username: ").strip() or "admin"
    folder, db = setup_user_storage(username)
    print(f"Storage folder created at: {folder}")
    print(f"Database created at: {db}")
