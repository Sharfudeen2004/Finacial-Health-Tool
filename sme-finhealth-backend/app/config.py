from pathlib import Path
import os
from dotenv import load_dotenv

# Load .env from project root (one level above /app)
BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

DATABASE_URL = os.getenv("DATABASE_URL", "")
if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL not set. Put it in project_root/.env")
