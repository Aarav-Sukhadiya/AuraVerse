import tkinter as tk
from tkinter import messagebox, scrolledtext
import os

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
    results = []
    if not query:
        return results

    query = query.lower()
    for root, dirs, files in os.walk(storage_root):
        for filename in files:
            if query in filename.lower():
                full_path = os.path.join(root, filename)
                file_type = os.path.basename(root)
                results.append({
                    "type": file_type,
                    "source": filename,
                    "path": full_path
                })
    return results


def build_gui(storage_root):
    root = tk.Tk()
    root.title("Storage Retrieval System")
    root.geometry("800x520")

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
    results_display = scrolledtext.ScrolledText(root, height=22, width=90, state=tk.DISABLED)
    results_display.pack(fill="both", expand=True, padx=10, pady=(5, 10))

    # ---------------- SEARCH FUNCTION ----------------
    def perform_search():
        query = query_input.get().strip()
        if not query:
            messagebox.showwarning("Empty Query", "Please enter a search term.")
            status.set("Empty query entered.")
            return

        results_display.config(state=tk.NORMAL)
        results_display.delete("1.0", tk.END)

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

            for i, res in enumerate(results):
                results_display.insert(tk.END, f"--- {i+1} ---\n")
                results_display.insert(tk.END, f"Type: {res['type']}\n")
                results_display.insert(tk.END, f"File: {res['source']}\n")
                results_display.insert(tk.END, f"Path: {res['path']}\n\n")

        except Exception as e:
            messagebox.showerror("Search Error", f"Error: {e}")
            status.set("Search failed.")
        finally:
            results_display.config(state=tk.DISABLED)

    query_input.bind("<Return>", lambda e: perform_search())

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
