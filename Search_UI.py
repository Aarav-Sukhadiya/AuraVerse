# Search_UI.py
import tkinter as tk
from tkinter import messagebox, scrolledtext
import json
import os
from pathlib import Path

# --- Backend defaults (can be overridden by main()) ---
DEFAULT_STORAGE_ROOT = "storage"

def create_storage_folders(storage_root=DEFAULT_STORAGE_ROOT):
    """
    Ensures the root storage directory and main subfolders exist.
    """
    folders_to_create = [
        os.path.join(storage_root, "image"),
        os.path.join(storage_root, "video"),
        os.path.join(storage_root, "json"),
        os.path.join(storage_root, "other"),
        os.path.join(storage_root, "audio"),
        os.path.join(storage_root, "pdf"),
        os.path.join(storage_root, "text")
    ]
    try:
        os.makedirs(storage_root, exist_ok=True)
        for path in folders_to_create:
            os.makedirs(path, exist_ok=True)
    except OSError as e:
        print(f"Error creating storage directories: {e}")
        raise

def retrieve_data(query, storage_root=DEFAULT_STORAGE_ROOT):
    """
    Searches the `storage_root` directory for files/folders matching the query.
    Returns a list of result dicts.
    """
    results = []
    if not query:
        return results

    query = query.lower()
    for root, dirs, files in os.walk(storage_root):
        for filename in files:
            if query in filename.lower():
                full_path = os.path.join(root, filename)
                file_type = os.path.basename(root)
                if file_type == storage_root:
                    file_type = "other"
                results.append({
                    "type": file_type,
                    "source": filename,
                    "path": full_path
                })
    return results

def build_gui(storage_root):
    """
    Build the Tk GUI widgets and return the root and some key widgets.
    """
    root = tk.Tk()
    root.title("Storage Retrieval System")
    root.geometry("780x480")

    # Status bar
    log_frame = tk.Frame(root, pady=2)
    log_frame.pack(fill="x", side=tk.BOTTOM, padx=10)
    status = tk.StringVar(value="Ready.")
    tk.Label(log_frame, textvariable=status, anchor="w").pack(fill="x")

    # Search frame
    search_frame = tk.Frame(root, pady=10)
    search_frame.pack(fill="x", padx=10, side=tk.TOP)
    tk.Label(search_frame, text="Search Query:", font=("Arial", 14)).pack(side=tk.LEFT, padx=(0, 10))

    query_input = tk.Entry(search_frame, font=("Arial", 12), width=50)
    query_input.pack(side=tk.LEFT, fill="x", expand=True, ipady=4)

    results_display = scrolledtext.ScrolledText(root, height=20, width=90, state=tk.DISABLED)
    results_display.pack(fill="both", expand=True, padx=10, pady=(5, 10))

    return root, status, query_input, results_display

def main(storage_root=DEFAULT_STORAGE_ROOT):
    """
    Start the Search UI. Call this from other modules: Search_UI.main()
    Optionally pass a different storage_root path.
    """
    # Ensure storage directories exist
    try:
        create_storage_folders(storage_root)
    except Exception as e:
        print(f"Startup error creating storage folders: {e}")
        # Proceeding may still work but warn the user

    root, status, query_input, results_display = build_gui(storage_root)

    def perform_search():
        query = query_input.get().strip()
        if not query:
            messagebox.showwarning("Empty Query", "Please enter a search term.")
            status.set("Search attempted with empty query.")
            return

        results_display.config(state=tk.NORMAL)
        results_display.delete("1.0", tk.END)

        try:
            status.set(f"Searching for '{query}'...")
            root.update_idletasks()
            results = retrieve_data(query, storage_root=storage_root)

            if not results:
                results_display.insert(tk.END, f"No results found for: '{query}'")
                status.set(f"No results found for '{query}'.")
                return

            status.set(f"Found {len(results)} result(s) for '{query}'.")
            results_display.insert(tk.END, f"Found {len(results)} result(s):\n\n")
            for i, res in enumerate(results):
                results_display.insert(tk.END, f"--- Result {i+1} ---\n")
                results_display.insert(tk.END, f"Type: {res.get('type', 'N/A').capitalize()}\n")
                results_display.insert(tk.END, f"File: {res.get('source', 'N/A')}\n")
                results_display.insert(tk.END, f"Path: {res.get('path', 'N/A')}\n\n")

        except Exception as e:
            messagebox.showerror("Search Error", f"An error occurred during search:\n{e}")
            status.set("Search failed with an error.")
        finally:
            results_display.config(state=tk.DISABLED)

    # Bindings and buttons
    query_input.bind("<Return>", lambda event: perform_search())
    search_btn = tk.Button(root.children['!frame2'] if '!frame2' in root.children else root, text="Search", command=perform_search, font=("Arial", 11))
    # Fallback placement if frame not easily accessible (we already packed in build_gui)
    try:
        # try to find the search_frame packed earlier (safe fallback)
        # The button was meant to be placed next to the entry; create a small frame for it:
        # We'll place the button into the search_frame created in build_gui
        # (search_frame is the first frame packed at top, children ordering may vary)
        top_frames = [w for w in root.winfo_children() if isinstance(w, tk.Frame)]
        if top_frames:
            btn_parent = top_frames[0]
            tk.Button(btn_parent, text="Search", command=perform_search, font=("Arial", 11)).pack(side=tk.LEFT, padx=10)
        else:
            # final fallback: pack button at top
            search_btn.pack(side=tk.TOP, padx=10)
    except Exception:
        search_btn.pack(side=tk.TOP, padx=10)

    tk.Label(root, text="Search Results", font=("Arial", 14)).pack(anchor="w", padx=10, pady=(10,0))

    # start GUI loop
    status.set("Ready. Storage folders initialized.")
    root.mainloop()

if __name__ == "__main__":
    # default behavior when executed directly
    main()
