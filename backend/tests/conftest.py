from pathlib import Path
import sys


BACKEND_DIR = Path(__file__).resolve().parents[1]
SOCCER_SERVER_DIR = BACKEND_DIR / "soccer-mcp-server"

for path in (BACKEND_DIR, SOCCER_SERVER_DIR):
    path_str = str(path)
    if path_str not in sys.path:
        sys.path.insert(0, path_str)
