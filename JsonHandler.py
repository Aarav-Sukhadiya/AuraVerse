
import json
from pathlib import Path
from typing import Any, Dict, Optional

def is_json(path: str) -> bool:
    try:
        with open(path, "r", encoding="utf-8") as f:
            json.load(f)
        return True
    except Exception:
        return False

def load_json(path: str) -> Optional[Dict[str, Any]]:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None

def extract_metadata(data: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(data, dict):
        return {"json_keys": "", "json_preview": "", "json_search_text": ""}

    keys = list(data.keys())

    preview = {}
    for k, v in data.items():
        if isinstance(v, (str, int, float, bool)):
            preview[k] = v
        if len(preview) >= 5:
            break

    def flatten(obj):
        if isinstance(obj, dict):
            out = []
            for v in obj.values():
                out.append(flatten(v))
            return " ".join(out)
        elif isinstance(obj, list):
            return " ".join([flatten(x) for x in obj])
        else:
            return str(obj)

    search_text = flatten(data).lower()

    return {
        "json_keys": ",".join(keys),
        "json_preview": json.dumps(preview) if preview else "",
        "json_search_text": search_text
    }

def process_json_file(path: str) -> Dict[str, Any]:
    p = Path(path)
    if not p.exists():
        return {"valid": False, "error": "File not found", "metadata": {}}

    if not is_json(path):
        return {"valid": False, "error": "Invalid JSON file", "metadata": {}}

    data = load_json(path)
    if data is None:
        return {"valid": False, "error": "Failed to load JSON", "metadata": {}}

    meta = extract_metadata(data)
    return {"valid": True, "error": None, "metadata": meta, "raw": data}

# Replace the existing extract_text_from_any_file in JsonHandler.py with this:

def extract_text_from_any_file(path: str) -> str:
    """
    Return searchable text for supported file types.
    - JSON: uses extract_metadata -> json_search_text
    - Plain text-ish extensions (.txt, .md, .csv, .py, .log): returns file contents (safe, truncated)
    - Other extensions: returns empty string (could extend with PDF reader later)
    """
    try:
        p = Path(path)
        ext = p.suffix.lower()

        if ext == ".json":
            data = load_json(path)
            if data is None:
                return ""
            meta = extract_metadata(data)
            return meta.get("json_search_text", "")

        if ext in (".txt", ".md", ".csv", ".log", ".py"):
            # read a modest prefix of the file to avoid OOM on huge files
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                text = f.read(100_000)
                return text.lower()
        # future: add pdf/tiff/office support using external libs if you want

    except Exception:
        return ""
    return ""
