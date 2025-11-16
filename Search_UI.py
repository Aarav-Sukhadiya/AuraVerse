# Search_UI.py
"""
Search UI (restored old layout) — uses per-user storage_root and db_path.

Call:
    Search_UI.main(storage_root="/abs/path/to/username_folder", db_path="/abs/path/to/username_database.sqllite")
or
    Search_UI.main(username="admin")  # will call Creating_Storage.setup_user_storage("admin")

If storage_root/db_path are omitted, attempts to resolve using Creating_Storage.setup_user_storage(username).
"""

import os
import re
import sqlite3
import shutil
import subprocess
import sys
import tkinter as tk
from tkinter import messagebox, scrolledtext, filedialog

# try to import Creating_Storage so we can resolve storage if user passes only username
try:
    from Creating_Storage import setup_user_storage
except Exception:
    setup_user_storage = None


def strip_leading_timestamp(name: str) -> str:
    return re.sub(r'^\d+_', '', name)


def create_storage_folders(storage_root: str):
    parts = ["image", "video", "json", "text", "audio", "pdf", "other"]
    os.makedirs(storage_root, exist_ok=True)
    for p in parts:
        os.makedirs(os.path.join(storage_root, p), exist_ok=True)


def db_search(query: str, db_path: str):
    results = []
    if not db_path or not os.path.exists(db_path):
        return results

    try:
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        like_q = f"%{query}%"
        cur.execute("""
            SELECT id, stored_path, mime, category, json_preview, json_search_text
            FROM files
            WHERE stored_path LIKE ?
               OR original_path LIKE ?
               OR json_search_text LIKE ?
            ORDER BY id DESC
            LIMIT 500
        """, (like_q, like_q, like_q))
        rows = cur.fetchall()
    except Exception:
        rows = []
    finally:
        try:
            conn.close()
        except Exception:
            pass

    for r in rows:
        stored_path = r[1]
        category = r[3] or os.path.basename(os.path.dirname(stored_path))
        filename = os.path.basename(stored_path)
        results.append({
            "type": category,
            "source": filename,
            "display": strip_leading_timestamp(filename),
            "path": stored_path,
            "json_preview": r[4] or ""
        })
    return results


def fs_search(query: str, storage_root: str, cat_filter: str = None):
    results = []
    q = (query or "").lower()

    for root, dirs, files in os.walk(storage_root):
        file_type = os.path.basename(root).lower()
        if cat_filter and file_type != cat_filter:
            continue
        for filename in files:
            full_path = os.path.join(root, filename)
            name_lower = filename.lower()
            matches_name = (q and q in name_lower) or (not q)
            matches_text = False
            if q:
                try:
                    if filename.lower().endswith((".txt", ".json", ".md", ".csv", ".log", ".py")):
                        with open(full_path, "r", encoding="utf-8", errors="ignore") as f:
                            txt = f.read(200000)
                            if q in txt.lower():
                                matches_text = True
                except Exception:
                    matches_text = False

            if matches_name or matches_text:
                results.append({
                    "type": file_type,
                    "source": filename,
                    "display": strip_leading_timestamp(filename),
                    "path": full_path
                })
    return results


def retrieve_data(query: str, storage_root: str, db_path: str):
    if not query:
        return []

    cat_filter = None
    q = query.strip()
    if q.lower().startswith("type:"):
        parts = q.split(":", 1)
        if len(parts) > 1:
            cat_filter = parts[1].strip().lower()
            q = ""  # treat as category-only filter

    # try DB first
    try:
        if db_path and os.path.exists(db_path):
            db_results = db_search(q, db_path)
            if db_results:
                if cat_filter:
                    db_results = [r for r in db_results if r["type"].lower() == cat_filter]
                return db_results
    except Exception:
        pass

    # fallback to filesystem
    return fs_search(q, storage_root, cat_filter=cat_filter)


# ---------------- GUI (restored layout) ----------------
def build_gui(storage_root: str, db_path: str, username: str):
    root = tk.Tk()
    root.title(f"Storage Retrieval — {username}")
    root.geometry("920x585")

    # Top search area (old style)
    top = tk.Frame(root, pady=8)
    top.pack(fill="x", padx=10)

    lbl = tk.Label(top, text="Search:", font=("Arial", 14))
    lbl.pack(side="left", padx=(0, 8))

    query_input = tk.Entry(top, font=("Arial", 12), width=48)
    query_input.pack(side="left", fill="x", expand=True)

    search_btn = tk.Button(top, text="Search")
    search_btn.pack(side="left", padx=(8, 0))

    back_btn = tk.Button(top, text="Back")
    back_btn.pack(side="left", padx=(8, 0))

    # Main container: left preview (scrolledtext) + right panel (listbox + buttons)
    container = tk.Frame(root)
    container.pack(fill="both", expand=True, padx=10, pady=(6, 10))

    # Left: large scrolled text for details/preview
    results_display = scrolledtext.ScrolledText(container, height=24, width=70, state=tk.DISABLED)
    results_display.pack(side="left", fill="both", expand=True)

    # Right panel
    right = tk.Frame(container, width=300)
    right.pack(side="right", fill="y", padx=(10, 0))

    tk.Label(right, text="Results:", font=("Arial", 12)).pack(anchor="w")
    # keep selection when focus moves away so <<ListboxSelect>> reliably fires
    results_listbox = tk.Listbox(right, height=22, width=40, exportselection=False)

    results_listbox.pack(fill="y", expand=True, pady=(6, 8))

    # Buttons area on right
    btn_frame = tk.Frame(right)
    btn_frame.pack(fill="x", pady=(6, 0))
    open_btn = tk.Button(btn_frame, text="Open", width=10)
    open_btn.pack(side="left", padx=(0, 6))
    download_btn = tk.Button(btn_frame, text="Download", width=10)
    download_btn.pack(side="left")

    # Status bar at bottom
    status_var = tk.StringVar(value="Ready.")
    status_bar = tk.Label(root, textvariable=status_var, anchor="w")
    status_bar.pack(fill="x", side="bottom", padx=8, pady=(4, 6))

    # closure state
    current_results = []

    # ---------------- actions ----------------
    def show_selected_details(event=None):
    # get index safely
        sel = results_listbox.curselection()
        if not sel:
            # clear preview if nothing selected
            results_display.config(state=tk.NORMAL)
            results_display.delete("1.0", tk.END)
            results_display.config(state=tk.DISABLED)
            return
        idx = sel[0]
        # defensive check
        if idx < 0 or idx >= len(current_results):
            return
        res = current_results[idx]

        results_display.config(state=tk.NORMAL)
        results_display.delete("1.0", tk.END)

        # basic info
        results_display.insert(tk.END, f"Type: {res.get('type')}\n")
        results_display.insert(tk.END, f"File: {res.get('display')}\n")
        results_display.insert(tk.END, f"Stored filename: {res.get('source')}\n")
        results_display.insert(tk.END, f"Path: {res.get('path')}\n\n")

        # prefer DB preview if available
        preview = res.get("json_preview") or ""
        if preview:
            results_display.insert(tk.END, "---- Preview (from DB) ----\n")
            results_display.insert(tk.END, preview[:10000])
            results_display.config(state=tk.DISABLED)
            results_display.yview_moveto(0)
            return

        # fallback: try to read a small text preview from filesystem
        p = res.get("path")
        try:
            if p and os.path.exists(p):
                size = os.path.getsize(p)
                # allow larger text previews (up to 500 KB) but protect from huge files
                if size < 500_000 and p.lower().endswith((".txt", ".json", ".md", ".csv", ".log", ".py", ".xml", ".html")):
                    with open(p, "r", encoding="utf-8", errors="ignore") as f:
                        txt = f.read(100_000)  # read up to 100k chars
                        if txt:
                            results_display.insert(tk.END, "---- Preview (filesystem) ----\n")
                            results_display.insert(tk.END, txt)
                        else:
                            results_display.insert(tk.END, "[No textual preview available in file]\n")
                else:
                    # file too large or not a text extension
                    results_display.insert(tk.END, "[Preview skipped: file is binary or too large]\n")
            else:
                results_display.insert(tk.END, "[File not found on disk]\n")
        except Exception as e:
            # don't crash the UI — show error message in preview pane
            results_display.insert(tk.END, f"[Preview failed: {e}]\n")

        results_display.config(state=tk.DISABLED)
        results_display.yview_moveto(0)


    def open_selected():
        sel = results_listbox.curselection()
        if not sel:
            messagebox.showinfo("No selection", "Please select a result to open.")
            return
        res = current_results[sel[0]]
        path = res["path"]
        try:
            if sys.platform.startswith("win"):
                os.startfile(path)
            elif sys.platform == "darwin":
                subprocess.Popen(["open", path])
            else:
                subprocess.Popen(["xdg-open", path])
        except Exception as e:
            messagebox.showerror("Open failed", f"Could not open file:\n{e}")

    def download_selected():
        sel = results_listbox.curselection()
        if not sel:
            messagebox.showinfo("No selection", "Please select a result to download.")
            return
        res = current_results[sel[0]]
        src = res["path"]
        suggested = res.get("display") or res.get("source")
        dest = filedialog.asksaveasfilename(title="Save file as", initialfile=suggested)
        if not dest:
            return
        try:
            shutil.copy2(src, dest)
            messagebox.showinfo("Downloaded", f"Saved to: {dest}")
        except Exception as e:
            messagebox.showerror("Download failed", f"Could not copy file:\n{e}")

    # ---------------- search ----------------
    def perform_search():
        query = query_input.get().strip()
        if not query:
            messagebox.showwarning("Empty Query", "Please enter a search term.")
            status_var.set("Empty query.")
            return

        status_var.set(f"Searching for '{query}'...")
        root.update_idletasks()

        # retrieve_data expects storage_root and db_path
        results = retrieve_data(query, storage_root, db_path)

        results_listbox.delete(0, tk.END)
        results_display.config(state=tk.NORMAL)
        results_display.delete("1.0", tk.END)
        results_display.config(state=tk.DISABLED)
        current_results.clear()

        if not results:
            status_var.set("No results found.")
            messagebox.showinfo("No results", f"No results found for: '{query}'")
            return

        status_var.set(f"Found {len(results)} result(s).")
        for i, res in enumerate(results):
            label = f"[{res['type']}] {res['display']}"
            results_listbox.insert(tk.END, label)
            current_results.append(res)
            # if there is exactly one result, select it and show its preview automatically
            if len(current_results) == 1:
                results_listbox.selection_clear(0, tk.END)
                results_listbox.selection_set(0)
                # ensure the callback runs (or call it directly)
                show_selected_details()


    # ---------------- bindings ----------------
    search_btn.config(command=perform_search)
    query_input.bind("<Return>", lambda e: perform_search())
    results_listbox.bind("<<ListboxSelect>>", show_selected_details)
    open_btn.config(command=open_selected)
    download_btn.config(command=download_selected)

    # Back button (returns to main if available)
    def go_back():
        # close the Search UI window
        try:
            root.destroy()
        except Exception:
            pass

        # re-open the main UI for the same username
        try:
            import main as main_mod
            # call main with the same username so we don't fall back to admin
            main_mod.main(username=username)
        except Exception as e:
            # show error but don't crash
            messagebox.showerror("Error", f"Failed to return to main UI:\n{e}")


    back_btn.config(command=go_back)

    return root, query_input, status_var, results_listbox, current_results


def main(storage_root: str = None, db_path: str = None, username: str = "admin"):
    # resolve if missing
    if (storage_root is None or db_path is None) and setup_user_storage is not None:
        sr, dbp = setup_user_storage(username)
        storage_root = storage_root or str(sr)
        db_path = db_path or str(dbp)

    # fallback defaults if Creating_Storage not available
    if storage_root is None:
        storage_root = f"{username}_folder"
    if db_path is None:
        db_path = f"{username}_database.sqllite"

    create_storage_folders(storage_root)

    root, query_input, status_var, results_listbox, current_results = build_gui(storage_root, db_path, username)

    status_var.set("Ready.")
    root.mainloop()


if __name__ == "__main__":
    main()
