from pathlib import Path
import re

path = Path("soccer-mcp-server/soccer_server.py")
text = path.read_text(encoding="utf-8")
text = text.replace(
    "https://api-football-v1.p.rapidapi.com/v3",
    "https://v3.football.api-sports.io"
)
text = re.sub(
    r"\"x-rapidapi-host\": \"api-football-v1\.p\.rapidapi\.com\",?\s*\n\s*",
    "",
    text,
)
text = re.sub(
    r"\"x-rapidapi-key\": api_key\b",
    '"x-apisports-key": api_key',
    text,
)
path.write_text(text, encoding="utf-8")
print("Patch applied successfully.")
