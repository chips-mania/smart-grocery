from supabase import Client

from app.common.supabase_client import supabase


class BaseRepository:

    def __init__(self):

        self.db: Client = supabase