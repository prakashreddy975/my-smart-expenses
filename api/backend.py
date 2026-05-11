"""
Vercel serverless entry: exposes the Flask WSGI app.
Set Project Root to repo root and add DATABASE_URL (Neon) in Vercel env.
"""
import sys
from pathlib import Path

_BACKEND = Path(__file__).resolve().parent.parent / "backend"
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from app import app  # noqa: E402
