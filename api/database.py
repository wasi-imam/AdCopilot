"""
Supabase client setup for AdCopilot.
This module creates a single shared Supabase client instance
that the rest of the app (routers, services) can import and reuse.
"""

import os
from dotenv import load_dotenv
from supabase import create_client, Client

# Load variables from .env into the environment
load_dotenv()

SUPABASE_URL: str = os.getenv("SUPABASE_URL")
SUPABASE_SECRET_KEY: str = os.getenv("SUPABASE_SECRET_KEY")

if not SUPABASE_URL or not SUPABASE_SECRET_KEY:
    raise ValueError(
        "Missing SUPABASE_URL or SUPABASE_SECRET_KEY in .env file. "
        "Check your .env configuration."
    )

# Single shared client instance — backend uses the secret key
# because it needs full read/write access (not subject to RLS).
supabase: Client = create_client(SUPABASE_URL, SUPABASE_SECRET_KEY)