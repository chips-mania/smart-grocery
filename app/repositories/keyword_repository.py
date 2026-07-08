"""Legacy keyword map repository.

v3 uses ingredient_vectors_v3 + match_products_v3 instead of search_keyword_map.
Kept so old imports do not crash; always returns empty.
"""

from app.repositories.base_repository import BaseRepository


class KeywordRepository(BaseRepository):

    def get_search_keywords(self, ingredient: str) -> list[str]:
        return []

    def get_search_keyword(self, ingredient: str) -> dict | None:
        return None
