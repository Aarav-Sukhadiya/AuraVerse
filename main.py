#!/usr/bin/env python3
"""
Main.py
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

import Search_UI 
import JsonHandler

# ---------------- CONFIGURATION SECTION ----------------

BASE = Path.cwd()
STORAGE_ROOT = BASE / "storage"
DB_PATH = BASE / "file_catalog.sqlite"

CATEGORIES = {
    "image": STORAGE_ROOT / "image",
    "video": STORAGE_ROOT / "video",
    "json":  STORAGE_ROOT / "json",
    "text":  STORAGE_ROOT / "text",
    "audio": STORAGE_ROOT / "audio",
    "pdf":   STORAGE_ROOT / "pdf",
    "other": STORAGE_ROOT / "other",
}

for folder in CATEGORIES.values():
    folder.mkdir(parents=True, exist_ok=True)


# ---------- UTILITY FUNCTIONS ----------

def human_size(num_bytes: int):
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if num_bytes < 1024.0:
            return f"{num_bytes:3.1f} {unit}"
        num_bytes /= 1024.0
    return f"{num_bytes:.1f} PB"


def guess_mime(path: str):
    mime, _ = mimetypes.guess_type(path)
    return mime or "application/octet-stream"


def mime_to_category(mime: str, path: str) -> str:
    if mime.startswith("image/"): return "image"
    if mime.startswith("video/"): return "video"
    if mime.startswith("audio/"): return "audio"
    if mime == "application/json": return "json"
    if mime.startswith("text/"): return "text"
    if mime == "application/pdf": return "pdf"

    ext = Path(path).suffix.lower()
    if ext in (".json",): return "json"
    if ext in (".txt", ".md", ".csv", ".log", ".py"): return "text"
    return "other"


def sanitize_filename(s: str) -> str:
    s = s.strip()
    s = s.replace("/", "_").replace("\\", "_")
    s = re.sub(r"[^\w\-_\. ]+", "", s)
    s = s.replace(" ", "_")
    return s[:200]


def sha256_file(path: Path, chunk_size=65536):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(chunk_size), b""):
            h.update(chunk)
    return h.hexdigest()


# ---------- DATABASE ----------
def upgrade_db():
    cur = DB_CONN.cursor()
    try:
        cur.execute("ALTER TABLE files ADD COLUMN json_keys TEXT;")
    except: pass
    try:
        cur.execute("ALTER TABLE files ADD COLUMN json_preview TEXT;")
    except: pass
    try:
        cur.execute("ALTER TABLE files ADD COLUMN json_search_text TEXT;")
    except: pass
    DB_CONN.commit()

def init_db():
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


DB_CONN = init_db()
upgrade_db()


def insert_record(original_path, stored_path, mime, category, sha256):
    now = datetime.utcnow().isoformat()
    cur = DB_CONN.cursor()
    cur.execute("""
    INSERT INTO files (original_path, stored_path, mime, category, sha256, added_at)
    VALUES (?, ?, ?, ?, ?, ?)
    """, (original_path, stored_path, mime, category, sha256, now))
    DB_CONN.commit()
    return cur.lastrowid


# ---------- FILE PROCESSING ----------

def process_and_store_file(path: str, dry_run=False):
    
    p = Path(path)
    if not p.exists() or not p.is_file():
        return {"status":"error", "reason":"not_found", "path": path}

    mime = guess_mime(path)
    category = mime_to_category(mime, path)

    json_meta = None
    if category == "json":
        data = JsonHandler.process_json_file(path)
        if data["valid"]:
            json_meta = data["metadata"]

    folder = CATEGORIES.get(category, CATEGORIES["other"])
    folder.mkdir(parents=True, exist_ok=True)

    timestamp = int(time.time() * 1000)
    dest_name = f"{timestamp}_{sanitize_filename(p.name)}"
    dest_path = folder / dest_name
    sha = sha256_file(p)

    try:
        shutil.copy2(str(p), str(dest_path))
    except Exception as e:
        return {"status": "error", "reason": str(e), "path": path}

    now = datetime.utcnow().isoformat()
    if json_meta:
        cur = DB_CONN.cursor()
        cur.execute("""
            INSERT INTO files (original_path, stored_path, mime, category, sha256, added_at, 
                                json_keys, json_preview, json_search_text)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            str(path), str(dest_path), mime, category, sha, now,
            json_meta.get("json_keys", ""),
            json_meta.get("json_preview", ""),
            json_meta.get("json_search_text", "")
        ))
        DB_CONN.commit()
        rec_id = cur.lastrowid
    else:
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


# ---------- TKINTER UI ----------

class AppUI:
    def __init__(self, root, dry_run=False):
        self.root = root
        self.dry_run = dry_run
        root.title("MIME-only Store")

        main = ttk.Frame(root, padding=12)
        main.pack(fill="both", expand=True)

        top = ttk.Frame(main)
        top.pack(fill="x")

        ttk.Button(top, text="Select File(s)", command=self.select_files).pack(side="left")
        ttk.Button(top, text="Open Storage Folder", command=self.open_storage).pack(side="left", padx=8)
        ttk.Button(top, text="View DB (last 50)", command=self.show_db).pack(side="left", padx=8)

        # ---- NEW BUTTON ----
        ttk.Button(top, text="Data Retrieval", command=self.open_search_ui).pack(side="left", padx=8)
        # ----------------------

        self.progress = ttk.Label(main, text="Ready")
        self.progress.pack(fill="x", pady=(8, 6))

        cols = ("orig", "mime", "cat", "stored", "status")
        self.tree = ttk.Treeview(main, columns=cols, show="headings", height=16)
        for c, h in zip(cols, ("Original", "MIME", "Category", "Stored Path", "Status")):
            self.tree.heading(c, text=h)
            self.tree.column(c, width=220 if c == "stored" else 120)
        self.tree.pack(fill="both", expand=True)

    # ------- NEW METHOD -------
    def open_search_ui(self):
        self.root.destroy()
        Search_UI.main(back_callback=self.restart_main_ui)
    # --------------------------

    # ------- RESTART MAIN -----
    def restart_main_ui(self):
        import main
        main.main()
    # ---------------------------

    def select_files(self):
        paths = filedialog.askopenfilenames(title="Select files to ingest")
        if not paths:
            return
        threading.Thread(target=self._process_batch, args=(paths,), daemon=True).start()

    def _process_batch(self, paths):
        total = len(paths)
        self.root.after(0, lambda: self.progress.config(text=f"Processing 0/{total}"))

        for i, p in enumerate(paths, start=1):
            self.root.after(
                0,
                lambda p=p: self.tree.insert("", "end", values=(str(p), "", "", "", "processing"))
            )
            res = process_and_store_file(p, dry_run=self.dry_run)
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
            self.root.after(0, lambda i=i, total=total: self.progress.config(text=f"Processing {i}/{total}"))
        self.root.after(0, lambda: self.progress.config(text="Done"))

    def open_storage(self):
        try:
            folder = str(STORAGE_ROOT)
            if os.name == "nt":
                os.startfile(folder)
            elif os.uname().sysname == "Darwin":
                os.system(f"open {folder}")
            else:
                os.system(f'xdg-open "{folder}"')
        except Exception as e:
            messagebox.showerror("Error", f"Cannot open folder: {e}")

    def show_db(self):
        cur = DB_CONN.cursor()
        cur.execute("""
            SELECT id, original_path, stored_path, mime, category, sha256, added_at
            FROM files ORDER BY id DESC LIMIT 50
        """)
        rows = cur.fetchall()

        win = tk.Toplevel(self.root)
        win.title("DB - Last 50")
        txt = tk.Text(win, wrap="none", width=120, height=25)
        txt.pack(fill="both", expand=True)
        for r in rows:
            txt.insert("end", str(r) + "\n")
        txt.config(state="disabled")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    root = tk.Tk()
    app = AppUI(root, dry_run=args.dry_run)
    root.geometry("1100x700")
    root.mainloop()


if __name__ == "__main__":
    main()
