import tkinter as tk
from tkinter import messagebox, scrolledtext
import json
import os

# --- Backend Configuration ---
STORAGE_ROOT = "storage"

def create_storage_folders():
    """
    Ensures the root storage directory and main subfolders exist.
    This prevents the app from crashing if the folders are missing.
    """
    folders_to_create = [
        os.path.join(STORAGE_ROOT, "images"),
        os.path.join(STORAGE_ROOT, "videos"),
        os.path.join(STORAGE_ROOT, "json"),
        os.path.join(STORAGE_ROOT, "other")
    ]
    try:
        # Ensure root exists first
        os.makedirs(STORAGE_ROOT, exist_ok=True) 
        # Then create subfolders
        for path in folders_to_create:
            os.makedirs(path, exist_ok=True)
    except OSError as e:
        print(f"Error creating storage directories: {e}")
        # This will be caught by the startup check
        raise

def retrieve_data(query):
    """
    Searches the 'storage' directory for files/folders matching the query.
    This performs a real search on your file system.
    """
    print(f"BACKEND: Searching for query: '{query}'")
    
    results = []
    query = query.lower() # Case-insensitive search
    
    # Walk through the entire storage directory
    for root, dirs, files in os.walk(STORAGE_ROOT):
        # Check if query matches any file names
        for filename in files:
            if query in filename.lower():
                full_path = os.path.join(root, filename)
                
                # Get the subfolder name (e.g., "images", "json")
                file_type = os.path.basename(root)
                
                # Handle files in the root "storage" folder
                if file_type == STORAGE_ROOT:
                    file_type = "other"
                
                results.append({
                    "type": file_type,
                    "source": filename,
                    "path": full_path
                })
                
    return results

# --- Main Application ---
root = tk.Tk()
root.title("Storage Retrieval System")
root.geometry("780x480") # Made window smaller

# --- Status Bar ---
log_frame = tk.Frame(root, pady=2)
log_frame.pack(fill="x", side=tk.BOTTOM, padx=10)
status = tk.StringVar(value="Ready.")
tk.Label(log_frame, textvariable=status, anchor="w").pack(fill="x")

# --- Retrieval UI ---

def perform_search():
    """Handles the search button click."""
    query = query_input.get().strip()
    if not query:
        messagebox.showwarning("Empty Query", "Please enter a search term.")
        status.set("Search attempted with empty query.")
        return

    # Clear previous results
    results_display.config(state=tk.NORMAL)
    results_display.delete("1.0", tk.END)
    
    try:
        status.set(f"Searching for '{query}'...")
        root.update_idletasks() # Force UI update
        
        # Call the backend retrieval function
        results = retrieve_data(query)
        
        if not results:
            results_display.insert(tk.END, f"No results found for: '{query}'")
            status.set(f"No results found for '{query}'.")
            return

        status.set(f"Found {len(results)} result(s) for '{query}'.")
        
        # Display results
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
        results_display.config(state=tk.DISABLED) # Make results read-only


# --- Layout for Main Window ---
search_frame = tk.Frame(root, pady=10)
search_frame.pack(fill="x", padx=10, side=tk.TOP) # Pack at the top

tk.Label(search_frame, text="Search Query:", font=("Arial", 14)).pack(side=tk.LEFT, padx=(0, 10))

query_input = tk.Entry(search_frame, font=("Arial", 12), width=50)
query_input.pack(side=tk.LEFT, fill="x", expand=True, ipady=4)

# Bind <Return> key to the search function
query_input.bind("<Return>", lambda event: perform_search())

tk.Button(search_frame, text="Search", command=perform_search, font=("Arial", 11)).pack(side=tk.LEFT, padx=10)

tk.Label(root, text="Search Results", font=("Arial", 14)).pack(anchor="w", padx=10, pady=(10,0))

results_display = scrolledtext.ScrolledText(root, height=20, width=90, state=tk.DISABLED)
results_display.pack(fill="both", expand=True, padx=10, pady=(5, 10))


# --- Start the application ---
# Create folders on startup
try:
    create_storage_folders()
    status.set("Ready. Storage folders initialized.")
except Exception as e:
    status.set("Error: Could not create storage folders.")
    messagebox.showerror("Startup Error", f"Could not create storage folders: {e}\nApplication may not work correctly.")

root.mainloop()