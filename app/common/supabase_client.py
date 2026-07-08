from supabase import Client
from supabase import create_client

from app.common.config import SUPABASE_KEY
from app.common.config import SUPABASE_URL

supabase: Client = create_client(
    SUPABASE_URL,
    SUPABASE_KEY,
)