#!/usr/bin/env python3
"""
Main.py

This program provides a simple Tkinter-based UI that allows users to select files.  
Each selected file is:

1. Analyzed for its MIME type  
2. Mapped to a storage "category" (image, video, text, etc.)
3. Moved into storage/<category>/ with a timestamp prefix  
4. Logged inside a local SQLite database (file_catalog.sqlite)

No classification beyond MIME detection is done.
"""

import argparse
import os
import shutil
import sqlite3
import threading
import time
import hashlib
import mimetypes
from pathlib import Path
from datetime import datetime
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import re

# ---------------- CONFIGURATION SECTION ----------------

# Base working directory (the folder where the program is run)
BASE = Path.cwd()

# Root folder where all categorized files will be stored
STORAGE_ROOT = BASE / "storage"

# SQLite database file path
DB_PATH = BASE / "file_catalog.sqlite"

# Categories and their corresponding folders
# New files will be placed under storage/<category>/
CATEGORIES = {
    "image": STORAGE_ROOT / "image",
    "video": STORAGE_ROOT / "video",
    "json":  STORAGE_ROOT / "json",
    "text":  STORAGE_ROOT / "text",
    "audio": STORAGE_ROOT / "audio",
    "pdf":   STORAGE_ROOT / "pdf",
    "other": STORAGE_ROOT / "other",
}

# Make sure each category folder exists
for folder in CATEGORIES.values():
    folder.mkdir(parents=True, exist_ok=True)

# ---------------- UTILITY FUNCTIONS ----------------

def human_size(num_bytes: int):
    """
    Convert a byte-count into a readable human format (e.g., "23.1 MB").
    """
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if num_bytes < 1024.0:
            return f"{num_bytes:3.1f} {unit}"
        num_bytes /= 1024.0
    return f"{num_bytes:.1f} PB"


def guess_mime(path: str):
    """
    Use Python's built-in mimetypes to guess the MIME type from file extension.
    If unknown, return 'application/octet-stream'.
    """
    mime, _ = mimetypes.guess_type(path)
    return mime or "application/octet-stream"


def mime_to_category(mime: str, path: str) -> str:
    """
    Convert a MIME type to one of our storage categories.

    Example:
        image/png     → "image"
        video/mp4     → "video"
        application/json → "json"
        text/plain    → "text"
    
    If MIME is not known, fall back to extension-based logic.
    """
    if mime.startswith("image/"):
        return "image"
    if mime.startswith("video/"):
        return "video"
    if mime.startswith("audio/"):
        return "audio"
    if mime == "application/json":
        return "json"
    if mime.startswith("text/"):
        return "text"
    if mime == "application/pdf":
        return "pdf"

    # Additional fallback by extension
    ext = Path(path).suffix.lower()
    if ext in (".json",):
        return "json"
    if ext in (".txt", ".md", ".csv", ".log", ".py"):
        return "text"

    return "other"


def sanitize_filename(s: str) -> str:
    """
    Remove problematic characters from the filename.
    Replace spaces with underscores.
    Ensures the filename is filesystem-safe.
    """
    s = s.strip()
    s = s.replace("/", "_").replace("\\", "_")
    s = re.sub(r"[^\w\-_\. ]+", "", s)
    s = s.replace(" ", "_")
    return s[:200]  # Avoid overly long filenames


def sha256_file(path: Path, chunk_size=65536):
    """
    Efficiently compute the SHA-256 hash of a file by streaming it.
    This helps detect duplicates or verify integrity.
    """
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(chunk_size), b""):
            h.update(chunk)
    return h.hexdigest()


# ---------------- DATABASE FUNCTIONS ----------------

def init_db():
    """
    Initialize the SQLite database.
    Creates the 'files' table if it does not already exist.
    """
    conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
    c = conn.cursor()
    c.execute("""
    CREATE TABLE IF NOT EXISTS files (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        original_path TEXT,
        stored_path TEXT,
        mime TEXT,
        category TEXT,
        sha256 TEXT,
        added_at TEXT
    )
    """)
    conn.commit()
    return conn


# Open DB connection once
DB_CONN = init_db()


def insert_record(original_path, stored_path, mime, category, sha256):
    """
    Insert a new file record into the database.
    """
    now = datetime.utcnow().isoformat()
    cur = DB_CONN.cursor()
    cur.execute("""
    INSERT INTO files (original_path, stored_path, mime, category, sha256, added_at)
    VALUES (?, ?, ?, ?, ?, ?)
    """, (original_path, stored_path, mime, category, sha256, now))
    DB_CONN.commit()
    return cur.lastrowid


# ---------------- CORE FILE PROCESSING LOGIC ----------------

def process_and_store_file(path: str, dry_run=False):
    p = Path(path)
    if not p.exists() or not p.is_file():
        return {"status":"error", "reason":"not_found", "path": path}

    mime = guess_mime(path)
    category = mime_to_category(mime, path)

    # Determine destination folder
    folder = CATEGORIES.get(category, CATEGORIES["other"])
    folder.mkdir(parents=True, exist_ok=True)

    # Create unique stored filename
    timestamp = int(time.time() * 1000)
    dest_name = f"{timestamp}_{sanitize_filename(p.name)}"
    dest_path = folder / dest_name

    # Compute SHA256
    sha = sha256_file(p)

    # Dry-run (simulate only)
    if dry_run:
        return {
            "status": "dry-run",
            "original": str(p),
            "mime": mime,
            "category": category,
            "stored_path": str(dest_path),
            "sha256": sha
        }

    # ------ COPY INSTEAD OF MOVE ------
    try:
        shutil.copy2(str(p), str(dest_path))   # Copy file, preserve metadata
    except Exception as e:
        return {"status": "error", "reason": str(e), "path": path}

    # Insert into DB
    rec_id = insert_record(str(path), str(dest_path), mime, category, sha)

    return {
        "status": "copied",
        "id": rec_id,
        "original": str(path),
        "stored_path": str(dest_path),
        "mime": mime,
        "category": category,
        "sha256": sha
    }



# ---------------- TKINTER UI CODE ----------------

class AppUI:
    """
    GUI class that handles:
    - File selection
    - Showing status
    - Showing processing results in a table
    - Viewing storage folder
    - Viewing DB contents
    """

    def __init__(self, root, dry_run=False):
        self.root = root
        self.dry_run = dry_run
        root.title("MIME-only Store")

        main = ttk.Frame(root, padding=12)
        main.pack(fill="both", expand=True)

        # Top-area buttons
        top = ttk.Frame(main)
        top.pack(fill="x")

        ttk.Button(top, text="Select File(s)", command=self.select_files).pack(side="left")
        ttk.Button(top, text="Open Storage Folder", command=self.open_storage).pack(side="left", padx=8)
        ttk.Button(top, text="View DB (last 50)", command=self.show_db).pack(side="left", padx=8)

        # Progress Label
        self.progress = ttk.Label(main, text="Ready")
        self.progress.pack(fill="x", pady=(8, 6))

        # Table for results
        cols = ("orig", "mime", "cat", "stored", "status")
        self.tree = ttk.Treeview(main, columns=cols, show="headings", height=16)
        for c, h in zip(cols, ("Original", "MIME", "Category", "Stored Path", "Status")):
            self.tree.heading(c, text=h)
            self.tree.column(c, width=220 if c == "stored" else 120)
        self.tree.pack(fill="both", expand=True)

    def select_files(self):
        """
        When user clicks 'Select File(s)', show file dialog.
        """
        paths = filedialog.askopenfilenames(title="Select files to ingest")
        if not paths:
            return

        # Do processing in a background thread — prevents UI freezing.
        threading.Thread(target=self._process_batch, args=(paths,), daemon=True).start()

    def _process_batch(self, paths):
        """
        Process multiple files in sequence.
        """
        total = len(paths)
        self.root.after(0, lambda: self.progress.config(text=f"Processing 0/{total}"))

        for i, p in enumerate(paths, start=1):
            # Insert a temporary row showing "processing"
            self.root.after(
                0,
                lambda p=p: self.tree.insert("", "end", values=(str(p), "", "", "", "processing"))
            )

            # Process actual file
            res = process_and_store_file(p, dry_run=self.dry_run)

            # Update last inserted row with real data
            children = self.tree.get_children()
            if children:
                last = children[-1]
                mime = res.get("mime", "")
                cat = res.get("category", "")
                stored = res.get("stored_path", "")
                status = res.get("status")
                self.root.after(
                    0,
                    lambda iid=last, v=(str(p), mime, cat, stored, status): self.tree.item(iid, values=v)
                )

            # Update progress text
            self.root.after(0, lambda i=i, total=total: self.progress.config(text=f"Processing {i}/{total}"))

        self.root.after(0, lambda: self.progress.config(text="Done"))

    def open_storage(self):
        """
        Open the storage directory in system file explorer.
        """
        try:
            folder = str(STORAGE_ROOT)
            if os.name == "nt":
                os.startfile(folder)
            elif os.uname().sysname == "Darwin":
                os.system(f"open {folder}")
            else:
                os.system(f'xdg-open "{folder}"')
        except Exception as e:
            messagebox.showerror("Error", f"Cannot open storage folder: {e}")

    def show_db(self):
        """
        Display last 50 records from the SQLite DB.
        """
        cur = DB_CONN.cursor()
        cur.execute("""
            SELECT id, original_path, stored_path, mime, category, sha256, added_at
            FROM files ORDER BY id DESC LIMIT 50
        """)
        rows = cur.fetchall()

        # Simple popup to show DB contents
        win = tk.Toplevel(self.root)
        win.title("DB - Last 50")
        txt = tk.Text(win, wrap="none", width=120, height=25)
        txt.pack(fill="both", expand=True)
        for r in rows:
            txt.insert("end", str(r) + "\n")
        txt.config(state="disabled")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true",
                        help="Don't move files; only simulate actions")
    args = parser.parse_args()

    root = tk.Tk()
    app = AppUI(root, dry_run=args.dry_run)
    root.geometry("1100x700")
    root.mainloop()


if __name__ == "__main__":
    main()
