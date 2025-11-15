# Search_UI.py  -- updated to add Download / Open buttons for search results
import tkinter as tk
from tkinter import messagebox, scrolledtext, filedialog
import os
import shutil
import JsonHandler
import sys
import subprocess

DEFAULT_STORAGE_ROOT = "storage"


def create_storage_folders(storage_root=DEFAULT_STORAGE_ROOT):
    folders_to_create = [
        os.path.join(storage_root, "image"),
        os.path.join(storage_root, "video"),
        os.path.join(storage_root, "json"),
        os.path.join(storage_root, "other"),
        os.path.join(storage_root, "audio"),
        os.path.join(storage_root, "pdf"),
        os.path.join(storage_root, "text")
    ]
    os.makedirs(storage_root, exist_ok=True)
    for p in folders_to_create:
        os.makedirs(p, exist_ok=True)


def retrieve_data(query, storage_root=DEFAULT_STORAGE_ROOT):
    """
    Search the storage tree for files matching `query`.
    Supports:
      - plain substring search in filename
      - searching extracted text for text/json files via JsonHandler.extract_text_from_any_file
      - simple category filter using "type:<category>" (e.g. "type:image")
    """
    results = []
    if not query:
        return results

    q = query.strip().lower()

    # category filter support
    cat_filter = None
    if q.startswith("type:"):
        cat_filter = q.split(":", 1)[1].strip()
        # if it's just a type filter and nothing else, return all files of that type
        q = ""

    for root, dirs, files in os.walk(storage_root):
        file_type = os.path.basename(root).lower()  # folder name as category
        if cat_filter and file_type != cat_filter:
            continue

        for filename in files:
            full_path = os.path.join(root, filename)
            name_lower = filename.lower()

            matches_name = (q and q in name_lower) or (not q)  # if q empty after type:, then match all in that category
            matches_text = False
            try:
                # safe: extract_text_from_any_file returns "" on error
                extracted = JsonHandler.extract_text_from_any_file(full_path) or ""
                matches_text = (q and q in extracted.lower())
            except Exception:
                matches_text = False

            if matches_name or matches_text:
                results.append({
                    "type": file_type,
                    "source": filename,
                    "path": full_path
                })

    return results


def build_gui(storage_root):
    root = tk.Tk()
    root.title("Storage Retrieval System")
    root.geometry("880x560")

    # Status bar
    log_frame = tk.Frame(root, pady=2)
    log_frame.pack(fill="x", side=tk.BOTTOM, padx=10)
    status = tk.StringVar(value="Ready.")
    tk.Label(log_frame, textvariable=status, anchor="w").pack(fill="x")

    # ---------------- SEARCH FRAME ----------------
    search_frame = tk.Frame(root, pady=10)
    search_frame.pack(fill="x", padx=10, side=tk.TOP)

    tk.Label(search_frame, text="Search:", font=("Arial", 14)).pack(side=tk.LEFT, padx=(0, 10))

    query_input = tk.Entry(search_frame, font=("Arial", 12), width=40)
    query_input.pack(side=tk.LEFT, fill="x", expand=True)

    return root, status, query_input, search_frame


def main(storage_root=DEFAULT_STORAGE_ROOT, back_callback=None):

    create_storage_folders(storage_root)
    root, status, query_input, search_frame = build_gui(storage_root)

    # ---------------- RESULT DISPLAY ----------------
    # Left: textual details, Right: list of results + action buttons
    container = tk.Frame(root)
    container.pack(fill="both", expand=True, padx=10, pady=(5, 10))

    results_display = scrolledtext.ScrolledText(container, height=20, width=60, state=tk.DISABLED)
    results_display.pack(side=tk.LEFT, fill="both", expand=True)

    right_panel = tk.Frame(container, width=260)
    right_panel.pack(side=tk.RIGHT, fill="y", padx=(10, 0))

    tk.Label(right_panel, text="Results:", font=("Arial", 12)).pack(anchor="w")
    results_listbox = tk.Listbox(right_panel, height=18, width=40)
    results_listbox.pack(fill="y", expand=True, pady=(4, 6), side=tk.TOP)

    # store last search results so listbox index maps to dict
    current_results = []

    # ---------------- ACTIONS ----------------
    def show_selected_details(event=None):
        sel = results_listbox.curselection()
        if not sel:
            return
        idx = sel[0]
        res = current_results[idx]
        results_display.config(state=tk.NORMAL)
        results_display.delete("1.0", tk.END)
        results_display.insert(tk.END, f"Type: {res['type']}\n")
        results_display.insert(tk.END, f"File: {res['source']}\n")
        results_display.insert(tk.END, f"Path: {res['path']}\n\n")
        # attempt to include a small text preview for text/json files
        try:
            preview = JsonHandler.extract_text_from_any_file(res['path']) or ""
            if preview:
                preview_snip = preview[:10_000]  # avoid giant dumps
                results_display.insert(tk.END, "---- Preview ----\n")
                results_display.insert(tk.END, preview_snip)
                if len(preview) > len(preview_snip):
                    results_display.insert(tk.END, "\n\n[...preview truncated...]")
        except Exception:
            pass
        results_display.config(state=tk.DISABLED)

    def download_selected():
        sel = results_listbox.curselection()
        if not sel:
            messagebox.showinfo("No selection", "Please select a result to download.")
            return
        idx = sel[0]
        res = current_results[idx]
        src = res['path']
        suggested_name = res['source']

        dest = filedialog.asksaveasfilename(title="Save file as", initialfile=suggested_name)
        if not dest:
            return
        try:
            shutil.copy2(src, dest)
            messagebox.showinfo("Downloaded", f"Saved to: {dest}")
        except Exception as e:
            messagebox.showerror("Download failed", f"Could not copy file:\n{e}")

    def open_selected():
        sel = results_listbox.curselection()
        if not sel:
            messagebox.showinfo("No selection", "Please select a result to open.")
            return
        idx = sel[0]
        res = current_results[idx]
        path = res['path']
        try:
            if sys.platform.startswith("win"):
                os.startfile(path)
            elif sys.platform == "darwin":
                subprocess.Popen(["open", path])
            else:
                subprocess.Popen(["xdg-open", path])
        except Exception as e:
            messagebox.showerror("Open failed", f"Could not open file:\n{e}")

    # Buttons for actions
    btn_frame = tk.Frame(right_panel)
    btn_frame.pack(fill="x", pady=(6, 0))

    tk.Button(btn_frame, text="Open", width=10, command=open_selected).pack(side=tk.LEFT, padx=(0, 6))
    tk.Button(btn_frame, text="Download", width=10, command=download_selected).pack(side=tk.LEFT)

    # ---------------- SEARCH FUNCTION ----------------
    def perform_search():
        query = query_input.get().strip()
        if not query:
            messagebox.showwarning("Empty Query", "Please enter a search term.")
            status.set("Empty query entered.")
            return

        results_display.config(state=tk.NORMAL)
        results_display.delete("1.0", tk.END)
        results_listbox.delete(0, tk.END)
        current_results.clear()

        try:
            status.set(f"Searching for '{query}'...")
            root.update_idletasks()
            results = retrieve_data(query, storage_root)

            if not results:
                results_display.insert(tk.END, f"No results found for: '{query}'")
                status.set("No results found.")
                results_display.config(state=tk.DISABLED)
                return

            status.set(f"Found {len(results)} result(s).")
            results_display.insert(tk.END, f"Found {len(results)} result(s):\n\n")

            # populate listbox and current_results
            for i, res in enumerate(results):
                label = f"[{res['type']}] {res['source']}"
                results_listbox.insert(tk.END, label)
                current_results.append(res)

                results_display.insert(tk.END, f"--- {i+1} ---\n")
                results_display.insert(tk.END, f"Type: {res['type']}\n")
                results_display.insert(tk.END, f"File: {res['source']}\n")
                results_display.insert(tk.END, f"Path: {res['path']}\n\n")

        except Exception as e:
            messagebox.showerror("Search Error", f"Error: {e}")
            status.set("Search failed.")
        finally:
            results_display.config(state=tk.DISABLED)

    # bind enter key to search
    query_input.bind("<Return>", lambda e: perform_search())
    results_listbox.bind("<<ListboxSelect>>", show_selected_details)

    # ---------------- BUTTONS BESIDE SEARCH BAR ----------------
    tk.Button(
        search_frame, text="Search", command=perform_search,
        font=("Arial", 12), width=10
    ).pack(side=tk.LEFT, padx=10)

    # BACK BUTTON RESTARTS MAIN WINDOW
    def go_back():
        root.destroy()
        try:
            import importlib
            import main as main_mod
            importlib.reload(main_mod)
            main_mod.main()
        except Exception as e:
            print("Failed to restart main.py:", e)

    tk.Button(
        search_frame, text="Back", command=go_back,
        font=("Arial", 12), width=10
    ).pack(side=tk.LEFT)
    # -----------------------------------------------------------

    status.set("Ready.")
    root.mainloop()


if __name__ == "__main__":
    main()
