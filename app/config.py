"""Central configuration, loaded from environment / .env."""
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent

# Which LLM backend the Supervisor uses. "gemini" has a genuinely free tier
# (no card required); "anthropic" needs paid API credits.
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "gemini").strip().lower()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-6")

DATABASE_PATH = BASE_DIR / os.getenv("DATABASE_PATH", "data/customers.db")
POLICY_DIR = BASE_DIR / "data" / "policies"

# Not fatal at import time (lets init_db.py and tests run without any key) —
# whichever supervisor implementation is selected will refuse to run without
# its own key.
