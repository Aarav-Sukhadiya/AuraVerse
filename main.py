#!/usr/bin/env python3
"""
Main.py
Updated: Adds JsonData button which shows all JSON files stored (preview + download/open).
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
from tkinter import ttk, filedialog, messagebox,scrolledtext
import re
import sys
import subprocess
import json
import tempfile
import Search_UI
import JsonHandler

# --- per-user storage: use Creating_Storage.setup_user_storage(username) ---
# Requires Creating_Storage.py next to this file (it defines setup_user_storage)
try:
    from Creating_Storage import setup_user_storage
except Exception as _e:
    setup_user_storage = None  # will error later if missing

# default username (change as needed). auth_ui provides the same username.
#USERNAME = "admin"

if setup_user_storage is None:
    raise RuntimeError("Creating_Storage.py not found or setup_user_storage missing. Add Creating_Storage.py.")
# call setup to get the exact folder and DB path (will create them if they don't exist)
#STORAGE_ROOT, DB_PATH = setup_user_storage(USERNAME)

# ensure pathlib.Path types (some code expects Path)
from pathlib import Path
#STORAGE_ROOT = Path(STORAGE_ROOT)
#DB_PATH = Path(DB_PATH)

# make sure storage root exists
#STORAGE_ROOT.mkdir(parents=True, exist_ok=True)
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
    if mime and mime.startswith("image/"): return "image"
    if mime and mime.startswith("video/"): return "video"
    if mime and mime.startswith("audio/"): return "audio"
    if mime == "application/json": return "json"
    if mime and mime.startswith("text/"): return "text"
    if mime == "application/pdf": return "pdf"

    ext = Path(path).suffix.lower()
    if ext in (".json",): return "json"
    if ext in (".txt", ".md", ".csv", ".log", ".py",".java",".cpp",".js",".c",".cs"): return "text"
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

def init_db(db_path):
    conn = sqlite3.connect(str(db_path), check_same_thread=False)
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
        if data.get("valid"):
            json_meta = data.get("metadata", None)

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
    def __init__(self, root, storage_root, db_path, username="admin", dry_run=False):
        self.root = root
        self.dry_run = dry_run
        self.username = username
        root.title(f"Add Files — {username}" )

        main = ttk.Frame(root, padding=12)
        main.pack(fill="both", expand=True)

        top = ttk.Frame(main)
        top.pack(fill="x")

        ttk.Button(top, text="Select File(s)", command=self.select_files).pack(side="left")
        ttk.Button(top, text="Open Storage Folder", command=self.open_storage).pack(side="left", padx=8)
        ttk.Button(top, text="View DB (last 50)", command=self.show_db).pack(side="left", padx=8)
        ttk.Button(top, text="Show Database", command=self.show_database).pack(side="left", padx=8)
        # NEW button for JSON data
        ttk.Button(top, text="JsonData", command=self.show_json_data).pack(side="left", padx=8)

        # ---- Data Retrieval Button ----
        ttk.Button(top, text="Data Retrieval", command=self.open_search_ui).pack(side="left", padx=8)
        # ------------------------------

        self.progress = ttk.Label(main, text="Ready")
        self.progress.pack(fill="x", pady=(8, 6))

        cols = ("orig", "mime", "cat", "stored", "status")
        self.tree = ttk.Treeview(main, columns=cols, show="headings", height=16)
        for c, h in zip(cols, ("Original", "MIME", "Category", "Stored Path", "Status")):
            self.tree.heading(c, text=h)
            self.tree.column(c, width=220 if c == "stored" else 120)
        self.tree.pack(fill="both", expand=True)

                # ---------------- JSON input area (paste/type JSON here) ----------------
        lower = ttk.Frame(main, padding=(0, 8))
        lower.pack(fill="both", expand=False, pady=(8, 0))

        ttk.Label(lower, text="Paste JSON here:", font=("Arial", 10)).pack(anchor="w")
        self.json_text = scrolledtext.ScrolledText(lower, height=10, wrap="none")
        self.json_text.pack(fill="both", expand=True, pady=(4, 6))

        btn_row2 = ttk.Frame(lower)
        btn_row2.pack(fill="x")
        ttk.Button(btn_row2, text="Submit JSON", command=self.submit_json_text).pack(side="left")
        # ------------------------------------------------------------------------


    def open_search_ui(self):
        self.root.destroy()
        Search_UI.main(storage_root=str(STORAGE_ROOT), db_path=str(DB_PATH), username=USERNAME)

    def restart_main_ui(self):
        import main
        main.main()

    def select_files(self):
        paths = filedialog.askopenfilenames(
        initialdir=os.path.join(os.path.expanduser("~"), "Desktop"),
        title="Select files to import"
        )


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
            elif sys.platform == "darwin":
                subprocess.Popen(["open", folder])
            else:
                subprocess.Popen(["xdg-open", folder])
        except Exception as e:
            messagebox.showerror("Error", f"Cannot open folder: {e}")
    
    def submit_json_text(self):
        """
        Get JSON from the json_text scrolled text widget, validate it, write to a temp file,
        and call the existing process_and_store_file pipeline. Works with either the
        old process_and_store_file(path, dry_run=...) signature or the newer
        process_and_store_file(path, storage_root, db_path, dry_run=...).
        """
        txt = ""
        try:
            txt = self.json_text.get("1.0", "end").strip()
        except Exception:
            messagebox.showwarning("Error", "Cannot read JSON text area.")
            return

        if not txt:
            messagebox.showwarning("Empty", "Please paste JSON into the text area before submitting.")
            return

        # validate JSON
        try:
            _ = json.loads(txt)
        except Exception as e:
            messagebox.showerror("Invalid JSON", f"JSON parse error:\n{e}")
            return

        # write to temporary file
        try:
            tf = tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".json", encoding="utf-8")
            tf.write(txt)
            tmp_path = tf.name
            tf.close()
        except Exception as e:
            messagebox.showerror("Error", f"Could not create temporary file:\n{e}")
            return

        # Now call process_and_store_file. Try multiple signatures for compatibility.
        res = None
        try:
            # Try the simple signature first (path, dry_run=...)
            res = process_and_store_file(tmp_path, dry_run=getattr(self, "dry_run", False))
        except TypeError:
            # try the newer signature that requires storage_root and db_path
            try:
                # try to get attributes from self (if AppUI was constructed with storage_root/db_path)
                storage_root = getattr(self, "storage_root", None)
                db_path = getattr(self, "db_path", None)

                # if missing, try to resolve via Creating_Storage using default USERNAME if available
                if storage_root is None or db_path is None:
                    try:
                        import Creating_Storage
                        # attempt to use a USERNAME defined in module scope if present, else 'admin'
                        username = getattr(Creating_Storage, "USERNAME", None) or "admin"
                        storage_root, db_path = Creating_Storage.setup_user_storage(username)
                    except Exception:
                        # fallback to look for global STORAGE_ROOT/DB_PATH variables
                        storage_root = globals().get("STORAGE_ROOT", storage_root)
                        db_path = globals().get("DB_PATH", db_path)

                # ensure strings
                storage_root = str(storage_root) if storage_root is not None else None
                db_path = str(db_path) if db_path is not None else None

                # call the function with storage and db if available
                if storage_root and db_path:
                    res = process_and_store_file(tmp_path, storage_root, db_path, dry_run=getattr(self, "dry_run", False))
                else:
                    # last resort: call simple signature (may raise again)
                    res = process_and_store_file(tmp_path, dry_run=getattr(self, "dry_run", False))
            except Exception as e2:
                # capture error
                res = {"status": "error", "reason": f"{e2}"}
        except Exception as e:
            res = {"status": "error", "reason": f"{e}"}

        # remove the temporary source file (we no longer need it; stored copy is inside storage if successful)
        try:
            os.unlink(tmp_path)
        except Exception:
            pass

        # Handle result
        if isinstance(res, dict) and res.get("status") == "copied":
            stored = res.get("stored_path", "")
            messagebox.showinfo("Saved", f"JSON stored: {stored}")
            # insert into treeview for visual feedback
            try:
                self.tree.insert("", "end", values=(
                    res.get("original") or "", res.get("mime") or "", res.get("category") or "",
                    res.get("stored_path") or "", res.get("status") or "copied"
                ))
            except Exception:
                pass
            # clear the text area
            try:
                self.json_text.delete("1.0", "end")
            except Exception:
                pass
        else:
            reason = ""
            if isinstance(res, dict):
                reason = res.get("reason") or res.get("error") or str(res)
            else:
                reason = str(res)
            messagebox.showerror("Store failed", f"Could not save JSON:\n{reason}")


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

    def show_database(self):
        """
        Show ALL rows from the files table in a new window.
        """
        try:
            cur = DB_CONN.cursor()
            cur.execute("SELECT * FROM files ORDER BY id DESC")
            rows = cur.fetchall()
            cols = [d[0] for d in cur.description] if cur.description else []

            win = tk.Toplevel(self.root)
            win.title("Database - All Records")

            # Text widget with horizontal + vertical scrollbars
            frm = ttk.Frame(win)
            frm.pack(fill="both", expand=True)

            txt = tk.Text(frm, wrap="none")
            vsb = ttk.Scrollbar(frm, orient="vertical", command=txt.yview)
            hsb = ttk.Scrollbar(frm, orient="horizontal", command=txt.xview)
            txt.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)

            vsb.pack(side="right", fill="y")
            hsb.pack(side="bottom", fill="x")
            txt.pack(fill="both", expand=True, side="left")

            # header
            header = " | ".join(cols)
            txt.insert("end", header + "\n")
            txt.insert("end", "-" * max(len(header), 80) + "\n")

            for r in rows:
                txt.insert("end", str(r) + "\n")

            txt.config(state="disabled")
        except Exception as e:
            messagebox.showerror("DB Error", f"Could not fetch database records:\n{e}")


    def show_json_data(self):
        """Show all JSON-category rows in a tabular Treeview and allow preview/open/download/export.
        """
        
        
        try:
            cur = DB_CONN.cursor()
            cur.execute("""
                SELECT id, original_path, stored_path, mime, category, json_keys, added_at
                FROM files
                WHERE category = 'json' OR mime = 'application/json'
                ORDER BY id DESC
            """)
            rows = cur.fetchall()
        except Exception as e:
            messagebox.showerror("DB Error", f"Could not query database:\n{e}")
            return

        win = tk.Toplevel(self.root)
        win.title("Json Data (Table)")
        win.geometry("1200x700")

        # Left: table, Right: preview
        left = ttk.Frame(win, padding=(6,6))
        left.pack(side="left", fill="both", expand=True)
        right = ttk.Frame(win, padding=(6,6))
        right.pack(side="right", fill="both", expand=True)

        # Top of left: action buttons
        btn_row = ttk.Frame(left)
        btn_row.pack(fill="x", pady=(0,6))
        refresh_btn = ttk.Button(btn_row, text="Refresh", width=12)
        open_btn = ttk.Button(btn_row, text="Open", width=12)
        download_btn = ttk.Button(btn_row, text="Download", width=12)
        export_btn = ttk.Button(btn_row, text="Export CSV", width=12)
        refresh_btn.pack(side="left", padx=(0,6))
        open_btn.pack(side="left", padx=(0,6))
        download_btn.pack(side="left", padx=(0,6))
        export_btn.pack(side="left", padx=(6,0))

        # Treeview with scrollbar
        cols = ("id", "original_path", "stored_path", "mime", "category", "json_keys", "added_at")
        tree = ttk.Treeview(left, columns=cols, show="headings", selectmode="browse")
        for c in cols:
            tree.heading(c, text=c, anchor="w")
            tree.column(c, width=160 if c != "original_path" and c != "stored_path" else 300, anchor="w")
        vs = ttk.Scrollbar(left, orient="vertical", command=tree.yview)
        hs = ttk.Scrollbar(left, orient="horizontal", command=tree.xview)
        tree.configure(yscrollcommand=vs.set, xscrollcommand=hs.set)
        tree.pack(fill="both", expand=True, side="left")
        vs.pack(side="right", fill="y")
        hs.pack(side="bottom", fill="x")

        # populate rows
        records = []  # keep a list of dicts for actions
        for r in rows:
            rec = {
                "id": r[0],
                "original_path": r[1],
                "stored_path": r[2],
                "mime": r[3],
                "category": r[4],
                "json_keys": r[5] if len(r) > 5 else "",
                "added_at": r[6] if len(r) > 6 else ""
            }
            records.append(rec)
            tree.insert("", "end", values=(
                rec["id"], Path(rec["original_path"]).name, rec["stored_path"], rec["mime"],
                rec["category"], rec["json_keys"], rec["added_at"]
            ))

        # Right: Preview text with scrollbars
        ttk.Label(right, text="Preview:", font=("Arial", 11)).pack(anchor="w")
        preview_txt = tk.Text(right, wrap="none")
        pv_v = ttk.Scrollbar(right, orient="vertical", command=preview_txt.yview)
        pv_h = ttk.Scrollbar(right, orient="horizontal", command=preview_txt.xview)
        preview_txt.configure(yscrollcommand=pv_v.set, xscrollcommand=pv_h.set)
        pv_v.pack(side="right", fill="y")
        pv_h.pack(side="bottom", fill="x")
        preview_txt.pack(fill="both", expand=True, side="left")

        # Helper functions
        def get_selected_index():
            sel = tree.selection()
            if not sel:
                return None
            iid = sel[0]
            vals = tree.item(iid, "values")
            # values layout: id, original_name, stored_path, mime, category, json_keys, added_at
            # find record by id
            try:
                rid = int(vals[0])
            except Exception:
                return None
            for i, rec in enumerate(records):
                if rec["id"] == rid:
                    return i
            return None

        def load_preview_by_index(idx):
            preview_txt.config(state="normal")
            preview_txt.delete("1.0", tk.END)
            if idx is None or idx < 0 or idx >= len(records):
                preview_txt.config(state="disabled")
                return
            rec = records[idx]
            stored = rec.get("stored_path")
            if not stored or not Path(stored).exists():
                preview_txt.insert("end", f"[Missing file on disk] Path: {stored}")
                preview_txt.config(state="disabled")
                return
            # Try to read and pretty-print JSON
            try:
                with open(stored, "r", encoding="utf-8") as f:
                    raw = f.read()
                try:
                    parsed = json.loads(raw)
                    pretty = json.dumps(parsed, indent=2, ensure_ascii=False)
                    preview_txt.insert("end", pretty)
                except Exception:
                    # fallback to JsonHandler.extract_text or raw
                    try:
                        extracted = JsonHandler.extract_text_from_any_file(stored) or raw
                        preview_txt.insert("end", extracted)
                    except Exception:
                        preview_txt.insert("end", raw[:200000])
            except Exception as e:
                preview_txt.insert("end", f"Error reading file: {e}")
            preview_txt.config(state="disabled")

        def on_tree_select(event=None):
            idx = get_selected_index()
            load_preview_by_index(idx)

        def do_open():
            idx = get_selected_index()
            if idx is None:
                messagebox.showinfo("No selection", "Please select a record to open.")
                return
            path = records[idx].get("stored_path")
            if not path or not Path(path).exists():
                messagebox.showerror("Missing file", f"File not found:\n{path}")
                return
            try:
                if sys.platform.startswith("win"):
                    os.startfile(path)
                elif sys.platform == "darwin":
                    subprocess.Popen(["open", path])
                else:
                    subprocess.Popen(["xdg-open", path])
            except Exception as e:
                messagebox.showerror("Open failed", f"Could not open file:\n{e}")

        def do_download():
            idx = get_selected_index()
            if idx is None:
                messagebox.showinfo("No selection", "Please select a record to download.")
                return
            src = records[idx].get("stored_path")
            if not src or not Path(src).exists():
                messagebox.showerror("Missing file", f"Stored file not found:\n{src}")
                return
            suggested = Path(records[idx].get("original_path") or src).name
            dest = filedialog.asksaveasfilename(title="Save JSON as", initialfile=suggested)
            if not dest:
                return
            try:
                shutil.copy2(src, dest)
                messagebox.showinfo("Downloaded", f"Saved to: {dest}")
            except Exception as e:
                messagebox.showerror("Download failed", f"Could not copy file:\n{e}")

        def do_refresh():
            # reload data from DB and repopulate the tree & records
            try:
                cur = DB_CONN.cursor()
                cur.execute("""
                    SELECT id, original_path, stored_path, mime, category, json_keys, added_at
                    FROM files
                    WHERE category = 'json' OR mime = 'application/json'
                    ORDER BY id DESC
                """)
                newrows = cur.fetchall()
            except Exception as e:
                messagebox.showerror("DB Error", f"Could not refresh:\n{e}")
                return
            # clear
            for iid in tree.get_children():
                tree.delete(iid)
            records.clear()
            for r in newrows:
                rec = {
                    "id": r[0],
                    "original_path": r[1],
                    "stored_path": r[2],
                    "mime": r[3],
                    "category": r[4],
                    "json_keys": r[5] if len(r) > 5 else "",
                    "added_at": r[6] if len(r) > 6 else ""
                }
                records.append(rec)
                tree.insert("", "end", values=(
                    rec["id"], Path(rec["original_path"]).name, rec["stored_path"], rec["mime"],
                    rec["category"], rec["json_keys"], rec["added_at"]
                ))
            preview_txt.config(state="normal")
            preview_txt.delete("1.0", tk.END)
            preview_txt.config(state="disabled")

        def do_export_csv():
            if not records:
                messagebox.showinfo("No data", "No JSON records to export.")
                return
            dest = filedialog.asksaveasfilename(title="Export CSV", defaultextension=".csv", filetypes=[("CSV","*.csv")])
            if not dest:
                return
            try:
                import csv
                with open(dest, "w", newline="", encoding="utf-8") as cf:
                    writer = csv.writer(cf)
                    writer.writerow(cols)
                    for rec in records:
                        writer.writerow([rec.get(c, "") for c in cols])
                messagebox.showinfo("Exported", f"CSV exported to: {dest}")
            except Exception as e:
                messagebox.showerror("Export failed", f"Could not export CSV:\n{e}")

        # Bindings
        tree.bind("<<TreeviewSelect>>", on_tree_select)
        tree.bind("<Double-1>", lambda e: do_open())

        refresh_btn.config(command=do_refresh)
        open_btn.config(command=do_open)
        download_btn.config(command=do_download)
        export_btn.config(command=do_export_csv)

        # If there is at least one row, select first and show preview
        if records:
            first_iid = tree.get_children()[0]
            tree.selection_set(first_iid)
            tree.see(first_iid)
            load_preview_by_index(0)



def main(username = "admin"):
    # Resolve per-user storage + db (creates them if missing)
    from Creating_Storage import setup_user_storage

    # get paths (they come back as Path objects from Creating_Storage)
    storage_root, db_path = setup_user_storage(username)

    # convert to pathlib.Path (guarantee)
    storage_root = Path(storage_root)
    db_path = Path(db_path)

    # export these as globals because many functions expect them
    global STORAGE_ROOT, DB_PATH, DB_CONN, CATEGORIES, USERNAME
    STORAGE_ROOT = storage_root
    DB_PATH = db_path
    USERNAME = username

    # build category folder Path objects (use Path / operator)
    CATEGORIES = {
        "image":  STORAGE_ROOT / "image",
        "video":  STORAGE_ROOT / "video",
        "json":   STORAGE_ROOT / "json",
        "text":   STORAGE_ROOT / "text",
        "audio":  STORAGE_ROOT / "audio",
        "pdf":    STORAGE_ROOT / "pdf",
        "other":  STORAGE_ROOT / "other",
    }

    # ensure category folders exist (Creating_Storage already created them,
    # but this is defensive and safe)
    for folder in CATEGORIES.values():
        folder.mkdir(parents=True, exist_ok=True)

    # initialize DB_CONN using the per-user DB path
    DB_CONN = init_db(DB_PATH)

    # perform DB upgrades (if required)
    try:
        upgrade_db()
    except Exception:
        pass

    # CLI args support (keeps existing behaviour)
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    # Start UI
    root = tk.Tk()
    root.title(f"AuraVerse — {username}")

    # create AppUI and pass storage/db info (AppUI will still use globals too)
    app = AppUI(root, storage_root=STORAGE_ROOT, db_path=DB_PATH, username=USERNAME)

    root.geometry("1100x700")
    root.mainloop()



if __name__ == "__main__":
    main()
