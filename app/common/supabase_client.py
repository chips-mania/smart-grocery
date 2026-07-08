from __future__ import annotations

from typing import Any

from supabase import Client
from supabase import create_client

from app.common.config import SUPABASE_KEY
from app.common.config import SUPABASE_URL

_client: Client | None = None


def get_supabase() -> Client:
    global _client
    if _client is not None:
        return _client
    if not SUPABASE_URL or not SUPABASE_KEY:
        raise RuntimeError(
            "SUPABASE_URL and SUPABASE_KEY environment variables are required"
        )
    _client = create_client(SUPABASE_URL, SUPABASE_KEY)
    return _client


class _LazySupabase:
    """Defer client creation so missing env vars do not crash import."""

    def __getattr__(self, name: str) -> Any:
        return getattr(get_supabase(), name)


supabase = _LazySupabase()
