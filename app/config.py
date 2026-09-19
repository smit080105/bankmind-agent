"""Central configuration, loaded from environment / .env."""
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent

# Which LLM backend the Supervisor uses. "gemini" has a genuinely free tier
# (no card required); "anthropic" needs paid API credits.
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "groq").strip().lower()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.6-flash")
# Google's AI Studio "AQ." auth keys have had a widespread, unresolved bug
# (as of late 2026) where they're rejected by the standard Gemini Developer
# API with a confusing "Expected OAuth 2 access token" error. Vertex AI
# Express Mode is a separate free product with its own key type that isn't
# affected — set this to true and use an Express Mode key if you hit that.
GEMINI_USE_VERTEX_EXPRESS = os.getenv("GEMINI_USE_VERTEX_EXPRESS", "false").strip().lower() == "true"

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-6")

# Groq: a genuinely free, no-credit-card tier (rate-limited, not credit-
# limited) running open models on their own hardware. No known auth bugs
# as of late 2026, unlike Gemini's AQ.-key issue above — a good fallback.
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")

DATABASE_PATH = BASE_DIR / os.getenv("DATABASE_PATH", "data/customers.db")
POLICY_DIR = BASE_DIR / "data" / "policies"

# Not fatal at import time (lets init_db.py and tests run without any key) —
# whichever supervisor implementation is selected will refuse to run without
# its own key.
