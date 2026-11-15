from pathlib import Path
from dotenv import load_dotenv

# Folder that holds bot.py, .env and info/. Everything path-related hangs off this.
PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Load .env before any submodule reads environment variables at import time
load_dotenv(PROJECT_ROOT / ".env")
