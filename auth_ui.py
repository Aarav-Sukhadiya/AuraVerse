#!/usr/bin/env python3
"""
auth_ui.py (updated)

Standalone Tkinter-based authentication UI that, upon successful login (or registration),
creates a per-user storage folder and SQLite DB by calling Creating_Storage.setup_user_storage(username).

Place Creating_Storage.py in the same directory (it must define setup_user_storage(username) -> (Path, Path)).
Run:
    python3 auth_ui.py
"""

import os
import sqlite3
import hashlib
import binascii
import secrets
from datetime import datetime
import tkinter as tk
from tkinter import ttk, messagebox
import main

DB_FILENAME = "auth_db.sqllite"

# PBKDF2 parameters
_HASH_NAME = "sha256"
_ITERATIONS = 150_000
_SALT_BYTES = 16
_KEY_BYTES = 32


# ---------- Crypto helpers ----------
def _make_salt() -> bytes:
    return secrets.token_bytes(_SALT_BYTES)


def hash_password(password: str, salt: bytes = None):
    if salt is None:
        salt = _make_salt()
    pwd = password.encode("utf-8")
    dk = hashlib.pbkdf2_hmac(_HASH_NAME, pwd, salt, _ITERATIONS, dklen=_KEY_BYTES)
    return {"salt": binascii.hexlify(salt).decode(), "hash": binascii.hexlify(dk).decode(), "iterations": _ITERATIONS}


def verify_password(password: str, salt_hex: str, hash_hex: str, iterations: int) -> bool:
    salt = binascii.unhexlify(salt_hex)
    expected = binascii.unhexlify(hash_hex)
    dk = hashlib.pbkdf2_hmac(_HASH_NAME, password.encode("utf-8"), salt, iterations, dklen=len(expected))
    return secrets.compare_digest(dk, expected)


# ---------- Database helpers ----------
def _get_conn():
    conn = sqlite3.connect(DB_FILENAME, timeout=5)
    return conn


def init_db():
    conn = _get_conn()
    c = conn.cursor()
    c.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            pwd_hash TEXT NOT NULL,
            pwd_salt TEXT NOT NULL,
            iterations INTEGER NOT NULL,
            created_at TEXT NOT NULL
        )
        """
    )
    conn.commit()
    conn.close()


def create_user(username: str, password: str) -> tuple[bool, str]:
    username = username.strip()
    if not username:
        return False, "Username cannot be empty."
    if len(password) < 6:
        return False, "Password must be at least 6 characters."

    creds = hash_password(password)
    now = datetime.utcnow().isoformat()
    try:
        conn = _get_conn()
        c = conn.cursor()
        c.execute(
            "INSERT INTO users (username, pwd_hash, pwd_salt, iterations, created_at) VALUES (?, ?, ?, ?, ?)",
            (username, creds["hash"], creds["salt"], creds["iterations"], now)
        )
        conn.commit()
        conn.close()
        return True, "User created successfully."
    except sqlite3.IntegrityError:
        return False, "Username already exists."
    except Exception as e:
        return False, f"DB error: {e}"


def authenticate_user(username: str, password: str) -> tuple[bool, str]:
    username = username.strip()
    if not username:
        return False, "Username required."
    try:
        conn = _get_conn()
        c = conn.cursor()
        c.execute("SELECT pwd_hash, pwd_salt, iterations FROM users WHERE username = ?", (username,))
        row = c.fetchone()
        conn.close()
        if not row:
            return False, "User not found."
        pwd_hash, pwd_salt, iterations = row
        ok = verify_password(password, pwd_salt, pwd_hash, iterations)
        if ok:
            return True, "Authentication successful."
        else:
            return False, "Incorrect password."
    except Exception as e:
        return False, f"DB error: {e}"


# ---------- Integration: call Creating_Storage.setup_user_storage ----------
def create_user_storage_safe(username: str):
    """
    Try to import Creating_Storage and call setup_user_storage(username).
    Returns (True, (storage_path, db_path)) on success, or (False, error_message) on failure.
    """
    try:
        # dynamic import so auth_ui can still run if Creating_Storage.py is absent
        import importlib
        cs = importlib.import_module("Creating_Storage")
    except Exception as e:
        return False, f"Creating_Storage import failed: {e}"

    if not hasattr(cs, "setup_user_storage"):
        return False, "Creating_Storage.setup_user_storage not found."

    try:
        storage_root, db_path = cs.setup_user_storage(username)
        return True, (storage_root, db_path)
    except Exception as e:
        return False, f"setup_user_storage failed: {e}"


# ---------- Tkinter UI ----------
class AuthUI:
    def __init__(self, master):
        self.master = master
        master.title("Auth UI")
        master.geometry("480x320")
        master.resizable(False, False)

        self.frame = ttk.Frame(master, padding=16)
        self.frame.pack(fill="both", expand=True)

        ttk.Label(self.frame, text="User Authentication", font=("Segoe UI", 14, "bold")).pack(pady=(0, 10))

        # Username
        ufrm = ttk.Frame(self.frame)
        ufrm.pack(fill="x", pady=(2, 8))
        ttk.Label(ufrm, text="Username:", width=12).pack(side="left")
        self.username_var = tk.StringVar()
        ttk.Entry(ufrm, textvariable=self.username_var, width=34).pack(side="left", padx=(4, 0))

        # Password
        pfrm = ttk.Frame(self.frame)
        pfrm.pack(fill="x", pady=(2, 8))
        ttk.Label(pfrm, text="Password:", width=12).pack(side="left")
        self.password_var = tk.StringVar()
        ttk.Entry(pfrm, textvariable=self.password_var, width=34, show="*").pack(side="left", padx=(4, 0))

        # Buttons
        btnfrm = ttk.Frame(self.frame)
        btnfrm.pack(fill="x", pady=(12, 8))
        ttk.Button(btnfrm, text="Login", command=self.on_login).pack(side="left", expand=True, fill="x")
        ttk.Button(btnfrm, text="Register", command=self.on_register).pack(side="left", expand=True, fill="x", padx=(8, 0))

        # Info / status
        self.status_var = tk.StringVar(value="Enter credentials and choose Login or Register.")
        ttk.Label(self.frame, textvariable=self.status_var, wraplength=440, foreground="#333").pack(pady=(8, 0))

        # Hint
        hint = "Password must be at least 6 chars. This demo stores credentials locally in auth_db.sqllite."
        ttk.Label(self.frame, text=hint, font=("Segoe UI", 8), foreground="#666").pack(side="bottom", pady=(10, 0))

    def on_register(self):
        username = self.username_var.get().strip()
        password = self.password_var.get()
        success, msg = create_user(username, password)
        self.status_var.set(msg)
        if success:
            messagebox.showinfo("Registered", f"User '{username}' created.\nYou can now log in.")
            self.password_var.set("")
        
            

    def on_login(self):
        username = self.username_var.get().strip()
        password = self.password_var.get()

        success, msg = authenticate_user(username, password)
        self.status_var.set(msg)

        if success:
            # 1) Create user storage (folder + DB)
            ok, res = create_user_storage_safe(username)
            if not ok:
                messagebox.showerror("Error", f"Login OK but storage creation failed:\n{res}")
                return

            # 2) Launch main.py for this user
            try:
                import main
                # Close login UI
                self.master.destroy()
                # Start the main UI for this username
                main.main(username=username)

            except Exception as e:
                messagebox.showerror("Launch Error", f"Failed to launch main UI:\n{e}")

            # Clear password for safety
            self.password_var.set("")

        else:
            messagebox.showerror("Authentication failed", msg)



def main():
    init_db()
    root = tk.Tk()
    app = AuthUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
