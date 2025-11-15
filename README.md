Group Members:
    Aarav Sukhadiya(10319) Team Leader
    Kavya Tejani(10690)
    Adit Krishnadas(10402)

🌀 AuraVerse – Multi-User File Intelligence & JSON Management System

  AuraVerse is a multi-user, secure, local-first file management system built in Python.
  It provides authentication, per-user isolated databases, intelligent file ingestion, JSON processing, and a complete search & retrieval UI powered by SQLite text search and fallback filesystem scanning.

  Designed for developers who need a clean, organized, user-specific file cataloging system.


🌐 Overview

  AuraVerse allows multiple users to log in securely and maintain their own isolated file-storage environments.
  Each user gets:
  
  their own private folder
  
  their own private SQLite database
  
  independent file ingestion, JSON storage, and search operations
  
  This ensures data isolation, user-level organization, and a scalable foundation for personal or team use.

🚀 Key Features

  Below is a precise and complete listing of everything the system supports.
  
  🔐 Authentication
  
  A dedicated UI: auth_ui.py
  
  ✔ Secure login system
  ✔ Registration system
  ✔ Password hashing using PBKDF2-HMAC-SHA256
  ✔ Proper salt generation using secrets
  ✔ Usernames must be unique
  ✔ Dynamic window title (Login — <username>)
  ✔ Launches main application after successful login
  ✔ Auto-provisions storage/database for each user at first login
  
  🗂 Per-User Storage Architecture
  
  Each authenticated user automatically gets:
  
  <username>_folder/
  <username>_database.sqllite
  
  
  Inside the folder:
  
  image/
  video/
  json/
  text/
  audio/
  pdf/
  other/
  
  
  ✔ Every file is classified automatically based on MIME type
  ✔ Folders created automatically if missing
  ✔ User environments are completely independent

  🖥 Main Application UI (main.py)
  
  The central dashboard after logging in.
  
  Includes:
  
  ✔ Username-aware window title:
  AuraVerse — <username>
  
  ✔ File Selection
  
  Select multiple files
  
  Automatic processing through ingestion pipeline
  
  Shows progress
  
  Displays result in Treeview
  
  Stores metadata into user's DB
  
  ✔ Storage Folder Access
  
  Open the user’s folder directly from the UI
  
  ✔ Database Tools
  
  View last 50 DB entries
  
  View complete DB
  
  View only JSON entries
  
  View metadata for each entry
  
  ✔ JSON Viewer
  
  Shows: keys, search text, preview text
  
  Can open or download JSON data
  
  📝 JSON Input System (Typed/Pasted JSON Submission)
  
  A dedicated text input area in the lower half of main UI:
  
  ✔ Paste or type raw JSON
  ✔ Validates JSON structure
  ✔ Saves JSON into
  <username>_folder/json/
  ✔ Auto-indexes entry in the user's DB
  ✔ Auto-displays in the Treeview
  ✔ Uses same ingestion pipeline as file imports
  
  📥 File Ingestion Pipeline
  
  Runs whenever a user uploads a file or submits JSON.
  
  ✔ Computes SHA256 checksum
  ✔ Detects MIME type
  ✔ Classifies into:
  
  image
  
  video
  
  json
  
  text
  
  audio
  
  pdf
  
  other
  
  ✔ Auto-generated unique filenames using timestamp prefixes
  ✔ Copies files into the appropriate user folder
  ✔ Inserts detailed metadata into SQLite
  ✔ JSON files get extended metadata
  
  🧠 Metadata & Database Features
  
  The database stores:
  
  Field	Description
  id	unique entry ID
  original_path	original source file path
  stored_path	user storage location
  mime	MIME type
  category	classified category
  sha256	file hash
  added_at	timestamp
  json_keys	extracted keys (for JSON)
  json_preview	short preview
  json_search_text	searchable flattened text
  
  ✔ Full compatibility even with different JSON structures
  ✔ Database automatically created per user
  ✔ SQLite-based efficient text search
  
  🔎 Search & Retrieval UI (Search_UI.py)
  
  A dedicated window for fast searching.
  
  Supports:
  
  ✔ Search by filename
  ✔ Search inside JSON content
  ✔ Search inside text files
  ✔ Search across all categories
  ✔ Filter with:
  type:image, type:json, type:pdf, etc.
  
  UI Features:
  
  ✔ Old layout preserved
  ✔ Left: Scrolled text preview
  ✔ Right: List of results
  ✔ Supports previewing:
  
  JSON
  
  text files
  ✔ Open file with system default program
  ✔ Download file
  ✔ Username-aware title:
  Storage Retrieval — <username>
  
  ✔ DB-first search
  ✔ Filesystem fallback search
  
  🛡 Safety & Robustness
  
  ✔ Prevents crashes on invalid JSON
  ✔ Prevents UI freezes by using worker threads
  ✔ Handles missing files gracefully
  ✔ Protects against mega-size previews
  ✔ Temporary JSON files are cleaned up automatically
  ✔ All operations isolated per user

  📂 Folder Structure
  AuraVerse/
  │
  ├── auth_ui.py              # Login/Register UI
  ├── Creating_Storage.py     # User storage/db creation logic
  ├── main.py                 # Main dashboard UI
  ├── Search_UI.py            # Search & Retrieval UI
  ├── JsonHandler.py          # JSON parsing utilities
  └── README.md               # Project documentation

🔧 Installation
python3 -m venv .venv
source .venv/bin/activate

# No additional pip installations required
python3 auth_ui.py

▶️ Usage

  Run auth_ui.py
  
  Create a user OR log in
  
  AuraVerse auto-creates per-user storage
  
  Main UI appears
  
  Upload files OR paste JSON in the bottom panel
  
  Search through files using Search UI

🌟 Future Enhancements

  Here are logical future expansions:
  
  🔄 Logout / Switch User button
  
  🔍 Full-text indexing across ALL file types
  
  📤 Export user DB or entire user storage
  
  📋 Import/export JSON schemas
  
  🧪 JSON validation tools (schema, formatting)
  
  🌓 Dark mode UI
  
  🪪 Profile pictures or avatar-based login
  
  🌐 Web version (Flask/FastAPI conversion)
  
  💾 Backup & restore system
  
  📊 File statistics analytics dashboard
