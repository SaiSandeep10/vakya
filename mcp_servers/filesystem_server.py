"""
V.A.K.Y.A — Voice Activated Knowledge Yantric Agent
Week 4 | mcp_servers/filesystem_server.py

Filesystem MCP Tool Server.
Lets VAKYA search, list, and read files on your local machine.
Restricted to safe directories only — no system files.
"""

import os
import json
from pathlib import Path
from datetime import datetime

# ──────────────────────────────────────────────
# CONFIG — allowed search directories
# ──────────────────────────────────────────────

ALLOWED_DIRS = [
    Path.home() / "Desktop",
    Path.home() / "Documents",
    Path.home() / "Downloads",
    Path.home() / "OneDrive",
    Path.home() / "Music",
    Path.home() / "Pictures",
]

MAX_RESULTS      = 10     # max files returned per search
MAX_READ_CHARS   = 3000   # max characters read from a file
READABLE_EXTS    = {".txt", ".md", ".py", ".json", ".csv", ".log", ".yaml", ".yml", ".html", ".js"}


# ──────────────────────────────────────────────
# HELPERS
# ──────────────────────────────────────────────

def _is_safe_path(path: Path) -> bool:
    """Ensure the path is within an allowed directory."""
    path = path.resolve()
    return any(
        str(path).startswith(str(allowed.resolve()))
        for allowed in ALLOWED_DIRS
        if allowed.exists()
    )

def _format_size(size_bytes: int) -> str:
    """Human-readable file size."""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 ** 2:
        return f"{size_bytes / 1024:.1f} KB"
    elif size_bytes < 1024 ** 3:
        return f"{size_bytes / 1024**2:.1f} MB"
    return f"{size_bytes / 1024**3:.1f} GB"


# ──────────────────────────────────────────────
# TOOL FUNCTIONS
# ──────────────────────────────────────────────

def search_files(filename: str, directory: str = "") -> dict:
    """
    Search for files by name (partial match) in allowed directories.
    Optionally restrict to a specific subdirectory.
    """
    filename  = filename.strip().lower()
    if not filename:
        return {"success": False, "message": "Please provide a filename to search for."}

    search_dirs = ALLOWED_DIRS
    if directory:
        custom = Path(directory.strip())
        if custom.exists() and _is_safe_path(custom):
            search_dirs = [custom]

    matches = []
    for base in search_dirs:
        if not base.exists():
            continue
        try:
            for root, dirs, files in os.walk(base):
                # Skip hidden folders
                dirs[:] = [d for d in dirs if not d.startswith(".")]
                for f in files:
                    if filename in f.lower():
                        full_path = Path(root) / f
                        try:
                            stat = full_path.stat()
                            matches.append({
                                "name":     f,
                                "path":     str(full_path),
                                "size":     _format_size(stat.st_size),
                                "modified": datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M"),
                            })
                        except PermissionError:
                            continue
                        if len(matches) >= MAX_RESULTS:
                            break
                if len(matches) >= MAX_RESULTS:
                    break
        except PermissionError:
            continue

    if not matches:
        return {"success": True, "message": f"No files found matching '{filename}'.", "files": []}

    summary = f"Found {len(matches)} file{'s' if len(matches) > 1 else ''} matching '{filename}'."
    return {
        "success": True,
        "message": summary,
        "files":   matches
    }


def read_file(filepath: str) -> dict:
    """
    Read the contents of a text file.
    Only readable extensions are supported.
    """
    path = Path(filepath.strip())

    if not path.exists():
        return {"success": False, "message": f"File not found: {filepath}"}

    if not _is_safe_path(path):
        return {"success": False, "message": "Access denied. File is outside allowed directories."}

    if path.suffix.lower() not in READABLE_EXTS:
        return {
            "success": False,
            "message": f"Cannot read {path.suffix} files. Supported: {', '.join(READABLE_EXTS)}"
        }

    try:
        content = path.read_text(encoding="utf-8", errors="replace")
        truncated = len(content) > MAX_READ_CHARS
        content   = content[:MAX_READ_CHARS]

        return {
            "success":   True,
            "message":   f"Read {path.name} ({_format_size(path.stat().st_size)}).",
            "filename":  path.name,
            "content":   content,
            "truncated": truncated
        }
    except PermissionError:
        return {"success": False, "message": f"Permission denied reading {path.name}."}
    except Exception as e:
        return {"success": False, "message": str(e)}


def list_directory(directory: str = "") -> dict:
    """
    List files and folders in a directory.
    Defaults to Desktop if no directory given.
    """
    if directory:
        path = Path(directory.strip())
    else:
        path = Path.home() / "Desktop"

    if not path.exists():
        return {"success": False, "message": f"Directory not found: {directory}"}

    if not _is_safe_path(path):
        return {"success": False, "message": "Access denied. Directory is outside allowed paths."}

    try:
        items = []
        for item in sorted(path.iterdir()):
            if item.name.startswith("."):
                continue
            try:
                stat = item.stat()
                items.append({
                    "name":     item.name,
                    "type":     "folder" if item.is_dir() else "file",
                    "size":     _format_size(stat.st_size) if item.is_file() else "",
                    "modified": datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M"),
                })
            except PermissionError:
                continue

        if not items:
            return {"success": True, "message": f"{path.name} is empty.", "items": []}

        folders = [i for i in items if i["type"] == "folder"]
        files   = [i for i in items if i["type"] == "file"]
        summary = f"{path.name} contains {len(folders)} folder{'s' if len(folders) != 1 else ''} and {len(files)} file{'s' if len(files) != 1 else ''}."

        return {
            "success": True,
            "message": summary,
            "path":    str(path),
            "items":   items[:30]   # cap at 30
        }
    except PermissionError:
        return {"success": False, "message": f"Permission denied accessing {directory}."}
    except Exception as e:
        return {"success": False, "message": str(e)}


def get_recent_files(count: int = 5) -> dict:
    """
    Return the most recently modified files across allowed directories.
    """
    all_files = []

    for base in ALLOWED_DIRS:
        if not base.exists():
            continue
        try:
            for root, dirs, files in os.walk(base):
                dirs[:] = [d for d in dirs if not d.startswith(".")]
                for f in files:
                    if f.startswith("."):
                        continue
                    full_path = Path(root) / f
                    try:
                        mtime = full_path.stat().st_mtime
                        all_files.append((mtime, full_path))
                    except (PermissionError, OSError):
                        continue
        except PermissionError:
            continue

    all_files.sort(key=lambda x: x[0], reverse=True)
    recent = all_files[:count]

    if not recent:
        return {"success": True, "message": "No recent files found.", "files": []}

    files_info = [{
        "name":     str(p.name),
        "path":     str(p),
        "modified": datetime.fromtimestamp(t).strftime("%Y-%m-%d %H:%M")
    } for t, p in recent]

    names = ", ".join(f["name"] for f in files_info[:3])
    return {
        "success": True,
        "message": f"Most recent files: {names}.",
        "files":   files_info
    }


# ──────────────────────────────────────────────
# TOOL DEFINITIONS
# ──────────────────────────────────────────────

FILESYSTEM_TOOLS = [
    {
        "name":        "search_files",
        "description": "Search for files by name on the user's computer. Searches Desktop, Documents, Downloads, and OneDrive.",
        "function":    search_files,
        "parameters":  {"filename": str, "directory": str}
    },
    {
        "name":        "read_file",
        "description": "Read the text contents of a file. Works with .txt, .md, .py, .json, .csv files.",
        "function":    read_file,
        "parameters":  {"filepath": str}
    },
    {
        "name":        "list_directory",
        "description": "List the files and folders inside a directory. Defaults to Desktop.",
        "function":    list_directory,
        "parameters":  {"directory": str}
    },
    {
        "name":        "get_recent_files",
        "description": "Get the most recently modified files on the user's computer.",
        "function":    get_recent_files,
        "parameters":  {"count": int}
    },
]


# ──────────────────────────────────────────────
# STANDALONE TEST
# Run: python mcp_servers/filesystem_server.py
# ──────────────────────────────────────────────

if __name__ == "__main__":
    print("[TEST] Listing Desktop:")
    result = list_directory()
    print(json.dumps(result, indent=2))

    print("\n[TEST] Recent files:")
    result = get_recent_files(3)
    print(json.dumps(result, indent=2))

    print("\n[TEST] Searching for 'vakya':")
    result = search_files("vakya")
    print(json.dumps(result, indent=2))